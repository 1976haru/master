# -*- coding: utf-8 -*-
"""HARU Mastering v3.4 - confidence-based delay guard and auto alignment."""
from __future__ import annotations

import csv
import shutil
from dataclasses import replace
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V33_PATH = ROOT / "Suno15_Mastering_v3_3.pyw"


def _load_v33():
    loader = SourceFileLoader("suno15_v33", str(V33_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.3 프로그램을 불러올 수 없습니다: {V33_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v33 = _load_v33()

from haru_mastering.alignment import align_audio_file
from haru_mastering.auto_finish import repair_tail_automatically
from haru_mastering.quality_gate import evaluate_master as _CORE_EVALUATE


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.4 - SMART DELAY GUARD"
_DELAY_RESULTS: dict[str, object] = {}
_ALIGNMENT_RESULTS: dict[str, tuple[int, int]] = {}
_BASE_SETTINGS = v33.v32._settings


def _delay_config() -> dict:
    payload = v33.v32.v3._profile_payload()
    return payload["global"].get("autoFinish", {})


def _settings_v34(genre_key: str):
    kwargs, auto, profile = _BASE_SETTINGS(genre_key)
    kwargs.update(
        {
            "delay_information_limit_samples": int(auto.get("delayInformationLimitSamples", 8)),
            "delay_warning_limit_samples": int(auto.get("delayWarningLimitSamples", 47)),
            "delay_minimum_confidence": float(auto.get("delayMinimumConfidence", 0.70)),
            "delay_window_count": int(auto.get("delayWindowCount", 5)),
            "delay_window_seconds": float(auto.get("delayWindowSeconds", 6.0)),
            "delay_consistency_tolerance_samples": int(
                auto.get("delayConsistencyToleranceSamples", 3)
            ),
        }
    )
    return kwargs, auto, profile


def _repair_tail_after_alignment(path: Path, auto: dict) -> None:
    repair_tail_automatically(
        path,
        window_ms=float(auto.get("tailWindowMs", 100.0)),
        end_rms_threshold_dbfs=float(auto.get("tailEndRmsThresholdDbfs", -50.0)),
        last_sample_threshold_dbfs=float(auto.get("tailLastSampleThresholdDbfs", -60.0)),
        energetic_end_threshold_dbfs=float(auto.get("energeticTailThresholdDbfs", -35.0)),
        energetic_fade_ms=float(auto.get("energeticTailFadeMs", 400.0)),
        hard_cut_fade_ms=float(auto.get("hardCutAutoFadeMs", 25.0)),
        micro_fade_ms=float(auto.get("microFadeMs", 5.0)),
        micro_fade_last_sample_threshold_dbfs=float(
            auto.get("microFadeLastSampleThresholdDbfs", -80.0)
        ),
    )


def _evaluate_with_smart_delay(source_path, processed_path, **kwargs):
    auto = _delay_config()
    result = _CORE_EVALUATE(source_path, processed_path, **kwargs)
    key = str(Path(processed_path).resolve())
    _DELAY_RESULTS[key] = result

    delay = result.residual_delay_samples
    minimum_align = int(auto.get("delayAutomaticAlignmentMinimumSamples", 48))
    maximum_align = int(auto.get("delayMaximumAutomaticAlignmentSamples", 4800))
    minimum_confidence = float(auto.get("delayMinimumConfidence", 0.70))

    should_align = (
        result.delay_classification == "FAIL"
        and delay is not None
        and minimum_align <= abs(int(delay)) <= maximum_align
        and result.delay_consistent
        and result.delay_confidence >= minimum_confidence
    )
    if not should_align:
        return result

    target = Path(processed_path)
    backup = target.with_name(target.stem + ".delay-backup.tmp.wav")
    shutil.copy2(target, backup)
    original_delay = int(delay)
    try:
        align_audio_file(target, original_delay)
        _repair_tail_after_alignment(target, auto)
        repaired = _CORE_EVALUATE(source_path, target, **kwargs)
        after_delay = repaired.residual_delay_samples
        improved = (
            after_delay is not None
            and abs(int(after_delay)) < abs(original_delay)
            and repaired.delay_classification != "FAIL"
        )
        if not improved:
            backup.replace(target)
            _DELAY_RESULTS[key] = result
            return result

        note = (
            f"automatic sample alignment applied: {original_delay:+d} → "
            f"{int(after_delay):+d} samples"
        )
        warnings = repaired.warnings
        if note not in warnings:
            warnings = warnings + (note,)
        fixed = replace(
            repaired,
            status="FAIL" if repaired.issues else "PASS",
            warnings=warnings,
            delay_auto_aligned=True,
            delay_original_samples=original_delay,
        )
        _DELAY_RESULTS[key] = fixed
        _ALIGNMENT_RESULTS[key] = (original_delay, int(after_delay))
        backup.unlink(missing_ok=True)
        return fixed
    except Exception:
        if backup.exists():
            backup.replace(target)
        _DELAY_RESULTS[key] = result
        return result
    finally:
        backup.unlink(missing_ok=True)


v33.v32._settings = _settings_v34
v33.v32.evaluate_master = _evaluate_with_smart_delay


class AppV34(v33.AppV33):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set(
            "v3.4 자동완성 준비 — 미세 지연은 과잉 탈락시키지 않고 큰 지연만 자동정렬합니다."
        )
        base_showinfo = v33.v32.legacy.messagebox.showinfo

        def versioned_showinfo(title, message):
            return base_showinfo(str(title).replace("v3.3", "v3.4").replace("v3.2", "v3.4"), message)

        v33.v32.legacy.messagebox.showinfo = versioned_showinfo

    def append_log(self, text):
        return super().append_log(
            str(text).replace("v3.3", "v3.4").replace("v3.2", "v3.4")
        )

    def _patch_csv_with_delay_diagnostics(self, output_dir: Path) -> int:
        csv_path = output_dir / "mastering_report.csv"
        if not csv_path.exists():
            return 0

        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = list(reader.fieldnames or [])

        additions = (
            "delay_classification",
            "delay_confidence",
            "delay_window_estimates",
            "delay_auto_alignment_samples",
            "delay_after_samples",
        )
        for name in additions:
            if name not in fieldnames:
                fieldnames.append(name)

        fixed_count = 0
        for row in rows:
            track = row.get("track", "")
            master_path = output_dir / f"{Path(track).stem}_MASTER.wav"
            key = str(master_path.resolve())
            result = _DELAY_RESULTS.get(key)
            if result is None:
                continue
            row["delay_classification"] = str(result.delay_classification)
            row["delay_confidence"] = f"{float(result.delay_confidence):.2f}"
            row["delay_window_estimates"] = ",".join(
                str(value) for value in result.delay_window_estimates_samples
            )
            alignment = _ALIGNMENT_RESULTS.get(key)
            if alignment is None:
                row["delay_auto_alignment_samples"] = "0"
                row["delay_after_samples"] = str(result.residual_delay_samples or 0)
                continue

            before, after = alignment
            fixed_count += 1
            row["delay_auto_alignment_samples"] = str(before)
            row["delay_after_samples"] = str(after)
            label = f"샘플 자동정렬({before:+d}→{after:+d})"
            existing = (row.get("auto_fixes") or "").strip()
            if label not in existing:
                row["auto_fixes"] = f"{existing} / {label}".strip(" /")
            processing = (row.get("processing_mode") or "normal").strip()
            if "delay_align" not in processing:
                row["processing_mode"] = processing + "+delay_align"

        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        report_copy = output_dir / "03_REPORT" / csv_path.name
        report_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_path, report_copy)
        return fixed_count

    def _worker(self, folder, files):
        _DELAY_RESULTS.clear()
        _ALIGNMENT_RESULTS.clear()
        super()._worker(folder, files)
        output_dir = Path(self.last_output_dir)
        aligned_count = self._patch_csv_with_delay_diagnostics(output_dir)
        self._refresh_beginner_summary(output_dir)
        if aligned_count:
            self.after(
                0,
                self.append_log,
                f"v3.4 큰 지연 자동정렬 완료: {aligned_count}곡 — 재검사 통과",
            )


if __name__ == "__main__":
    AppV34().mainloop()
