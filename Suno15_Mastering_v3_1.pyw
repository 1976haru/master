# -*- coding: utf-8 -*-
"""HARU Mastering v3.1 - automatic finish edition.

음악 지식 없이도 폴더/장르 선택 후 시작만 누르면:
마스터링 -> Quality Gate -> 문제별 자동수정 -> Codec 검사 -> RELEASE_READY 생성까지 완료한다.
"""
from __future__ import annotations

import csv
import shutil
from dataclasses import replace
from datetime import datetime
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V3_PATH = ROOT / "Suno15_Mastering_v3.pyw"


def _load_v3():
    loader = SourceFileLoader("suno15_v3", str(V3_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3 프로그램을 불러올 수 없습니다: {V3_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v3 = _load_v3()
v2 = v3.v2
legacy = v3.legacy

from haru_mastering.auto_finish import (
    apply_click_safe_fade,
    organize_release_files,
    write_beginner_summary,
)
from haru_mastering.codec_preview import check_codec_safety
from haru_mastering.quality_gate import evaluate_master
from haru_mastering.report import write_quality_reports


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.1 - AUTO FINISH"


def _settings(genre_key: str) -> tuple[dict, dict, dict]:
    payload = v3._profile_payload()
    profile = v2.get_profile(genre_key)
    global_cfg = payload["global"]
    auto = global_cfg.get("autoFinish", {})
    gate = global_cfg["qualityGate"]
    lra_overrides = auto.get("genreLraReductionLimitLu", {})
    lra_limit = float(lra_overrides.get(genre_key, profile.get("maxLraReductionLu", 0.8)))
    kwargs = {
        "target_lufs_i": float(profile["targetLufsI"]),
        "true_peak_ceiling_dbtp": float(profile["truePeakCeilingDbtp"]),
        "lufs_tolerance_lu": float(gate["lufsToleranceLu"]),
        "true_peak_tolerance_db": float(gate["truePeakToleranceDb"]),
        "maximum_clipped_samples": int(gate["maximumClippedSamples"]),
        "maximum_residual_delay_samples": int(gate["maximumResidualDelaySamples"]),
        "maximum_dc_offset": float(gate["maximumDcOffset"]),
        "minimum_stereo_correlation": float(gate["minimumFullBandStereoCorrelation"]),
        "minimum_low_band_stereo_correlation": float(gate["minimumLowBandStereoCorrelation"]),
        "low_band_cutoff_hz": float(global_cfg["bassMonoBelowHz"]),
        "expected_output_sample_rate_hz": int(global_cfg["workingSampleRateHz"]),
        "maximum_lra_reduction_lu": lra_limit,
        "reject_on_duration_loss": bool(gate["rejectOnUnexpectedDurationLoss"]),
        "reject_on_tail_cut": bool(gate.get("rejectOnTailCut", True)),
        "tail_window_ms": float(auto.get("tailWindowMs", 100.0)),
        "tail_end_rms_threshold_dbfs": float(auto.get("tailEndRmsThresholdDbfs", -50.0)),
        "tail_last_sample_threshold_dbfs": float(auto.get("tailLastSampleThresholdDbfs", -60.0)),
        "max_delay_ms": float(global_cfg["latencyDetectionMaxMs"]),
        "true_peak_oversample": int(global_cfg["truePeakOversampleFactor"]),
    }
    return kwargs, auto, profile


def _has_issue(result, prefix: str) -> bool:
    return any(issue.startswith(prefix) for issue in result.issues)


class AppV31(v3.AppV3):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.start_btn.config(text="▶ 자동 마스터링 + 검사 + 수정 + 배포준비")
        self.status_var.set("v3.1 자동완성 준비 — 폴더와 장르만 선택하세요.")

    def _render_quality(self, src: Path, dst: Path, genre: str, factor: float):
        first, first_err = legacy.first_pass(self.ffmpeg, src, genre, factor)
        if not first:
            return False, first_err
        return legacy.master_two_pass(self.ffmpeg, src, dst, genre, factor, first)

    def _worker(self, folder, files):
        genre, mode = self.genre_var.get(), self.quality_var.get()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = folder / f"MASTER_{genre.replace(' ', '_')}_{'AUTO' if mode == 'QUALITY+' else 'FAST'}_{stamp}"
        out_dir.mkdir(parents=True, exist_ok=True)
        self.last_output_dir = out_dir

        gate_kwargs, auto_cfg, profile = _settings(genre)
        max_retries = int(auto_cfg.get("maximumAutoRerenders", 2)) if mode == "QUALITY+" else 0
        fade_ms = float(auto_cfg.get("hardCutAutoFadeMs", 25.0))
        codec_enabled = bool(auto_cfg.get("codecPreviewEnabled", True)) and mode == "QUALITY+"
        codec_tolerance = float(auto_cfg.get("codecTruePeakSafetyMarginDb", 0.05))
        codec_step = float(auto_cfg.get("codecCeilingStepDb", 0.20))

        rows = []
        gate_results = []
        release_rows = []
        unresolved = []
        auto_fixed_count = 0
        codec_safe_count = 0
        total = len(files)
        original_genre_tp = float(legacy.GENRES[genre]["target_tp"])

        self.after(0, self.append_log, f"v3.1 완전자동 | 장르: {legacy.GENRES[genre]['label']}")
        self.after(0, self.append_log, "마스터링 → 자동검사 → 자동수정 → 코덱검사 → RELEASE_READY")
        self.after(0, self.append_log, "-" * 64)

        try:
            for idx, src in enumerate(files, 1):
                self.after(0, self.status_var.set, f"{idx}/{total} 자동 처리 중: {src.name}")
                self.after(0, self.append_log, f"[{idx:02d}/{total:02d}] {src.name}")
                raw, _ = legacy.analyze_raw(self.ffmpeg, src)
                raw_lra = legacy.safe_float(raw.get("input_lra")) if raw else None
                factor = legacy.adaptive_factor(raw_lra) if mode == "QUALITY+" else 1.0
                current_tp = original_genre_tp
                dst = out_dir / f"{src.stem}_MASTER.wav"
                fixes: list[str] = []
                codec_result = None
                codec_error = ""
                result = None
                render_ok = False
                render_err = ""

                for attempt in range(max_retries + 1):
                    legacy.GENRES[genre]["target_tp"] = current_tp
                    if mode == "QUALITY+":
                        render_ok, render_err = self._render_quality(src, dst, genre, factor)
                    else:
                        render_ok, render_err = legacy.master_one_pass(self.ffmpeg, src, dst, genre)
                    if not render_ok or not dst.exists():
                        break

                    result = evaluate_master(src, dst, **gate_kwargs)

                    if result.tail_hard_cut:
                        apply_click_safe_fade(dst, fade_ms=fade_ms)
                        fixes.append(f"Tail {fade_ms:.0f}ms 자동 페이드")
                        result = evaluate_master(src, dst, **gate_kwargs)

                    if _has_issue(result, "LRA reduction exceeded") and attempt < max_retries:
                        new_factor = max(0.30, factor * 0.65)
                        if new_factor < factor - 0.01:
                            factor = new_factor
                            fixes.append(f"압축 자동 완화({factor:.2f})")
                            self.after(0, self.append_log, f"    ↻ LRA 보호 재마스터 {attempt + 1}/{max_retries}")
                            continue

                    if result.status == "PASS" and codec_enabled:
                        try:
                            codec_result = check_codec_safety(
                                dst,
                                true_peak_ceiling_dbtp=float(profile["truePeakCeilingDbtp"]),
                                tolerance_db=codec_tolerance,
                                ffmpeg=self.ffmpeg,
                            )
                            codec_error = ""
                        except Exception as exc:
                            codec_result = None
                            codec_error = f"codec verification failed: {exc}"
                            break
                        if not codec_result.safe and attempt < max_retries:
                            current_tp -= codec_step
                            fixes.append(f"코덱 피크 보호 ceiling {current_tp:.2f} dBTP")
                            self.after(0, self.append_log, f"    ↻ AAC/MP3 피크 보호 재마스터 {attempt + 1}/{max_retries}")
                            continue
                    break

                legacy.GENRES[genre]["target_tp"] = original_genre_tp

                if not render_ok or result is None:
                    status = "FAIL"
                    notes = "마스터링 처리 실패"
                    unresolved.append((src.name, [notes]))
                    (out_dir / f"ERROR_{src.stem}.txt").write_text((render_err or "")[-5000:], encoding="utf-8", errors="ignore")
                else:
                    if codec_enabled and result.status == "PASS" and codec_result is None and not codec_error:
                        try:
                            codec_result = check_codec_safety(
                                dst,
                                true_peak_ceiling_dbtp=float(profile["truePeakCeilingDbtp"]),
                                tolerance_db=codec_tolerance,
                                ffmpeg=self.ffmpeg,
                            )
                        except Exception as exc:
                            codec_error = f"codec verification failed: {exc}"

                    codec_safe = codec_result.safe if codec_result is not None else (not codec_enabled)
                    if result.status == "PASS" and codec_error:
                        status = "FAIL"
                        notes = codec_error
                        result = replace(result, status="FAIL", issues=result.issues + (notes,))
                        unresolved.append((src.name, [notes]))
                    elif result.status == "PASS" and not codec_safe:
                        status = "FAIL"
                        notes = f"codec peak unsafe: {codec_result.maximum_true_peak_dbtp:.2f} dBTP"
                        result = replace(result, status="FAIL", issues=result.issues + (notes,))
                        unresolved.append((src.name, [notes]))
                    else:
                        status = result.status
                        notes = " / ".join(list(result.issues) + list(result.warnings))
                        if status != "PASS":
                            unresolved.append((src.name, list(result.issues) + list(result.warnings)))

                    if codec_result is not None and codec_result.safe:
                        codec_safe_count += 1
                    gate_results.append((src.name, result))

                if fixes and status == "PASS":
                    auto_fixed_count += 1
                release_rows.append((dst, status))
                final = legacy.analyze_raw(self.ffmpeg, dst)[0] if dst.exists() else None
                rows.append({
                    "track": src.name,
                    "status": status,
                    "source_LUFS": raw.get("input_i", "") if raw else "",
                    "source_dBTP": raw.get("input_tp", "") if raw else "",
                    "source_LRA": raw.get("input_lra", "") if raw else "",
                    "target_LUFS": legacy.GENRES[genre]["target_i"],
                    "final_LUFS": final.get("input_i", "") if final else "",
                    "final_dBTP": final.get("input_tp", "") if final else "",
                    "adaptive_factor": f"{factor:.2f}",
                    "auto_fixes": " / ".join(fixes),
                    "codec_max_dBTP": f"{codec_result.maximum_true_peak_dbtp:.2f}" if codec_result is not None else "",
                    "notes": notes,
                })
                icon = "PASS" if status == "PASS" else "REVIEW"
                fix_text = f" | 자동수정: {', '.join(fixes)}" if fixes else ""
                self.after(0, self.append_log, f"    → {icon}{fix_text}")
                self.after(0, self.progress_var.set, idx / total * 100)
        finally:
            legacy.GENRES[genre]["target_tp"] = original_genre_tp

        if rows:
            with open(out_dir / "mastering_report.csv", "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

        if gate_results:
            json_path, html_path = write_quality_reports(out_dir, gate_results)
        else:
            json_path = html_path = None

        sections = []
        if unresolved:
            for name, issues in unresolved:
                sections += ["=" * 72, f"자동 해결 한도 초과: {name}", legacy.make_studio_prompt(genre, issues)]
        else:
            sections += [
                "모든 곡이 v3.1 자동검사/자동수정 기준 PASS입니다. Suno Studio 추가 보완은 필수가 아닙니다.",
                legacy.make_studio_prompt(genre),
            ]
        prompt_path = out_dir / "STUDIO_문제곡_보완_프롬프트.txt"
        prompt_path.write_text("\n".join(sections), encoding="utf-8")

        paths = organize_release_files(out_dir, release_rows)
        for report_file in [out_dir / "mastering_report.csv", prompt_path, json_path, html_path]:
            if report_file and Path(report_file).exists():
                shutil.copy2(report_file, paths["report"] / Path(report_file).name)

        pass_count = sum(row["status"] == "PASS" for row in rows)
        review_count = len(rows) - pass_count
        beginner = write_beginner_summary(
            out_dir,
            pass_count=pass_count,
            review_count=review_count,
            auto_fixed_count=auto_fixed_count,
            codec_safe_count=codec_safe_count,
            total_count=len(rows),
        )
        self.last_check_items = unresolved

        if review_count == 0:
            summary = (
                f"자동완성 완료: {len(rows)}곡 전부 배포 가능\n"
                f"자동 수정 완료 {auto_fixed_count}곡 / 코덱 안전 {codec_safe_count}곡\n"
                f"사용할 폴더: {paths['release']}"
            )
            title = "v3.1 자동완성 — 배포 가능"
        else:
            summary = (
                f"자동완성 완료: PASS {pass_count} / 배포 보류 {review_count}\n"
                f"안전한 파일: {paths['release']}\n"
                f"보류 파일: {paths['review']}\n"
                f"최종 판정: {beginner}"
            )
            title = "v3.1 자동완성 — 일부 배포 보류"

        self.after(0, self.append_log, "-" * 64)
        self.after(0, self.append_log, summary)
        self.after(0, self.status_var.set, f"완료 — PASS {pass_count} / 보류 {review_count}")
        self.after(0, self.start_btn.config, {"state": "normal"})
        self.after(0, lambda: legacy.messagebox.showinfo(title, summary))


if __name__ == "__main__":
    AppV31().mainloop()
