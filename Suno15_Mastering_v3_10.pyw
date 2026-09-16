"""HARU Mastering v3.10 Queue Manager UI.

The v3.9 mastering engine remains isolated in its own child process.
"""
from __future__ import annotations

import os
import sys
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
    sys.modules[loader.name] = module
    try:
        loader.exec_module(module)
    except Exception:
        sys.modules.pop(loader.name, None)
        raise
    return module


v39 = _load_v39()
from haru_mastering.profile_catalog import (  # noqa: E402
    CHANNEL_DISPLAY_ORDER,
    CHANNEL_PROFILES,
    DEFAULT_SOUND_MODE,
    GENRE_DISPLAY_ORDER,
    GENRE_PROFILES,
    normalize_channel_key,
    normalize_genre_key,
)
from haru_mastering.queue_manager import QueueManager, QueueStore  # noqa: E402


SOUND_LABELS = {
    "NATURAL": "자연스러움",
    "RICH": "풍부함+",
}
QUALITY_MODES = {"FAST", "QUALITY+"}


def queue_channel_label(channel_key: str) -> str:
    return CHANNEL_PROFILES[normalize_channel_key(channel_key)].label


def queue_genre_label(genre_key: str) -> str:
    return GENRE_PROFILES[normalize_genre_key(genre_key)].label


def queue_sound_label(sound_mode: str) -> str:
    return SOUND_LABELS.get(str(sound_mode or "").upper(), str(sound_mode or ""))


def queue_quality_mode(quality_mode: str) -> str:
    mode = str(quality_mode or "QUALITY+").upper()
    return mode if mode in QUALITY_MODES else "QUALITY+"


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

        self.queue_channel_var = tk.StringVar(value=normalize_channel_key(self.channel_var.get()))
        self.queue_genre_var = tk.StringVar(value=normalize_genre_key(self.genre_var.get()))
        self.queue_sound_var = tk.StringVar(value=str(self.sound_var.get() or DEFAULT_SOUND_MODE).upper())
        self.queue_quality_var = tk.StringVar(value=queue_quality_mode(self.quality_var.get()))
        self.queue_settings_summary = tk.StringVar()

        controls = ttk.LabelFrame(self.queue_tab, text="대기열에 추가할 설정")
        controls.pack(fill="x", padx=14, pady=(14, 8))
        ttk.Label(controls, text="대기열 작업 설정", font=("Malgun Gothic", 9, "bold")).pack(
            anchor="w", padx=10, pady=(8, 2)
        )

        channel_grid = ttk.Frame(controls)
        channel_grid.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(channel_grid, text="채널:", width=8).grid(row=0, column=0, sticky="nw", padx=(0, 8), pady=4)
        for index, key in enumerate(CHANNEL_DISPLAY_ORDER):
            ttk.Radiobutton(
                channel_grid,
                text=CHANNEL_PROFILES[key].label,
                variable=self.queue_channel_var,
                value=key,
                command=self._update_queue_settings_summary,
            ).grid(row=index // 3, column=(index % 3) + 1, sticky="w", padx=8, pady=4)

        genre_row = ttk.Frame(controls)
        genre_row.pack(fill="x", padx=10, pady=4)
        ttk.Label(genre_row, text="장르:", width=8).pack(side="left", padx=(0, 8))
        genre_displays = [queue_genre_label(key) for key in GENRE_DISPLAY_ORDER]
        self._queue_genre_display_to_key = dict(zip(genre_displays, GENRE_DISPLAY_ORDER))
        self.queue_genre_display_var = tk.StringVar(value=queue_genre_label(self.queue_genre_var.get()))
        self.queue_genre_combo = ttk.Combobox(
            genre_row,
            textvariable=self.queue_genre_display_var,
            values=genre_displays,
            state="readonly",
            width=34,
        )
        self.queue_genre_combo.pack(side="left", fill="x", expand=True)
        self.queue_genre_combo.bind("<<ComboboxSelected>>", self._on_queue_genre_combo)

        sound_quality = ttk.Frame(controls)
        sound_quality.pack(fill="x", padx=10, pady=4)
        ttk.Label(sound_quality, text="사운드:", width=8).pack(side="left", padx=(0, 8))
        ttk.Radiobutton(
            sound_quality,
            text="자연스러움",
            variable=self.queue_sound_var,
            value="NATURAL",
            command=self._update_queue_settings_summary,
        ).pack(side="left", padx=(0, 18))
        ttk.Radiobutton(
            sound_quality,
            text="풍부함+",
            variable=self.queue_sound_var,
            value="RICH",
            command=self._update_queue_settings_summary,
        ).pack(side="left", padx=(0, 28))
        ttk.Label(sound_quality, text="품질:", width=6).pack(side="left", padx=(0, 8))
        ttk.Radiobutton(
            sound_quality,
            text="FAST",
            variable=self.queue_quality_var,
            value="FAST",
            command=self._update_queue_settings_summary,
        ).pack(side="left", padx=(0, 18))
        ttk.Radiobutton(
            sound_quality,
            text="QUALITY+",
            variable=self.queue_quality_var,
            value="QUALITY+",
            command=self._update_queue_settings_summary,
        ).pack(side="left")

        ttk.Label(controls, textvariable=self.queue_settings_summary, justify="left").pack(
            fill="x", padx=14, pady=(4, 8)
        )
        self._update_queue_settings_summary()

        top = ttk.Frame(controls)
        top.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(top, text="+ 작업 추가", command=self._queue_add_job).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="여러 폴더 추가", command=self._queue_add_root).pack(side="left", padx=6)
        ttk.Button(top, text="선택 작업 삭제", command=self._queue_remove_selected).pack(side="left", padx=6)
        ttk.Button(top, text="대기 작업 전체 삭제", command=self._queue_clear_waiting).pack(side="left", padx=6)
        ttk.Button(top, text="선택 작업 중지", command=self._queue_cancel_selected).pack(side="left", padx=6)
        ttk.Button(top, text="결과 폴더 열기", command=self._queue_open_result).pack(side="left", padx=6)

        settings = ttk.Frame(controls)
        settings.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(settings, text="동시 작업 수").pack(side="left", padx=(0, 8))
        self.queue_concurrency = tk.IntVar(value=1)
        ttk.Radiobutton(
            settings,
            text="1개",
            variable=self.queue_concurrency,
            value=1,
            command=self._queue_concurrency_changed,
        ).pack(side="left")
        ttk.Radiobutton(
            settings,
            text="2개",
            variable=self.queue_concurrency,
            value=2,
            command=self._queue_concurrency_changed,
        ).pack(side="left", padx=(8, 20))
        self.queue_sleep_prevention = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings,
            text="작업 중 PC 절전 방지",
            variable=self.queue_sleep_prevention,
            command=self._queue_sleep_changed,
        ).pack(side="left")

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
            "id": "작업 ID",
            "status": "상태",
            "folder": "폴더",
            "channel": "채널",
            "genre": "장르",
            "sound": "사운드",
            "quality": "품질",
            "progress": "진행",
            "pid": "PID",
            "result": "결과",
        }
        widths = {
            "id": 180,
            "status": 130,
            "folder": 180,
            "channel": 170,
            "genre": 120,
            "sound": 80,
            "quality": 85,
            "progress": 75,
            "pid": 75,
            "result": 170,
        }
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

    def _on_queue_genre_combo(self, _event=None) -> None:
        display = self.queue_genre_display_var.get()
        key = self._queue_genre_display_to_key.get(display)
        if key:
            self.queue_genre_var.set(key)
            self._update_queue_settings_summary()

    def _queue_settings_payload(self) -> dict[str, str]:
        return {
            "channel_key": normalize_channel_key(self.queue_channel_var.get()),
            "genre_key": normalize_genre_key(self.queue_genre_var.get()),
            "sound_mode": str(self.queue_sound_var.get() or DEFAULT_SOUND_MODE).upper(),
            "quality_mode": queue_quality_mode(self.queue_quality_var.get()),
        }

    def _queue_settings_labels(self) -> dict[str, str]:
        payload = self._queue_settings_payload()
        return {
            "channel": queue_channel_label(payload["channel_key"]),
            "genre": queue_genre_label(payload["genre_key"]),
            "sound": queue_sound_label(payload["sound_mode"]),
            "quality": payload["quality_mode"],
        }

    def _update_queue_settings_summary(self) -> None:
        if hasattr(self, "queue_genre_display_var"):
            self.queue_genre_display_var.set(queue_genre_label(self.queue_genre_var.get()))
        labels = self._queue_settings_labels()
        self.queue_settings_summary.set(
            "현재 Queue 설정으로 추가됩니다:\n"
            f"채널: {labels['channel']} / 장르: {labels['genre']} / "
            f"사운드: {labels['sound']} / 품질: {labels['quality']}"
        )

    def _confirm_add_queue_folders(self, folders: list[Path]) -> bool:
        labels = self._queue_settings_labels()
        folder_lines = "\n".join(f"- {folder.name}" for folder in folders[:10])
        if len(folders) > 10:
            folder_lines += f"\n... 외 {len(folders) - 10}개"
        scope = (
            "선택된 모든 폴더에 현재 Queue 설정 한 세트를 적용합니다."
            if len(folders) > 1
            else "선택한 폴더에 현재 Queue 설정을 적용합니다."
        )
        message = (
            f"{scope}\n\n"
            f"폴더:\n{folder_lines}\n\n"
            f"채널: {labels['channel']}\n"
            f"장르: {labels['genre']}\n"
            f"사운드: {labels['sound']}\n"
            f"품질: {labels['quality']}"
        )
        return bool(v39.legacy.messagebox.askokcancel("대기열에 추가", message))

    def _queue_add_job(self):
        folder = v39.legacy.filedialog.askdirectory(title="마스터링 작업 폴더 선택")
        if not folder:
            return
        folders = [Path(folder)]
        if self._confirm_add_queue_folders(folders):
            job = self._add_queue_folder(folders[0])
            if job:
                self.queue_status.set("1개 작업을 대기열에 추가했습니다.")

    def _queue_add_root(self):
        root = v39.legacy.filedialog.askdirectory(title="여러 앨범 상위 폴더 선택")
        if not root:
            return
        folders = [
            path
            for path in Path(root).iterdir()
            if path.is_dir()
            and any(item.suffix.lower() in {".wav", ".wave"} for item in path.iterdir() if item.is_file())
        ]
        folders = sorted(folders, key=lambda path: path.name.lower())
        if not folders:
            v39.legacy.messagebox.showinfo("대기열에 추가", "WAV 파일이 있는 하위 폴더를 찾지 못했습니다.")
            return
        if not self._confirm_add_queue_folders(folders):
            return
        added = 0
        for folder in folders:
            if self._add_queue_folder(folder, show_errors=False):
                added += 1
        self.queue_status.set(f"{added}개 작업을 대기열에 추가했습니다.")
        self._refresh_queue_tree()

    def _add_queue_folder(self, folder: Path, *, show_errors: bool = True):
        try:
            settings = self._queue_settings_payload()
            job = self.queue_manager.add_job(
                folder,
                channel_key=settings["channel_key"],
                genre_key=settings["genre_key"],
                sound_mode=settings["sound_mode"],
                quality_mode=settings["quality_mode"],
            )
        except (ValueError, OSError) as exc:
            if show_errors:
                v39.legacy.messagebox.showwarning("작업을 추가할 수 없음", str(exc))
            return None
        self._refresh_queue_tree()
        return job

    def _queue_remove_selected(self):
        selection = self.queue_tree.selection()
        if not selection:
            v39.legacy.messagebox.showinfo("선택 작업 삭제", "삭제할 작업을 먼저 선택하세요.")
            return
        removed = 0
        running_selected = False
        for job_id in selection:
            job = next((job for job in self.queue_manager.jobs if job.job_id == job_id), None)
            if not job:
                continue
            if job.status == "RUNNING":
                running_selected = True
                continue
            if self.queue_manager.remove(job.job_id):
                removed += 1
        if running_selected:
            v39.legacy.messagebox.showwarning("선택 작업 삭제", "현재 실행 중인 작업입니다.\n먼저 작업을 중지하세요.")
        if removed:
            self.queue_status.set(f"{removed}개 작업을 대기열에서 삭제했습니다.")
        elif not running_selected:
            self.queue_status.set("삭제할 수 있는 선택 작업이 없습니다.")
        self._refresh_queue_tree()

    def _queue_clear_waiting(self):
        waiting_count = len([job for job in self.queue_manager.jobs if job.status == "WAITING"])
        if waiting_count <= 0:
            v39.legacy.messagebox.showinfo("대기 작업 전체 삭제", "삭제할 대기 중인 작업이 없습니다.")
            return
        if not v39.legacy.messagebox.askokcancel(
            "대기 작업 전체 삭제",
            f"대기 중인 작업 {waiting_count}개를 모두 삭제하시겠습니까?",
        ):
            return
        removed = self.queue_manager.remove_waiting_jobs()
        self.queue_status.set(f"{removed}개 대기 작업을 삭제했습니다.")
        self._refresh_queue_tree()

    def _queue_cancel_selected(self):
        selection = self.queue_tree.selection()
        if not selection:
            v39.legacy.messagebox.showinfo("선택 작업 중지", "중지할 실행 중 작업을 먼저 선택하세요.")
            return
        cancelled = 0
        for job_id in selection:
            job = next((job for job in self.queue_manager.jobs if job.job_id == job_id), None)
            if job and job.status == "RUNNING" and self.queue_manager.cancel_job(job.job_id):
                cancelled += 1
        if cancelled:
            self.queue_status.set(f"{cancelled}개 실행 중 작업을 중지했습니다.")
        else:
            v39.legacy.messagebox.showinfo("선택 작업 중지", "RUNNING 상태의 작업을 선택하세요.")
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
        job = next((job for job in self.queue_manager.jobs if job.job_id == selection[0]), None)
        if job and job.output_dir and Path(job.output_dir).exists() and os.name == "nt":
            os.startfile(job.output_dir)

    def _queue_tree_values(self, job):
        result = ""
        if job.status == "COMPLETED":
            result = "완료"
        elif job.status == "COMPLETED_WITH_REVIEW":
            result = "검토 필요"
        elif job.validation_warning:
            result = job.validation_warning
        elif job.error_message:
            result = job.error_message[:32]
        return (
            job.job_id,
            job.status,
            Path(job.folder).name,
            queue_channel_label(job.channel_key),
            queue_genre_label(job.genre_key),
            queue_sound_label(job.sound_mode),
            queue_quality_mode(job.quality_mode),
            f"{job.current_track}/{job.total_tracks}",
            job.process_id or "",
            result,
        )

    def _refresh_queue_tree(self):
        if not hasattr(self, "queue_tree"):
            return
        selected = [job_id for job_id in self.queue_tree.selection()]
        try:
            yview = self.queue_tree.yview()[0]
        except Exception:
            yview = None

        job_ids = [job.job_id for job in self.queue_manager.jobs]
        current_ids = set(job_ids)
        tree_ids = set(self.queue_tree.get_children())
        for stale_id in tree_ids - current_ids:
            self.queue_tree.delete(stale_id)

        for index, job in enumerate(self.queue_manager.jobs):
            values = self._queue_tree_values(job)
            if self.queue_tree.exists(job.job_id):
                self.queue_tree.item(job.job_id, values=values)
            else:
                self.queue_tree.insert("", "end", iid=job.job_id, values=values)
            self.queue_tree.move(job.job_id, "", index)

        keep_selected = [job_id for job_id in selected if job_id in current_ids]
        if keep_selected:
            self.queue_tree.selection_set(*keep_selected)
        if yview is not None:
            try:
                self.queue_tree.yview_moveto(yview)
            except Exception:
                pass

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
