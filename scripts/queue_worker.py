from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import traceback
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_v39(root: Path):
    source = root / "Suno15_Mastering_v3_9.pyw"
    loader = SourceFileLoader("haru_queue_v39", str(source))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {source}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, type=Path)
    args = parser.parse_args()
    job_path = args.job.resolve()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    progress_path = Path(job["progress_file"])
    result_path = Path(job["result_file"])
    log_path = job_path.parent / "worker.log"
    root = Path(__file__).resolve().parents[1]
    files = sorted(
        [path for path in Path(job["folder"]).iterdir() if path.is_file() and path.suffix.lower() in {".wav", ".wave"}],
        key=lambda path: path.name.lower(),
    )
    atomic_json(progress_path, {"status": "RUNNING", "current_track": 0, "total_tracks": len(files), "stage": "starting"})
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"worker starting: job={job['job_id']} pid={os.getpid()}\n", encoding="utf-8")
    try:
        import tkinter as tk

        app_module = load_v39(root)
        app = app_module.AppV39()
        app.withdraw()
        app.queue_job_id = str(job["job_id"])
        app_module.legacy.messagebox.showinfo = lambda *_args, **_kwargs: None
        app_module.legacy.messagebox.showwarning = lambda *_args, **_kwargs: None
        app_module.legacy.messagebox.showerror = lambda *_args, **_kwargs: None

        def direct_after(_delay, callback, *callback_args):
            return callback(*callback_args)

        app.after = direct_after
        app.channel_var.set(job["channel_key"])
        app.genre_var.set(job["genre_key"])
        app.sound_var.set(job["sound_mode"])
        app.quality_var.set(job["quality_mode"])

        original_stage = app._stage_status

        def progress_stage(index, total, stage, source):
            with log_path.open("a", encoding="utf-8") as log_handle:
                log_handle.write(f"[{index:02d}/{total:02d}] {stage}: {source.name}\n")
            atomic_json(
                progress_path,
                {
                    "status": "RUNNING",
                    "current_track": int(index),
                    "total_tracks": int(total),
                    "stage": str(stage),
                    "track_name": source.name,
                    "updated_at": app_module.datetime.now().isoformat(timespec="seconds"),
                },
            )
            return original_stage(index, total, stage, source)

        app._stage_status = progress_stage
        app._worker(Path(job["folder"]), files)
        output_dir = str(getattr(app, "last_output_dir", "") or "")
        report_path = Path(output_dir) / "mastering_report.csv"
        rows = []
        if report_path.exists():
            with report_path.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
        if not report_path.exists():
            raise RuntimeError("mastering worker completed without mastering_report.csv")
        review = sum(row.get("release_disposition") == "NEEDS_REVIEW" for row in rows)
        status = "COMPLETED_WITH_REVIEW" if review else "COMPLETED"
        result = {
            "status": status,
            "output_dir": output_dir,
            "total_tracks": len(files),
            "release_ready": len(rows) - review,
            "needs_review": review,
            "pass": sum(row.get("quality_status") == "PASS" for row in rows),
            "warn": sum(row.get("quality_status") == "WARN" for row in rows),
            "fail": sum(row.get("quality_status") == "FAIL" for row in rows),
        }
        atomic_json(result_path, result)
        return 0
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as exc:
        trace_path = job_path.parent / "ERROR_worker.txt"
        trace_path.write_text(traceback.format_exc(), encoding="utf-8")
        atomic_json(result_path, {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}", "traceback_file": str(trace_path)})
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        return 1


if __name__ == "__main__":
    sys.exit(main())
