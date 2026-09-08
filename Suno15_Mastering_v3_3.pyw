# -*- coding: utf-8 -*-
"""HARU Mastering v3.3 - measured codec auto-gain edition."""
from __future__ import annotations

import csv
import shutil
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V32_PATH = ROOT / "Suno15_Mastering_v3_1.pyw"


def _load_v32():
    loader = SourceFileLoader("suno15_v32", str(V32_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.2 프로그램을 불러올 수 없습니다: {V32_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v32 = _load_v32()

from haru_mastering.codec_auto_gain import (
    CodecAutoGainResult,
    ensure_codec_safety_with_auto_gain,
)


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.3 - CODEC AUTO GAIN"
_BASE_CODEC_CHECK = v32.check_codec_safety
_CODEC_RESULTS: dict[str, CodecAutoGainResult] = {}


def _codec_settings() -> dict:
    payload = v32.v3._profile_payload()
    return payload["global"].get("autoFinish", {})


def _codec_check_with_auto_gain(
    source_path,
    *,
    true_peak_ceiling_dbtp,
    tolerance_db=0.05,
    ffmpeg=None,
):
    auto = _codec_settings()
    outcome = ensure_codec_safety_with_auto_gain(
        source_path,
        checker=_BASE_CODEC_CHECK,
        true_peak_ceiling_dbtp=float(true_peak_ceiling_dbtp),
        tolerance_db=float(tolerance_db),
        ffmpeg=ffmpeg,
        maximum_passes=int(auto.get("codecMaximumAutoGainPasses", 3)),
        safety_margin_db=float(auto.get("codecPostGainSafetyMarginDb", 0.10)),
        minimum_step_db=float(auto.get("codecMinimumGainStepDb", 0.05)),
        maximum_single_reduction_db=float(auto.get("codecMaximumSingleGainReductionDb", 1.50)),
        maximum_total_reduction_db=float(auto.get("codecMaximumTotalGainReductionDb", 2.00)),
    )
    _CODEC_RESULTS[str(Path(source_path).resolve())] = outcome
    return outcome.safety


def _accurate_limit_text(track: str, issues: list[str], genre_label: str) -> str:
    codec_only = bool(issues) and all(issue.startswith("codec") for issue in issues)
    lines = [
        "=" * 72,
        f"자동 해결 한도 초과: {track}",
        f"장르: {genre_label}",
        "",
        "프로그램이 이 문제에 필요한 자동수정을 모두 시도했습니다.",
        "사용자가 EQ·컴프레서·Stem을 수동으로 조정할 필요는 없습니다.",
        "",
        "남은 문제:",
    ]
    lines.extend(f"- {issue}" for issue in issues)
    lines += ["", "권장 조치:", "- 이 파일은 02_NEEDS_REVIEW에 자동 분리됩니다."]
    if codec_only:
        lines += [
            "- WAV 자체의 손상보다 AAC/MP3 변환 피크가 자동감쇠 한도를 넘은 경우입니다.",
            "- 곡을 재생성하거나 편곡을 바꾸지 말고, 이 파일만 다음 자동 마스터링에서 다시 처리하세요.",
        ]
    else:
        lines += [
            "- 원본 WAV를 Full Song WAV로 다시 Export해 보세요.",
            "- 동일하면 해당 곡만 Suno에서 재생성한 뒤 다시 자동 마스터링하세요.",
        ]
    lines.append("- 01_RELEASE_READY의 다른 곡은 그대로 사용해도 됩니다.")
    return "\n".join(lines)


v32.check_codec_safety = _codec_check_with_auto_gain
v32._automatic_limit_text = _accurate_limit_text


class AppV33(v32.AppV31):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set("v3.3 자동완성 준비 — 코덱 피크도 필요한 만큼 자동 감쇠합니다.")
        base_showinfo = v32.legacy.messagebox.showinfo

        def versioned_showinfo(title, message):
            return base_showinfo(str(title).replace("v3.2", "v3.3"), message)

        v32.legacy.messagebox.showinfo = versioned_showinfo

    def append_log(self, text):
        return super().append_log(str(text).replace("v3.2", "v3.3"))

    def _patch_csv_with_codec_gain(self, output_dir: Path) -> int:
        csv_path = output_dir / "mastering_report.csv"
        if not csv_path.exists():
            return 0

        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = list(reader.fieldnames or [])

        for name in ("codec_gain_reduction_dB", "codec_auto_gain_passes"):
            if name not in fieldnames:
                fieldnames.append(name)

        fixed_count = 0
        for row in rows:
            track = row.get("track", "")
            master_path = output_dir / f"{Path(track).stem}_MASTER.wav"
            outcome = _CODEC_RESULTS.get(str(master_path.resolve()))
            reduction = outcome.total_gain_reduction_db if outcome is not None else 0.0
            passes = outcome.passes if outcome is not None else 0
            row["codec_gain_reduction_dB"] = f"{reduction:.2f}"
            row["codec_auto_gain_passes"] = str(passes)
            if reduction > 0.0:
                fixed_count += 1
                label = f"코덱 자동 감쇠(-{reduction:.2f}dB)"
                existing = (row.get("auto_fixes") or "").strip()
                if label not in existing:
                    row["auto_fixes"] = f"{existing} / {label}".strip(" /")
                processing = (row.get("processing_mode") or "normal").strip()
                if "codec_gain" not in processing:
                    row["processing_mode"] = processing + "+codec_gain"

        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        report_copy = output_dir / "03_REPORT" / csv_path.name
        report_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_path, report_copy)
        return fixed_count

    def _refresh_beginner_summary(self, output_dir: Path) -> None:
        summary = output_dir / "03_REPORT" / "초보자_최종판정.txt"
        csv_path = output_dir / "mastering_report.csv"
        if not summary.exists() or not csv_path.exists():
            return
        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        auto_fixed = sum(bool((row.get("auto_fixes") or "").strip()) for row in rows)
        text = summary.read_text(encoding="utf-8")
        lines = []
        for line in text.splitlines():
            if line.startswith("자동 수정 완료:"):
                line = f"자동 수정 완료: {auto_fixed}"
            lines.append(line)
        summary.write_text("\n".join(lines), encoding="utf-8")

    def _worker(self, folder, files):
        _CODEC_RESULTS.clear()
        super()._worker(folder, files)
        output_dir = Path(self.last_output_dir)
        codec_fixed = self._patch_csv_with_codec_gain(output_dir)
        self._refresh_beginner_summary(output_dir)
        if codec_fixed:
            self.after(
                0,
                self.append_log,
                f"v3.3 코덱 자동감쇠 완료: {codec_fixed}곡 — 재생성 없이 안전 피크 확보",
            )


if __name__ == "__main__":
    AppV33().mainloop()
