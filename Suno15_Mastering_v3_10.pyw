"""HARU Mastering v3.10 Queue Manager UI.

The v3.9 mastering engine remains isolated in its own child process.
"""
from __future__ import annotations

import os
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_v39():
    source = ROOT / "Suno15_Mastering_v3_9.pyw"
    loader = SourceFileLoader("haru_queue_v39_ui", str(source))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {source}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v39 = _load_v39()
from haru_mastering.queue_manager import QueueManager, QueueStore


class AppV310(v39.AppV39):
    def __init__(self):
        super().__init__()
        self.title("HARU Mastering v3.10 - 작업 대기열")
        self.queue_manager = QueueManager(
            QueueStore(ROOT / ".haru_queue"),
            max_concurrency=1,
            on_update=lambda _job: self.after(0, self._refresh_queue_tree),
        )
        self._build_queue_tab()
        self.protocol("WM_DELETE_WINDOW", self._close_queue)
        self.after(500, self._queue_tick)

    def _build_queue_tab(self):
        ttk = v39.legacy.ttk
        tk = v39.legacy.tk
        self.queue_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.queue_tab, text="작업 대기열")

        controls = ttk.LabelFrame(self.queue_tab, text="HARU MASTERING QUEUE")
        controls.pack(fill="x", padx=14, pady=(14, 8))
        top = ttk.Frame(controls)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Button(top, text="+ 작업 추가", command=self._queue_add_job).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="여러 폴더 추가", command=self._queue_add_root).pack(side="left", padx=6)
        ttk.Button(top, text="선택 삭제", command=self._queue_remove_selected).pack(side="left", padx=6)
        ttk.Button(top, text="결과 폴더 열기", command=self._queue_open_result).pack(side="left", padx=6)

        settings = ttk.Frame(controls)
        settings.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(settings, text="동시 작업 수").pack(side="left", padx=(0, 8))
        self.queue_concurrency = tk.IntVar(value=1)
        ttk.Radiobutton(settings, text="1개", variable=self.queue_concurrency, value=1, command=self._queue_concurrency_changed).pack(side="left")
        ttk.Radiobutton(settings, text="2개", variable=self.queue_concurrency, value=2, command=self._queue_concurrency_changed).pack(side="left", padx=(8, 20))
        self.queue_sleep_prevention = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings, text="작업 중 PC 절전 방지", variable=self.queue_sleep_prevention, command=self._queue_sleep_changed).pack(side="left")

        actions = ttk.Frame(controls)
        actions.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(actions, text="전체 시작", command=self._queue_start).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="대기열 일시정지", command=self._queue_pause).pack(side="left", padx=6)
        ttk.Button(actions, text="현재 작업 후 정지", command=self._queue_stop_after_current).pack(side="left", padx=6)
        self.queue_status = tk.StringVar(value="대기열 준비")
        ttk.Label(actions, textvariable=self.queue_status).pack(side="right")

        columns = ("id", "status", "folder", "channel", "genre", "sound", "quality", "progress", "pid", "result")
        self.queue_tree = ttk.Treeview(self.queue_tab, columns=columns, show="headings", height=15)
        headings = {
            "id": "작업 ID", "status": "상태", "folder": "폴더", "channel": "채널", "genre": "장르",
            "sound": "사운드", "quality": "품질", "progress": "진행", "pid": "PID", "result": "결과",
        }
        widths = {"id": 180, "status": 130, "folder": 180, "channel": 150, "genre": 120, "sound": 75, "quality": 85, "progress": 75, "pid": 75, "result": 170}
        for column in columns:
            self.queue_tree.heading(column, text=headings[column])
            self.queue_tree.column(column, width=widths[column], anchor="center" if column != "folder" else "w")
        self.queue_tree.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self._refresh_queue_tree()

    def _queue_sleep_changed(self):
        self.queue_manager.set_sleep_prevention(self.queue_sleep_prevention.get())

    def _queue_concurrency_changed(self):
        self.queue_manager.set_concurrency(self.queue_concurrency.get())
        self._refresh_queue_tree()

    def _queue_add_job(self):
        folder = v39.legacy.filedialog.askdirectory(title="마스터링 작업 폴더 선택")
        if folder:
            self._add_queue_folder(Path(folder))

    def _queue_add_root(self):
        root = v39.legacy.filedialog.askdirectory(title="앨범 상위 폴더 선택")
        if not root:
            return
        folders = [path for path in Path(root).iterdir() if path.is_dir() and any(item.suffix.lower() in {".wav", ".wave"} for item in path.iterdir() if item.is_file())]
        for folder in sorted(folders, key=lambda path: path.name.lower()):
            self._add_queue_folder(folder, show_errors=False)
        self._refresh_queue_tree()

    def _add_queue_folder(self, folder: Path, *, show_errors: bool = True):
        try:
            self.queue_manager.add_job(
                folder,
                channel_key=self.channel_var.get(),
                genre_key=self.genre_var.get(),
                sound_mode=self.sound_var.get(),
                quality_mode=self.quality_var.get(),
            )
        except (ValueError, OSError) as exc:
            if show_errors:
                v39.legacy.messagebox.showwarning("작업을 추가할 수 없음", str(exc))
        self._refresh_queue_tree()

    def _queue_remove_selected(self):
        for item in self.queue_tree.selection():
            values = self.queue_tree.item(item, "values")
            job = next((job for job in self.queue_manager.jobs if job.job_id == values[0]), None)
            if job and job.status != "RUNNING":
                self.queue_manager.remove(job.job_id)
        self._refresh_queue_tree()

    def _queue_start(self):
        self.queue_manager.start()
        self.queue_status.set("대기열 실행 중")
        self._refresh_queue_tree()

    def _queue_pause(self):
        self.queue_manager.pause()
        self.queue_status.set("PAUSED - 실행 중 작업은 계속")

    def _queue_stop_after_current(self):
        self.queue_manager.stop_after_current_jobs()
        self.queue_status.set("현재 작업 완료 후 정지")

    def _queue_open_result(self):
        selection = self.queue_tree.selection()
        if not selection:
            return
        values = self.queue_tree.item(selection[0], "values")
        job = next((job for job in self.queue_manager.jobs if job.job_id == values[0]), None)
        if job and job.output_dir and Path(job.output_dir).exists() and os.name == "nt":
            os.startfile(job.output_dir)

    def _refresh_queue_tree(self):
        if not hasattr(self, "queue_tree"):
            return
        self.queue_tree.delete(*self.queue_tree.get_children())
        for job in self.queue_manager.jobs:
            result = ""
            if job.status in {"COMPLETED", "COMPLETED_WITH_REVIEW"}:
                result = job.status.replace("COMPLETED_WITH_", "")
            elif job.validation_warning:
                result = job.validation_warning
            elif job.error_message:
                result = job.error_message[:32]
            values = (
                job.job_id, job.status, Path(job.folder).name, job.channel_key, job.genre_key,
                job.sound_mode, job.quality_mode, f"{job.current_track}/{job.total_tracks}",
                job.process_id or "", result,
            )
            self.queue_tree.insert("", "end", values=values)

    def _queue_tick(self):
        self.queue_manager.poll()
        self._refresh_queue_tree()
        self.after(1000, self._queue_tick)

    def start_mastering(self):
        if self.queue_manager.active_jobs:
            v39.legacy.messagebox.showwarning("Queue 실행 중", "Queue 실행 중에는 단일 마스터링을 시작할 수 없습니다.")
            return
        return super().start_mastering()

    def _close_queue(self):
        self.queue_manager.shutdown()
        self.destroy()


if __name__ == "__main__":
    AppV310().mainloop()
