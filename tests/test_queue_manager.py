from __future__ import annotations

import json
from pathlib import Path

from haru_mastering.queue_manager import (
    MasteringQueueJob,
    QueueManager,
    QueueStore,
    WindowsSleepInhibitor,
    atomic_write_json,
)


def _folder(tmp_path: Path, name: str, count: int = 15) -> Path:
    folder = tmp_path / name
    folder.mkdir()
    for index in range(count):
        (folder / f"{index + 1:02d}.wav").write_bytes(b"RIFF")
    return folder


class FakeProcess:
    next_pid = 1000

    def __init__(self, *, exit_code: int | None = None):
        self.pid = FakeProcess.next_pid
        FakeProcess.next_pid += 1
        self.exit_code = exit_code
        self.terminated = False
        self.killed = False
        self.wait_timeouts = []

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.terminated = True
        if self.exit_code is None:
            self.exit_code = -15

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        return self.exit_code

    def kill(self):
        self.killed = True
        self.exit_code = -9


def _manager(tmp_path, *, concurrency=1, processes=None, inhibitor=None):
    created = processes if processes is not None else []

    def popen(*_args, **_kwargs):
        process = FakeProcess()
        created.append(process)
        return process

    manager = QueueManager(
        QueueStore(tmp_path / ".haru_queue"),
        max_concurrency=concurrency,
        popen=popen,
        command_builder=lambda job: ["fake", job.job_id],
        sleep_inhibitor=inhibitor,
    )
    return manager, created


def test_queue_job_serialization_and_atomic_state(tmp_path):
    store = QueueStore(tmp_path / ".haru_queue")
    job = MasteringQueueJob("job1", str(tmp_path), "TOKYO_CHILL", "CHILL_RAP", "RICH", "QUALITY+")
    store.save([job])
    assert store.state_path.exists()
    restored, paused = store.load()
    assert paused is False
    assert restored[0].to_dict() == job.to_dict()
    target = tmp_path / "atomic.json"
    atomic_write_json(target, {"ok": True})
    assert json.loads(target.read_text()) == {"ok": True}


def test_queue_restores_waiting_and_orphaned_running_job(tmp_path):
    store = QueueStore(tmp_path / ".haru_queue")
    waiting = MasteringQueueJob("wait", str(tmp_path), "A", "B", "NATURAL", "FAST")
    running = MasteringQueueJob("run", str(tmp_path), "A", "B", "NATURAL", "FAST", status="RUNNING", process_id=42)
    store.save([waiting, running])
    restored, _ = store.load()
    assert [job.status for job in restored] == ["WAITING", "WAITING"]
    assert restored[1].process_id is None


def test_duplicate_source_folder_warning_and_fifteen_file_warning(tmp_path):
    manager, _ = _manager(tmp_path)
    folder = _folder(tmp_path, "album", count=14)
    job = manager.add_job(folder, channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="QUALITY+")
    assert job.validation_warning == "expected 15 WAV files, found 14"
    try:
        manager.add_job(folder, channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="QUALITY+")
    except ValueError as exc:
        assert "already" in str(exc)
    else:
        raise AssertionError("duplicate source folder was accepted")


def test_queue_concurrency_one_and_two_never_exceed_limit(tmp_path):
    manager, processes = _manager(tmp_path, concurrency=1)
    for name in ("a", "b", "c"):
        manager.add_job(_folder(tmp_path, name), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    manager.start()
    assert len(manager.processes) == 1
    assert len([job for job in manager.jobs if job.status == "RUNNING"]) == 1
    processes[0].exit_code = 0
    paths = manager.store.job_paths(manager.jobs[0].job_id)
    atomic_write_json(paths["result"], {"status": "COMPLETED", "total_tracks": 15})
    manager.poll()
    assert len(manager.processes) == 1

    second_root = tmp_path / "second"
    second_root.mkdir()
    manager2, processes2 = _manager(second_root, concurrency=2)
    for name in ("a", "b", "c"):
        manager2.add_job(_folder(tmp_path / "second", name), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    manager2.start()
    assert len(manager2.processes) == 2
    assert len(manager2.active_jobs) == 2
    assert len(processes2) == 2


def test_pause_and_stop_after_current_do_not_kill_running_jobs(tmp_path):
    manager, processes = _manager(tmp_path, concurrency=2)
    for name in ("a", "b", "c"):
        manager.add_job(_folder(tmp_path, name), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    manager.start()
    manager.pause()
    assert len(manager.processes) == 2
    manager.poll()
    assert len(manager.processes) == 2
    manager.stop_after_current_jobs()
    assert len(manager.processes) == 2
    assert all(process.exit_code is None for process in processes)


def test_remove_selected_waiting_jobs_and_refuse_running_job(tmp_path):
    manager, _ = _manager(tmp_path, concurrency=1)
    jobs = [
        manager.add_job(_folder(tmp_path, name), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
        for name in ("a", "b", "c", "d")
    ]
    assert manager.remove(jobs[0].job_id) is True
    assert manager.remove(jobs[2].job_id) is True
    assert [job.job_id for job in manager.jobs] == [jobs[1].job_id, jobs[3].job_id]

    manager.start()
    running = manager.jobs[0]
    assert running.status == "RUNNING"
    assert manager.remove(running.job_id) is False
    assert manager.jobs[0].job_id == running.job_id
    assert manager.jobs[0].status == "RUNNING"


def test_remove_waiting_jobs_keeps_running_job(tmp_path):
    manager, _ = _manager(tmp_path, concurrency=1)
    for name in ("a", "b", "c"):
        manager.add_job(_folder(tmp_path, name), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    manager.start()
    removed = manager.remove_waiting_jobs()
    assert removed == 2
    assert len(manager.jobs) == 1
    assert manager.jobs[0].status == "RUNNING"


def test_cancel_running_job_terminates_process_and_continues_queue(tmp_path):
    manager, processes = _manager(tmp_path, concurrency=1)
    first = manager.add_job(_folder(tmp_path, "a"), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    second = manager.add_job(_folder(tmp_path, "b"), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    manager.start()

    assert manager.cancel_job(first.job_id) is True

    assert processes[0].terminated is True
    assert processes[0].wait_timeouts == [5]
    assert manager.jobs[0].status == "CANCELLED"
    assert manager.jobs[0].process_id is None
    assert manager.jobs[0].completed_at
    assert manager.jobs[1].job_id == second.job_id
    assert manager.jobs[1].status == "RUNNING"
    assert len(manager.processes) == 1


def test_worker_crash_marks_failed_and_starts_next_job(tmp_path):
    manager, processes = _manager(tmp_path, concurrency=1)
    first = manager.add_job(_folder(tmp_path, "a"), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    manager.add_job(_folder(tmp_path, "b"), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    manager.start()
    processes[0].exit_code = 1
    atomic_write_json(manager.store.job_paths(first.job_id)["result"], {"status": "FAILED", "error": "boom"})
    manager.poll()
    assert manager.jobs[0].status == "FAILED"
    assert len(manager.processes) == 1
    assert manager.jobs[1].status == "RUNNING"


def test_review_is_distinct_from_process_failure(tmp_path):
    manager, processes = _manager(tmp_path)
    job = manager.add_job(_folder(tmp_path, "a"), channel_key="A", genre_key="B", sound_mode="RICH", quality_mode="FAST")
    manager.start()
    processes[0].exit_code = 0
    atomic_write_json(manager.store.job_paths(job.job_id)["result"], {"status": "COMPLETED_WITH_REVIEW", "total_tracks": 15})
    manager.poll()
    assert manager.jobs[0].status == "COMPLETED_WITH_REVIEW"


def test_sleep_prevention_enters_and_restores_state(tmp_path):
    calls = []
    inhibitor = WindowsSleepInhibitor(api=lambda value: calls.append(value))
    manager, _ = _manager(tmp_path, inhibitor=inhibitor)
    manager.sleep_inhibitor.enter()
    assert calls[-1] == inhibitor.ES_CONTINUOUS | inhibitor.ES_SYSTEM_REQUIRED
    manager.shutdown()
    assert calls[-1] == inhibitor.ES_CONTINUOUS
