from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


QUEUE_VERSION = "v3.10"
STATUSES = {
    "WAITING",
    "RUNNING",
    "COMPLETED",
    "COMPLETED_WITH_REVIEW",
    "NEEDS_REVIEW",
    "FAILED",
    "CANCELLED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class MasteringQueueJob:
    job_id: str
    folder: str
    channel_key: str
    genre_key: str
    sound_mode: str
    quality_mode: str
    status: str = "WAITING"
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    completed_at: str | None = None
    current_track: int = 0
    total_tracks: int = 0
    output_dir: str | None = None
    process_id: int | None = None
    error_message: str | None = None
    validation_warning: str | None = None
    progress_file: str = ""
    result_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MasteringQueueJob":
        values = {field_name: payload.get(field_name) for field_name in cls.__dataclass_fields__}
        values["status"] = values.get("status") or "WAITING"
        return cls(**values)


def atomic_write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)


def read_json(path: str | Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


class QueueStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.jobs_root = self.root / "jobs"
        self.state_path = self.root / "queue_state.json"

    def job_paths(self, job_id: str) -> dict[str, Path]:
        directory = self.jobs_root / job_id
        return {
            "directory": directory,
            "job": directory / "job.json",
            "progress": directory / "progress.json",
            "result": directory / "result.json",
            "log": directory / "worker.log",
        }

    def save(self, jobs: Iterable[MasteringQueueJob], *, paused: bool = False) -> None:
        jobs_list = list(jobs)
        for job in jobs_list:
            paths = self.job_paths(job.job_id)
            job.progress_file = str(paths["progress"])
            job.result_file = str(paths["result"])
            atomic_write_json(paths["job"], job.to_dict())
        atomic_write_json(
            self.state_path,
            {"version": QUEUE_VERSION, "paused": bool(paused), "jobs": [job.to_dict() for job in jobs_list]},
        )

    def load(self) -> tuple[list[MasteringQueueJob], bool]:
        payload = read_json(self.state_path, {}) or {}
        jobs = [MasteringQueueJob.from_dict(item) for item in payload.get("jobs", [])]
        paused = bool(payload.get("paused", False))
        for job in jobs:
            if job.status == "RUNNING":
                job.status = "WAITING"
                job.process_id = None
                job.error_message = "previous worker was not running; queued from the beginning"
        return jobs, paused


class WindowsSleepInhibitor:
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self, api: Any | None = None):
        self._api = api
        self.active = False

    def enter(self) -> None:
        if self.active:
            return
        if self._api is None and os.name == "nt":
            self._api = ctypes.windll.kernel32.SetThreadExecutionState
        if self._api is not None:
            self._api(self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED)
        self.active = True

    def restore(self) -> None:
        if not self.active:
            return
        if self._api is not None:
            self._api(self.ES_CONTINUOUS)
        self.active = False


class QueueManager:
    def __init__(
        self,
        store: QueueStore,
        *,
        max_concurrency: int = 1,
        popen: Callable[..., Any] = subprocess.Popen,
        command_builder: Callable[[MasteringQueueJob], list[str]] | None = None,
        on_update: Callable[[MasteringQueueJob], None] | None = None,
        sleep_inhibitor: WindowsSleepInhibitor | None = None,
        sleep_prevention: bool = True,
    ):
        self.store = store
        self.jobs, self.paused = store.load()
        self.max_concurrency = 1 if int(max_concurrency) != 2 else 2
        self.popen = popen
        self.command_builder = command_builder or default_worker_command
        self.on_update = on_update
        self.sleep_inhibitor = sleep_inhibitor or WindowsSleepInhibitor()
        self.sleep_prevention = bool(sleep_prevention)
        self.processes: dict[str, Any] = {}
        self.stop_after_current = False

    @property
    def active_jobs(self) -> list[MasteringQueueJob]:
        return [job for job in self.jobs if job.status == "RUNNING"]

    def _changed(self, job: MasteringQueueJob | None = None) -> None:
        self.store.save(self.jobs, paused=self.paused)
        if job is not None and self.on_update:
            self.on_update(job)

    def add_job(self, folder: str | Path, *, channel_key: str, genre_key: str, sound_mode: str, quality_mode: str) -> MasteringQueueJob:
        folder_path = Path(folder).resolve()
        if any(Path(job.folder).resolve() == folder_path and job.status in {"WAITING", "RUNNING"} for job in self.jobs):
            raise ValueError("this source folder is already in the queue")
        audio_count = len([path for path in folder_path.iterdir() if path.is_file() and path.suffix.lower() in {".wav", ".wave"}])
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:6]
        job = MasteringQueueJob(
            job_id=job_id,
            folder=str(folder_path),
            channel_key=str(channel_key),
            genre_key=str(genre_key),
            sound_mode=str(sound_mode),
            quality_mode=str(quality_mode),
            total_tracks=audio_count,
            validation_warning=(None if audio_count == 15 else f"expected 15 WAV files, found {audio_count}"),
        )
        self.jobs.append(job)
        self._changed(job)
        return job

    def remove(self, job_id: str) -> bool:
        before = len(self.jobs)
        self.jobs = [job for job in self.jobs if job.job_id != job_id or job.status == "RUNNING"]
        removed = len(self.jobs) != before
        if removed:
            self._changed()
        return removed

    def remove_waiting_jobs(self) -> int:
        before = len(self.jobs)
        self.jobs = [job for job in self.jobs if job.status != "WAITING"]
        removed = before - len(self.jobs)
        if removed:
            self._changed()
        return removed

    def cancel_job(self, job_id: str) -> bool:
        job = next((job for job in self.jobs if job.job_id == job_id), None)
        if job is None:
            return False
        if job.status == "WAITING":
            job.status = "CANCELLED"
            job.completed_at = utc_now()
            job.process_id = None
            self._changed(job)
            return True
        if job.status != "RUNNING":
            return False

        process = self.processes.pop(job_id, None)
        if process is not None:
            self._terminate_process(process)
        job.status = "CANCELLED"
        job.completed_at = utc_now()
        job.process_id = None
        self._changed(job)
        if not self.active_jobs:
            self.sleep_inhibitor.restore()
        self._launch_available()
        return True

    def _terminate_process(self, process: Any) -> None:
        try:
            process.terminate()
        except Exception:
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except Exception:
                return
            try:
                process.wait(timeout=5)
            except Exception:
                return
        except Exception:
            return

    def start(self) -> None:
        self.paused = False
        self.stop_after_current = False
        self._launch_available()

    def pause(self) -> None:
        self.paused = True
        self._changed()

    def stop_after_current_jobs(self) -> None:
        self.stop_after_current = True
        self._changed()

    def set_concurrency(self, value: int) -> None:
        self.max_concurrency = 1 if int(value) != 2 else 2
        self._launch_available()

    def set_sleep_prevention(self, enabled: bool) -> None:
        self.sleep_prevention = bool(enabled)
        if self.sleep_prevention and self.active_jobs:
            self.sleep_inhibitor.enter()
        elif not self.sleep_prevention:
            self.sleep_inhibitor.restore()

    def _launch_available(self) -> None:
        if self.paused or self.stop_after_current:
            return
        while len(self.active_jobs) < self.max_concurrency:
            waiting = next((job for job in self.jobs if job.status == "WAITING"), None)
            if waiting is None:
                break
            paths = self.store.job_paths(waiting.job_id)
            waiting.progress_file = str(paths["progress"])
            waiting.result_file = str(paths["result"])
            waiting.status = "RUNNING"
            waiting.started_at = utc_now()
            waiting.process_id = None
            atomic_write_json(paths["job"], waiting.to_dict())
            try:
                process = self.popen(
                    self.command_builder(waiting),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                waiting.status = "FAILED"
                waiting.completed_at = utc_now()
                waiting.error_message = f"could not start worker: {exc}"
                self._changed(waiting)
                continue
            waiting.process_id = int(getattr(process, "pid", 0) or 0)
            self.processes[waiting.job_id] = process
            self._changed(waiting)
        if self.active_jobs and self.sleep_prevention:
            self.sleep_inhibitor.enter()

    def poll(self) -> None:
        for job_id, process in list(self.processes.items()):
            code = process.poll()
            if code is None:
                progress = read_json(self.store.job_paths(job_id)["progress"], {}) or {}
                job = next(job for job in self.jobs if job.job_id == job_id)
                job.current_track = int(progress.get("current_track", job.current_track) or 0)
                job.total_tracks = int(progress.get("total_tracks", job.total_tracks) or 0)
                self._changed(job)
                continue
            job = next(job for job in self.jobs if job.job_id == job_id)
            result = read_json(self.store.job_paths(job_id)["result"], {}) or {}
            if code == 0 and result.get("status") in {"COMPLETED", "COMPLETED_WITH_REVIEW"}:
                job.status = str(result["status"])
                job.output_dir = result.get("output_dir")
                job.current_track = int(result.get("total_tracks", job.total_tracks) or job.total_tracks)
            else:
                job.status = "FAILED"
                job.error_message = result.get("error") or f"worker exited with code {code}"
            job.completed_at = utc_now()
            job.process_id = None
            self.processes.pop(job_id, None)
            self._changed(job)
        if not self.active_jobs:
            self.sleep_inhibitor.restore()
        self._launch_available()

    def shutdown(self) -> None:
        self.sleep_inhibitor.restore()


def default_worker_command(job: MasteringQueueJob) -> list[str]:
    root = Path(__file__).resolve().parents[2]
    worker = root / "scripts" / "queue_worker.py"
    return [sys.executable, str(worker), "--job", str(Path(job.progress_file).parent / "job.json")]
