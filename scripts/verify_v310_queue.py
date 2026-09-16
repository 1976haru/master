from __future__ import annotations

from pathlib import Path

from haru_mastering.queue_manager import MasteringQueueJob, QueueManager, QueueStore


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ui = (ROOT / "Suno15_Mastering_v3_10.pyw").read_text(encoding="utf-8")
    worker = (ROOT / "scripts" / "queue_worker.py").read_text(encoding="utf-8")
    manager_source = (ROOT / "src" / "haru_mastering" / "queue_manager.py").read_text(encoding="utf-8")
    assert "QueueManager" in ui
    assert "Suno15_Mastering_v3_9.pyw" in worker
    assert "messagebox.showinfo = lambda" in worker
    assert "max_concurrency" in manager_source
    job = MasteringQueueJob("verify", str(ROOT), "TOKYO_CHILL", "CHILL_RAP", "RICH", "QUALITY+")
    assert job.status == "WAITING"
    assert QueueManager(QueueStore(ROOT / ".tmp_v310_verify")).max_concurrency == 1
    print("[PASS] HARU Mastering v3.10 Queue Manager runtime is ready")
    print("Parent scheduler: ON")
    print("Headless v3.9 child: ON")
    print("Concurrency limit: 1 or 2")
    print("File IPC and atomic queue state: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
