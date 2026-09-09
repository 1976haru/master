# -*- coding: utf-8 -*-
"""HARU Mastering v3.6 - final WAV report synchronization."""
from __future__ import annotations

import csv
import math
import shutil
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V35_PATH = ROOT / "Suno15_Mastering_v3_5.pyw"


def _load_v35():
    loader = SourceFileLoader("suno15_v35", str(V35_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.5 프로그램을 불러올 수 없습니다: {V35_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v35 = _load_v35()

from haru_mastering.auto_finish import inspect_tail


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.6 - FINAL REPORT SYNC"
_COMPLETION_SENTENCES = tuple(
    f"모든 곡이 v{version} 자동검사와 자동수정을 통과했습니다."
    for version in ("3.2", "3.3", "3.4", "3.5")
)
_COMPLETION_V36 = "모든 곡이 v3.6 자동검사와 자동수정을 통과했습니다."


def _upgrade_completion_text(text: str) -> str:
    updated = str(text)
    for sentence in _COMPLETION_SENTENCES:
        updated = updated.replace(sentence, _COMPLETION_V36)
    return updated


def _format_db(value: float) -> str:
    return f"{value:.2f}" if math.isfinite(value) else "-inf"


def _refresh_completion_text_files(output_dir: str | Path) -> int:
    output = Path(output_dir)
    patterns = (
        "자동해결_결과*.txt",
        "STUDIO_문제곡_보완_프롬프트*.txt",
    )
    changed = 0
    seen: set[Path] = set()
    for pattern in patterns:
        for path in output.rglob(pattern):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            try:
                original = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                original = path.read_text(encoding="utf-8-sig")
            updated = _upgrade_completion_text(original)
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                changed += 1
    return changed


def _refresh_final_tail_csv(output_dir: str | Path) -> int:
    """Synchronize CSV Tail fields with the actual final WAV after codec gain."""
    output = Path(output_dir)
    csv_path = output / "mastering_report.csv"
    if not csv_path.exists():
        return 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    additions = (
        "tail_final_rms_dbfs",
        "tail_final_last_sample_dbfs",
        "tail_final_hard_cut",
        "tail_final_energetic_end",
        "tail_metrics_source",
    )
    for name in additions:
        if name not in fieldnames:
            fieldnames.append(name)

    refreshed = 0
    for row in rows:
        track = (row.get("track") or "").strip()
        if not track:
            continue
        master_path = output / f"{Path(track).stem}_MASTER.wav"
        if not master_path.exists():
            continue

        metrics = inspect_tail(
            master_path,
            window_ms=100.0,
            end_rms_threshold_dbfs=-50.0,
            last_sample_threshold_dbfs=-60.0,
            energetic_end_threshold_dbfs=-35.0,
        )
        final_rms = _format_db(metrics.end_rms_dbfs)
        final_last = _format_db(metrics.last_sample_dbfs)

        if "tail_after_RMS" in row:
            row["tail_after_RMS"] = final_rms
        if "tail_after_rms_dbfs" in row:
            row["tail_after_rms_dbfs"] = final_rms

        row["tail_final_rms_dbfs"] = final_rms
        row["tail_final_last_sample_dbfs"] = final_last
        row["tail_final_hard_cut"] = "true" if metrics.hard_cut else "false"
        row["tail_final_energetic_end"] = "true" if metrics.energetic_end else "false"
        row["tail_metrics_source"] = "final_master_after_codec"
        refreshed += 1

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report_copy = output / "03_REPORT" / csv_path.name
    report_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(csv_path, report_copy)
    return refreshed


class AppV36(v35.AppV35):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set(
            "v3.6 자동완성 준비 — 최종 WAV와 HTML·JSON·CSV·안내문을 일치시킵니다."
        )
        base_showinfo = v35.v34.v33.v32.legacy.messagebox.showinfo

        def versioned_showinfo(title, message):
            text = str(title)
            for version in ("v3.5", "v3.4", "v3.3", "v3.2"):
                text = text.replace(version, "v3.6")
            return base_showinfo(text, message)

        v35.v34.v33.v32.legacy.messagebox.showinfo = versioned_showinfo

    def append_log(self, text):
        value = str(text)
        for version in ("v3.5", "v3.4", "v3.3", "v3.2"):
            value = value.replace(version, "v3.6")
        return super().append_log(value)

    def _worker(self, folder, files):
        super()._worker(folder, files)
        output_dir = Path(self.last_output_dir)
        refreshed = _refresh_final_tail_csv(output_dir)
        text_files = _refresh_completion_text_files(output_dir)
        self._refresh_beginner_summary(output_dir)
        self.after(
            0,
            self.append_log,
            f"v3.6 최종 보고서 동기화 완료: Tail {refreshed}곡 / 안내문 {text_files}개",
        )


if __name__ == "__main__":
    AppV36().mainloop()
