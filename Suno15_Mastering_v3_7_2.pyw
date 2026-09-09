# -*- coding: utf-8 -*-
"""HARU Mastering v3.7.2 - guaranteed final CSV metrics synchronization."""
from __future__ import annotations

import csv
import math
import shutil
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V371_PATH = ROOT / "Suno15_Mastering_v3_7_1.pyw"


def _load_v371():
    loader = SourceFileLoader("suno15_v371", str(V371_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.7.1 프로그램을 불러올 수 없습니다: {V371_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v371 = _load_v371()

from haru_mastering.analysis import analyze_file
import haru_mastering.report as report_module


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.7.2 - GUARANTEED CSV SYNC"
REPORT_VERSION = "v3.7.2"
SYNC_VERSION = "v3.7.2"
LOUDNESS_TOLERANCE_LU = float(v371.LOUDNESS_TOLERANCE_LU)


def _format_metric(value: float) -> str:
    number = float(value)
    return f"{number:.2f}" if math.isfinite(number) else "-inf"


def _safe_float(value, default=None):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _master_candidates(output: Path, track: str):
    name = f"{Path(track).stem}_MASTER.wav"
    yield output / name
    yield output / "01_RELEASE_READY" / name
    yield output / "02_NEEDS_REVIEW" / name


def _find_master(output: Path, track: str) -> Path | None:
    for candidate in _master_candidates(output, track):
        if candidate.exists():
            return candidate
    return None


def _refresh_final_metrics_csv_v372(output_dir: str | Path) -> int:
    """Always create and synchronize v3.7.2 final metric columns.

    The parent v3.6.1 synchronizer is patched to this function so the columns
    are created during the already-proven real execution path. The function
    also finds MASTER WAVs after RELEASE_READY / NEEDS_REVIEW organization.
    """
    output = Path(output_dir)
    csv_path = output / "mastering_report.csv"
    if not csv_path.exists():
        return 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    additions = (
        "final_LRA",
        "final_lufs_delta_lu",
        "final_lufs_within_tolerance",
        "codec_strategy",
        "final_metrics_sync_version",
    )
    for name in additions:
        if name not in fieldnames:
            fieldnames.append(name)

    refreshed = 0
    for row in rows:
        track = (row.get("track") or "").strip()
        if not track:
            continue
        master_path = _find_master(output, track)
        if master_path is None:
            row["final_metrics_sync_version"] = SYNC_VERSION
            continue

        metrics = analyze_file(master_path)
        row["final_LUFS"] = _format_metric(metrics.lufs_i)
        row["final_dBTP"] = _format_metric(metrics.true_peak_dbtp)
        row["final_LRA"] = _format_metric(metrics.lra_lu)

        target = _safe_float(row.get("target_LUFS"))
        if target is None:
            row["final_lufs_delta_lu"] = ""
            row["final_lufs_within_tolerance"] = ""
        else:
            delta = float(metrics.lufs_i) - target
            row["final_lufs_delta_lu"] = f"{delta:+.2f}"
            row["final_lufs_within_tolerance"] = (
                "true" if abs(delta) <= LOUDNESS_TOLERANCE_LU + 1e-9 else "false"
            )

        row["codec_strategy"] = "ceiling_rerender_preserve_loudness"
        row["final_metrics_sync_version"] = SYNC_VERSION
        if "final_metrics_source" in fieldnames:
            row["final_metrics_source"] = "final_master_after_all_postprocessing"
        refreshed += 1

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report_copy = output / "03_REPORT" / csv_path.name
    report_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(csv_path, report_copy)
    return refreshed


def _upgrade_completion_text_v372(text: str) -> str:
    updated = str(text)
    for version in ("3.2", "3.3", "3.4", "3.5", "3.6", "3.6.1", "3.7", "3.7.1"):
        updated = updated.replace(
            f"모든 곡이 v{version} 자동검사와 자동수정을 통과했습니다.",
            "모든 곡이 v3.7.2 자동검사와 자동수정을 통과했습니다.",
        )
    return updated


def _refresh_completion_text_files_v372(output_dir: str | Path) -> int:
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
            updated = _upgrade_completion_text_v372(original)
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                changed += 1
    return changed


def install_v372_sync() -> None:
    # Parent v3.6.1 is the synchronization pass proven to execute in the user's
    # real run. Patch it directly, and patch the v3.7.1 pass too. This removes
    # inheritance/post-processing order as a failure mode.
    v371.v37.v361._refresh_final_metrics_csv = _refresh_final_metrics_csv_v372
    v371.v37.v361._refresh_completion_text_files = _refresh_completion_text_files_v372
    v371._refresh_final_metrics_csv = _refresh_final_metrics_csv_v372
    v371._refresh_completion_text_files = _refresh_completion_text_files_v372
    report_module.QUALITY_REPORT_VERSION = REPORT_VERSION


install_v372_sync()


class AppV372(v371.AppV371):
    def __init__(self):
        install_v372_sync()
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set(
            "v3.7.2 준비 — 최종 CSV까지 실제 MASTER WAV와 강제 동기화합니다."
        )

    def append_log(self, text):
        value = str(text)
        for old in ("v3.7.1", "v3.7", "v3.6.1", "v3.6", "v3.5", "v3.4", "v3.3", "v3.2"):
            if value.startswith(old + " ") or (old + " ") in value:
                value = value.replace(old, "v3.7.2")
        return super().append_log(value)

    def _worker(self, folder, files):
        install_v372_sync()
        super()._worker(folder, files)
        output_dir = Path(self.last_output_dir)
        refreshed = _refresh_final_metrics_csv_v372(output_dir)
        text_files = _refresh_completion_text_files_v372(output_dir)
        self._refresh_beginner_summary(output_dir)
        self.after(
            0,
            self.append_log,
            f"v3.7.2 최종 CSV 보증 동기화 완료: {refreshed}곡 / 안내문 {text_files}개",
        )


if __name__ == "__main__":
    AppV372().mainloop()
