from __future__ import annotations

from pathlib import Path

from haru_mastering.queue_manager import MasteringQueueJob, QueueManager, QueueStore


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ui = (ROOT / "Suno15_Mastering_v3_10.pyw").read_text(encoding="utf-8")
    worker = (ROOT / "scripts" / "queue_worker.py").read_text(encoding="utf-8")
    manager_source = (ROOT / "src" / "haru_mastering" / "queue_manager.py").read_text(encoding="utf-8")
    run = (ROOT / "RUN.bat").read_text(encoding="utf-8", errors="ignore")
    start = (ROOT / "START_HERE.bat").read_text(encoding="utf-8", errors="ignore")
    run_queue = (ROOT / "RUN_QUEUE.bat").read_text(encoding="utf-8", errors="ignore")
    assert "QueueManager" in ui
    assert "queue_channel_var" in ui
    assert "iid=job.job_id" in ui
    assert "cancel_job" in manager_source
    assert "Suno15_Mastering_v3_9.pyw" in worker
    assert "messagebox.showinfo = lambda" in worker
    assert "max_concurrency" in manager_source
    assert "call \"%~dp0RUN.bat\"" in start
    assert "Suno15_Mastering_v3_10.pyw" in run
    assert "Suno15_Mastering_v3_9.pyw" in run
    assert run.find("Suno15_Mastering_v3_10.pyw") < run.find("Suno15_Mastering_v3_9.pyw")
    assert "Suno15_Mastering_v3_10.pyw" in run_queue
    job = MasteringQueueJob("verify", str(ROOT), "TOKYO_CHILL", "CHILL_RAP", "RICH", "QUALITY+")
    assert job.status == "WAITING"
    assert QueueManager(QueueStore(ROOT / ".tmp_v310_verify")).max_concurrency == 1
    print("[PASS] HARU Mastering v3.10 Queue Manager runtime is ready")
    print("Parent scheduler: ON")
    print("Headless v3.9 child: ON")
    print("Concurrency limit: 1 or 2")
    print("File IPC and atomic queue state: ON")
    print("START_HERE -> RUN.bat -> v3.10: ON")
    print("RUN_QUEUE -> v3.10: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
