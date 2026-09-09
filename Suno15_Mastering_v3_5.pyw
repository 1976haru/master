# -*- coding: utf-8 -*-
"""HARU Mastering v3.5 - adaptive energetic tail finish."""
from __future__ import annotations

import csv
import shutil
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V34_PATH = ROOT / "Suno15_Mastering_v3_4.pyw"


def _load_v34():
    loader = SourceFileLoader("suno15_v34", str(V34_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.4 프로그램을 불러올 수 없습니다: {V34_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v34 = _load_v34()

from haru_mastering.auto_finish import TailRepairResult, repair_tail_automatically


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.5 - ADAPTIVE TAIL FINISH"
_TAIL_RESULTS: dict[str, TailRepairResult] = {}


def _tail_candidate_values(auto_cfg: dict) -> tuple[float, ...]:
    raw = auto_cfg.get("energeticTailFadeCandidatesMs", [400.0, 600.0, 800.0, 1200.0])
    if not isinstance(raw, (list, tuple)):
        raw = [400.0, 600.0, 800.0, 1200.0]
    values = tuple(float(value) for value in raw if float(value) > 0.0)
    return values or (400.0, 600.0, 800.0, 1200.0)


def _repair_with_config(path: Path, auto_cfg: dict) -> TailRepairResult:
    candidates = _tail_candidate_values(auto_cfg)
    repair = repair_tail_automatically(
        path,
        window_ms=float(auto_cfg.get("tailWindowMs", 100.0)),
        end_rms_threshold_dbfs=float(auto_cfg.get("tailEndRmsThresholdDbfs", -50.0)),
        last_sample_threshold_dbfs=float(auto_cfg.get("tailLastSampleThresholdDbfs", -60.0)),
        energetic_end_threshold_dbfs=float(auto_cfg.get("energeticTailThresholdDbfs", -35.0)),
        energetic_fade_ms=float(auto_cfg.get("energeticTailFadeMs", candidates[0])),
        energetic_fade_candidates_ms=candidates,
        energetic_target_margin_db=float(auto_cfg.get("energeticTailTargetMarginDb", 0.5)),
        maximum_energetic_fade_ms=float(auto_cfg.get("energeticTailMaximumFadeMs", 1200.0)),
        hard_cut_fade_ms=float(auto_cfg.get("hardCutAutoFadeMs", 25.0)),
        micro_fade_ms=float(auto_cfg.get("microFadeMs", 5.0)),
        micro_fade_last_sample_threshold_dbfs=float(
            auto_cfg.get("microFadeLastSampleThresholdDbfs", -80.0)
        ),
    )
    _TAIL_RESULTS[str(Path(path).resolve())] = repair
    return repair


def _adaptive_tail_after_alignment(path: Path, auto_cfg: dict) -> None:
    _repair_with_config(Path(path), auto_cfg)


# v3.4 calls this global after sample alignment. Replace it so the aligned file
# also receives the v3.5 adaptive fade ladder and the final diagnostics are kept.
v34._repair_tail_after_alignment = _adaptive_tail_after_alignment


class AppV35(v34.AppV34):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set(
            "v3.5 자동완성 준비 — 강한 곡 끝은 400→600→800→1200ms로 자동 확장합니다."
        )
        base_showinfo = v34.v33.v32.legacy.messagebox.showinfo

        def versioned_showinfo(title, message):
            text = str(title)
            for version in ("v3.4", "v3.3", "v3.2"):
                text = text.replace(version, "v3.5")
            return base_showinfo(text, message)

        v34.v33.v32.legacy.messagebox.showinfo = versioned_showinfo

    def append_log(self, text):
        value = str(text)
        for version in ("v3.4", "v3.3", "v3.2"):
            value = value.replace(version, "v3.5")
        return super().append_log(value)

    def _repair_tail(self, dst: Path, auto_cfg: dict, fixes: list[str]):
        repair = _repair_with_config(dst, auto_cfg)
        labels = {
            "musical_tail_fade": f"Tail {repair.fade_ms:.0f}ms 적응형 음악적 감쇠",
            "click_safe_fade": f"Tail {repair.fade_ms:.0f}ms 클릭방지",
            "micro_fade": f"Tail {repair.fade_ms:.0f}ms 마이크로 페이드",
        }
        if repair.mode in labels:
            v34.v33.v32._append_unique(fixes, labels[repair.mode])
        return repair

    def _patch_csv_with_adaptive_tail(self, output_dir: Path) -> int:
        csv_path = output_dir / "mastering_report.csv"
        if not csv_path.exists():
            return 0

        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = list(reader.fieldnames or [])

        additions = (
            "tail_fade_attempts_ms",
            "tail_selected_fade_ms",
            "tail_target_rms_dbfs",
            "tail_before_rms_dbfs",
            "tail_after_rms_dbfs",
        )
        for name in additions:
            if name not in fieldnames:
                fieldnames.append(name)

        adaptive_count = 0
        for row in rows:
            track = row.get("track", "")
            master_path = output_dir / f"{Path(track).stem}_MASTER.wav"
            repair = _TAIL_RESULTS.get(str(master_path.resolve()))
            if repair is None:
                continue

            row["tail_fade_attempts_ms"] = ",".join(
                f"{value:.0f}" for value in repair.attempted_fades_ms
            )
            row["tail_selected_fade_ms"] = f"{repair.fade_ms:.0f}"
            row["tail_target_rms_dbfs"] = (
                "" if repair.target_end_rms_dbfs is None else f"{repair.target_end_rms_dbfs:.1f}"
            )
            row["tail_before_rms_dbfs"] = f"{repair.before.end_rms_dbfs:.1f}"
            row["tail_after_rms_dbfs"] = f"{repair.after.end_rms_dbfs:.1f}"

            if repair.mode == "musical_tail_fade" and len(repair.attempted_fades_ms) > 1:
                adaptive_count += 1
                processing = (row.get("processing_mode") or "normal").strip()
                if "adaptive_tail" not in processing:
                    row["processing_mode"] = processing + "+adaptive_tail"

        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        report_copy = output_dir / "03_REPORT" / csv_path.name
        report_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_path, report_copy)
        return adaptive_count

    def _worker(self, folder, files):
        _TAIL_RESULTS.clear()
        super()._worker(folder, files)
        output_dir = Path(self.last_output_dir)
        adaptive_count = self._patch_csv_with_adaptive_tail(output_dir)
        self._refresh_beginner_summary(output_dir)
        if adaptive_count:
            self.after(
                0,
                self.append_log,
                f"v3.5 적응형 Tail 완료: {adaptive_count}곡 — 가장 짧은 안전 페이드 선택",
            )


if __name__ == "__main__":
    AppV35().mainloop()
