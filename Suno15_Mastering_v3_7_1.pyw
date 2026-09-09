# -*- coding: utf-8 -*-
"""HARU Mastering v3.7.1 - loudness-preserving codec safety and final CSV sync."""
from __future__ import annotations

import copy
import csv
import math
import re
import shutil
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V37_PATH = ROOT / "Suno15_Mastering_v3_7.pyw"


def _load_v37():
    loader = SourceFileLoader("suno15_v37", str(V37_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.7 프로그램을 불러올 수 없습니다: {V37_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v37 = _load_v37()

from haru_mastering.analysis import analyze_file
import haru_mastering.report as report_module


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.7.1 - LOUDNESS SAFE CODEC"
REPORT_VERSION = "v3.7.1"
LOUDNESS_TOLERANCE_LU = 0.20
CODEC_CEILING_STEP_DB = 0.50
CODEC_MAXIMUM_RERENDERS = 4

# v3.3 patched the v3.2 codec checker so the very first codec check could
# attenuate the already mastered WAV. That made a codec-safe file but could
# move -14 LUFS material to roughly -15.5 LUFS. v3.7.1 restores the original
# read-only checker so the existing v3.2 Stage 3 can first re-render from the
# source with a lower true-peak ceiling while preserving the loudness target.
_RAW_CODEC_CHECK = v37.v361.v36.v35.v34.v33._BASE_CODEC_CHECK
_ORIGINAL_PROFILE_PAYLOAD = v37.v32.v3._profile_payload


def _runtime_profile_payload():
    payload = copy.deepcopy(_ORIGINAL_PROFILE_PAYLOAD())
    auto = payload["global"].setdefault("autoFinish", {})
    auto["maximumAutoRerenders"] = max(
        CODEC_MAXIMUM_RERENDERS,
        int(auto.get("maximumAutoRerenders", 0)),
    )
    auto["codecCeilingStepDb"] = CODEC_CEILING_STEP_DB
    return payload


def install_loudness_preserving_codec_strategy() -> None:
    v37.v32.v3._profile_payload = _runtime_profile_payload
    v37.v32.check_codec_safety = _RAW_CODEC_CHECK
    report_module.QUALITY_REPORT_VERSION = REPORT_VERSION


install_loudness_preserving_codec_strategy()


_COMPLETION_SENTENCES = tuple(
    f"모든 곡이 v{version} 자동검사와 자동수정을 통과했습니다."
    for version in ("3.2", "3.3", "3.4", "3.5", "3.6", "3.6.1", "3.7")
)
_COMPLETION_V371 = "모든 곡이 v3.7.1 자동검사와 자동수정을 통과했습니다."
_VERSION_PATTERN = re.compile(r"v3\.(?:7\.1|7|6\.1|6|5|4|3|2)(?![\d.])")


def _normalize_version_text(text: str) -> str:
    return _VERSION_PATTERN.sub("v3.7.1", str(text))


def _upgrade_completion_text(text: str) -> str:
    updated = str(text)
    for sentence in _COMPLETION_SENTENCES:
        updated = updated.replace(sentence, _COMPLETION_V371)
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
    return f"{float(value):.2f}" if math.isfinite(float(value)) else "-inf"


def _safe_float(value, default=None):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _refresh_final_metrics_csv(output_dir: str | Path) -> int:
    """Synchronize final LUFS/dBTP/LRA with the actual release candidate WAV."""
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


class AppV371(v37.AppV37):
    def __init__(self):
        install_loudness_preserving_codec_strategy()
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set(
            "v3.7.1 준비 — 코덱 피크는 ceiling 재렌더로 잡고 목표 LUFS를 끝까지 지킵니다."
        )
        previous_showinfo = v37.legacy.messagebox.showinfo

        def versioned_showinfo(title, message):
            return previous_showinfo(_normalize_version_text(title), message)

        v37.legacy.messagebox.showinfo = versioned_showinfo

    def append_log(self, text):
        return super().append_log(_normalize_version_text(text))

    def _worker(self, folder, files):
        install_loudness_preserving_codec_strategy()
        super()._worker(folder, files)
        output_dir = Path(self.last_output_dir)
        refreshed = _refresh_final_metrics_csv(output_dir)
        text_files = _refresh_completion_text_files(output_dir)
        self._refresh_beginner_summary(output_dir)
        self.after(
            0,
            self.append_log,
            f"v3.7.1 최종 동기화 완료: LUFS·dBTP·LRA {refreshed}곡 / 안내문 {text_files}개",
        )


if __name__ == "__main__":
    AppV371().mainloop()
