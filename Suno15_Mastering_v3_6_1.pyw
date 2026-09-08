# -*- coding: utf-8 -*-
"""HARU Mastering v3.6.1 - final metrics sync and Tail INFO guard."""
from __future__ import annotations

import csv
import json
import math
import shutil
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V36_PATH = ROOT / "Suno15_Mastering_v3_6.pyw"


def _load_v36():
    loader = SourceFileLoader("suno15_v36", str(V36_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.6 프로그램을 불러올 수 없습니다: {V36_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v36 = _load_v36()

from haru_mastering.analysis import analyze_file


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.6.1 - FINAL METRICS SYNC"
_COMPLETION_SENTENCES = tuple(
    f"모든 곡이 v{version} 자동검사와 자동수정을 통과했습니다."
    for version in ("3.2", "3.3", "3.4", "3.5", "3.6")
)
_COMPLETION_V361 = "모든 곡이 v3.6.1 자동검사와 자동수정을 통과했습니다."


def _upgrade_completion_text(text: str) -> str:
    updated = str(text)
    for sentence in _COMPLETION_SENTENCES:
        updated = updated.replace(sentence, _COMPLETION_V361)
    return updated


def _refresh_completion_text_files(output_dir: str | Path) -> int:
    output = Path(output_dir)
    changed = 0
    seen: set[Path] = set()
    for pattern in ("자동해결_결과*.txt", "STUDIO_문제곡_보완_프롬프트*.txt"):
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


def _format_metric(value: float) -> str:
    return f"{value:.2f}" if math.isfinite(value) else "-inf"


def _load_tail_notes(output: Path) -> dict[str, str]:
    json_path = output / "HARU_QUALITY_GATE.json"
    if not json_path.exists():
        return {}
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    notes: dict[str, str] = {}
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            track = str(item.get("track") or "").strip()
            note = str(item.get("tail_note") or "").strip()
            if track and note:
                notes[track] = note
    return notes


def _refresh_final_metrics_csv(output_dir: str | Path) -> int:
    """Synchronize CSV loudness, peak, LRA and Tail metadata with final MASTER WAVs."""
    output = Path(output_dir)
    csv_path = output / "mastering_report.csv"
    if not csv_path.exists():
        return 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    additions = (
        "final_sample_peak_dbfs",
        "final_rms_dbfs",
        "final_crest_factor_db",
        "final_metrics_source",
        "tail_info_note",
    )
    for name in additions:
        if name not in fieldnames:
            fieldnames.append(name)

    tail_notes = _load_tail_notes(output)
    refreshed = 0
    for row in rows:
        track = (row.get("track") or "").strip()
        if not track:
            continue
        master_path = output / f"{Path(track).stem}_MASTER.wav"
        if not master_path.exists():
            continue

        metrics = analyze_file(master_path)
        if "final_LUFS" in row:
            row["final_LUFS"] = _format_metric(metrics.lufs_i)
        if "final_dBTP" in row:
            row["final_dBTP"] = _format_metric(metrics.true_peak_dbtp)
        if "final_LRA" in row:
            row["final_LRA"] = _format_metric(metrics.lra_lu)

        row["final_sample_peak_dbfs"] = _format_metric(metrics.sample_peak_dbfs)
        row["final_rms_dbfs"] = _format_metric(metrics.rms_dbfs)
        row["final_crest_factor_db"] = _format_metric(metrics.crest_factor_db)
        row["final_metrics_source"] = "final_master_after_all_postprocessing"
        row["tail_info_note"] = tail_notes.get(track, "")
        refreshed += 1

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report_copy = output / "03_REPORT" / csv_path.name
    report_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(csv_path, report_copy)
    return refreshed


class AppV361(v36.AppV36):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set(
            "v3.6.1 자동완성 준비 — 최종 LUFS·dBTP·LRA·Tail 보고서를 실제 WAV와 일치시킵니다."
        )
        previous_showinfo = v36.v35.v34.v33.v32.legacy.messagebox.showinfo

        def versioned_showinfo(title, message):
            text = str(title)
            for version in ("v3.6", "v3.5", "v3.4", "v3.3", "v3.2"):
                text = text.replace(version, "v3.6.1")
            return previous_showinfo(text, message)

        v36.v35.v34.v33.v32.legacy.messagebox.showinfo = versioned_showinfo

    def append_log(self, text):
        value = str(text)
        for version in ("v3.6", "v3.5", "v3.4", "v3.3", "v3.2"):
            value = value.replace(version, "v3.6.1")
        return super().append_log(value)

    def _worker(self, folder, files):
        super()._worker(folder, files)
        output_dir = Path(self.last_output_dir)
        refreshed = _refresh_final_metrics_csv(output_dir)
        text_files = _refresh_completion_text_files(output_dir)
        self._refresh_beginner_summary(output_dir)
        self.after(
            0,
            self.append_log,
            f"v3.6.1 최종 수치 동기화 완료: {refreshed}곡 / 안내문 {text_files}개",
        )


if __name__ == "__main__":
    AppV361().mainloop()
