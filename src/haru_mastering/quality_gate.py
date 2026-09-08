from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from math import gcd
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt, sosfiltfilt

from .alignment import estimate_delay_samples
from .analysis import AudioMetrics, analyze_array


@dataclass(frozen=True)
class QualityGateResult:
    status: str
    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    residual_delay_samples: int | None
    duration_delta_ms: float
    low_band_stereo_correlation: float
    lra_reduction_lu: float
    crest_factor_loss_db: float
    lra_guard_triggered: bool
    tail_end_rms_dbfs: float
    tail_last_sample_dbfs: float
    tail_hard_cut: bool
    tail_energetic_end: bool
    source: AudioMetrics
    processed: AudioMetrics

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = self.source.to_dict()
        payload["processed"] = self.processed.to_dict()
        return payload


def _maximum_dc(metrics: AudioMetrics) -> float:
    return max((abs(value) for value in metrics.dc_offset), default=0.0)


def _finite_metric_values(metrics: AudioMetrics) -> bool:
    values = [
        metrics.lufs_i,
        metrics.lra_lu,
        metrics.sample_peak_dbfs,
        metrics.true_peak_dbtp,
        metrics.rms_dbfs,
        metrics.crest_factor_db,
        metrics.stereo_correlation,
        metrics.side_to_mid_db,
    ]
    return all(np.isfinite(value) or value == float("-inf") for value in values)


def _dbfs(value: float) -> float:
    value = abs(float(value))
    if value <= 1e-15:
        return float("-inf")
    return 20.0 * math.log10(value)


def lra_dynamics_risk(
    *,
    lra_reduction_lu: float,
    final_lra_lu: float,
    crest_factor_loss_db: float,
    maximum_lra_reduction_lu: float,
    minimum_final_lra_lu: float,
    maximum_crest_factor_loss_db: float,
) -> bool:
    """Return True only when LRA loss is accompanied by real dynamics risk.

    LRA can move by more than a profile's preferred amount even when the final
    program remains open and the crest factor is preserved or improved.  Such
    files should not be rejected solely because one statistical metric moved.
    """
    if not np.isfinite(lra_reduction_lu) or not np.isfinite(final_lra_lu):
        return False
    if lra_reduction_lu <= float(maximum_lra_reduction_lu) + 0.05:
        return False
    low_final_lra = final_lra_lu < float(minimum_final_lra_lu)
    crest_collapsed = (
        np.isfinite(crest_factor_loss_db)
        and crest_factor_loss_db > float(maximum_crest_factor_loss_db)
    )
    return bool(low_final_lra or crest_collapsed)


def _tail_metrics(
    audio: np.ndarray,
    sample_rate: int,
    *,
    window_ms: float,
    end_rms_threshold_dbfs: float,
    last_sample_threshold_dbfs: float,
    energetic_end_threshold_dbfs: float | None,
) -> tuple[float, float, bool, bool]:
    if audio.shape[0] == 0:
        return float("-inf"), float("-inf"), False, False
    frames = max(1, int(round(sample_rate * float(window_ms) / 1000.0)))
    tail = audio[-frames:]
    rms = float(np.sqrt(np.mean(np.square(tail)))) if tail.size else 0.0
    last = float(np.max(np.abs(audio[-1])))
    end_rms_dbfs = _dbfs(rms)
    last_sample_dbfs = _dbfs(last)
    hard_cut = (
        end_rms_dbfs > float(end_rms_threshold_dbfs)
        and last_sample_dbfs > float(last_sample_threshold_dbfs)
    )
    energetic_end = (
        energetic_end_threshold_dbfs is not None
        and end_rms_dbfs > float(energetic_end_threshold_dbfs)
    )
    return end_rms_dbfs, last_sample_dbfs, hard_cut, energetic_end


def _resample_audio(audio: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
    if source_sr == target_sr:
        return audio
    divisor = gcd(int(source_sr), int(target_sr))
    return resample_poly(
        audio,
        up=int(target_sr // divisor),
        down=int(source_sr // divisor),
        axis=0,
        padtype="line",
    )


def _low_band_stereo_correlation(
    audio: np.ndarray,
    sample_rate: int,
    *,
    cutoff_hz: float = 110.0,
) -> float:
    if audio.ndim != 2 or audio.shape[1] < 2:
        return 1.0
    nyquist = sample_rate / 2.0
    cutoff = min(float(cutoff_hz), nyquist * 0.90)
    if cutoff <= 0:
        return 1.0
    sos = butter(4, cutoff, btype="lowpass", fs=sample_rate, output="sos")
    left = audio[:, 0]
    right = audio[:, 1]
    try:
        left_low = sosfiltfilt(sos, left)
        right_low = sosfiltfilt(sos, right)
    except ValueError:
        left_low = sosfilt(sos, left)
        right_low = sosfilt(sos, right)
    if np.std(left_low) < 1e-12 or np.std(right_low) < 1e-12:
        return 1.0
    return float(np.corrcoef(left_low, right_low)[0, 1])


def evaluate_master(
    source_path: str | Path,
    processed_path: str | Path,
    *,
    target_lufs_i: float,
    true_peak_ceiling_dbtp: float,
    lufs_tolerance_lu: float = 0.20,
    true_peak_tolerance_db: float = 0.05,
    maximum_clipped_samples: int = 0,
    maximum_residual_delay_samples: int = 1,
    maximum_dc_offset: float = 0.0001,
    minimum_stereo_correlation: float = -0.05,
    minimum_low_band_stereo_correlation: float = 0.70,
    low_band_cutoff_hz: float = 110.0,
    expected_output_sample_rate_hz: int | None = None,
    maximum_lra_reduction_lu: float | None = None,
    minimum_final_lra_lu: float = 3.5,
    maximum_crest_factor_loss_db: float = 0.75,
    reject_on_duration_loss: bool = True,
    reject_on_tail_cut: bool = True,
    tail_window_ms: float = 100.0,
    tail_end_rms_threshold_dbfs: float = -50.0,
    tail_last_sample_threshold_dbfs: float = -60.0,
    maximum_energetic_tail_rms_dbfs: float | None = None,
    max_delay_ms: float = 100.0,
    true_peak_oversample: int = 4,
) -> QualityGateResult:
    source_file = Path(source_path)
    processed_file = Path(processed_path)
    source_audio, source_sr = sf.read(source_file, always_2d=True, dtype="float64")
    processed_audio, processed_sr = sf.read(processed_file, always_2d=True, dtype="float64")

    source = analyze_array(source_audio, source_sr, true_peak_oversample=true_peak_oversample)
    processed = analyze_array(
        processed_audio,
        processed_sr,
        true_peak_oversample=true_peak_oversample,
    )

    issues: list[str] = []
    warnings: list[str] = []

    if expected_output_sample_rate_hz is not None and processed_sr != int(expected_output_sample_rate_hz):
        issues.append(
            f"unexpected output sample rate: {processed_sr} Hz "
            f"(expected {int(expected_output_sample_rate_hz)} Hz)"
        )

    try:
        source_for_delay = _resample_audio(source_audio, source_sr, processed_sr)
        if source_sr != processed_sr:
            warnings.append(
                f"source {source_sr} Hz was resampled to {processed_sr} Hz for delay measurement"
            )
        residual_delay = estimate_delay_samples(
            source_for_delay,
            processed_audio,
            processed_sr,
            max_delay_ms=max_delay_ms,
        )
    except ValueError as exc:
        residual_delay = None
        warnings.append(f"delay measurement unavailable: {exc}")

    duration_delta_ms = (processed.duration_seconds - source.duration_seconds) * 1000.0
    low_band_corr = _low_band_stereo_correlation(
        processed_audio,
        processed_sr,
        cutoff_hz=low_band_cutoff_hz,
    )
    lra_reduction = (
        float(source.lra_lu - processed.lra_lu)
        if np.isfinite(source.lra_lu) and np.isfinite(processed.lra_lu)
        else 0.0
    )
    crest_factor_loss = (
        float(source.crest_factor_db - processed.crest_factor_db)
        if np.isfinite(source.crest_factor_db) and np.isfinite(processed.crest_factor_db)
        else 0.0
    )
    lra_guard_triggered = False
    if maximum_lra_reduction_lu is not None:
        lra_guard_triggered = lra_dynamics_risk(
            lra_reduction_lu=lra_reduction,
            final_lra_lu=processed.lra_lu,
            crest_factor_loss_db=crest_factor_loss,
            maximum_lra_reduction_lu=float(maximum_lra_reduction_lu),
            minimum_final_lra_lu=float(minimum_final_lra_lu),
            maximum_crest_factor_loss_db=float(maximum_crest_factor_loss_db),
        )

    (
        tail_end_rms_dbfs,
        tail_last_sample_dbfs,
        tail_hard_cut,
        tail_energetic_end,
    ) = _tail_metrics(
        processed_audio,
        processed_sr,
        window_ms=tail_window_ms,
        end_rms_threshold_dbfs=tail_end_rms_threshold_dbfs,
        last_sample_threshold_dbfs=tail_last_sample_threshold_dbfs,
        energetic_end_threshold_dbfs=maximum_energetic_tail_rms_dbfs,
    )

    if not _finite_metric_values(processed):
        issues.append("processed metrics contain invalid numeric values")
    if abs(processed.lufs_i - float(target_lufs_i)) > float(lufs_tolerance_lu):
        issues.append(
            f"LUFS target miss: {processed.lufs_i:.2f} LUFS "
            f"(target {target_lufs_i:.2f} ±{lufs_tolerance_lu:.2f})"
        )
    if processed.true_peak_dbtp > float(true_peak_ceiling_dbtp) + float(true_peak_tolerance_db):
        issues.append(
            f"true peak exceeded: {processed.true_peak_dbtp:.2f} dBTP "
            f"> {true_peak_ceiling_dbtp:.2f} dBTP"
        )
    if processed.clipped_sample_count > int(maximum_clipped_samples):
        issues.append(f"clipped samples: {processed.clipped_sample_count}")
    if _maximum_dc(processed) > float(maximum_dc_offset):
        issues.append(f"DC offset too high: {_maximum_dc(processed):.6f}")
    if processed.channels >= 2 and processed.stereo_correlation < float(minimum_stereo_correlation):
        issues.append(f"stereo correlation too low: {processed.stereo_correlation:.3f}")
    if processed.channels >= 2 and low_band_corr < float(minimum_low_band_stereo_correlation):
        issues.append(
            f"low-band stereo correlation too low: {low_band_corr:.3f} "
            f"below {low_band_cutoff_hz:.0f} Hz"
        )
    if residual_delay is not None and abs(residual_delay) > int(maximum_residual_delay_samples):
        issues.append(
            f"residual processing delay: {residual_delay} samples "
            f"(limit ±{maximum_residual_delay_samples})"
        )
    if reject_on_duration_loss and duration_delta_ms < -1.0:
        issues.append(f"unexpected duration loss: {duration_delta_ms:.2f} ms")
    if lra_guard_triggered:
        issues.append(
            f"DYNAMICS RISK: LRA reduced {lra_reduction:.2f} LU "
            f"(preferred limit {float(maximum_lra_reduction_lu):.2f}), "
            f"final LRA {processed.lra_lu:.2f} LU, "
            f"crest loss {crest_factor_loss:.2f} dB"
        )
    if reject_on_tail_cut and tail_hard_cut:
        issues.append(
            f"TAIL HARD CUT: end RMS {tail_end_rms_dbfs:.1f} dBFS / "
            f"last sample {tail_last_sample_dbfs:.1f} dBFS"
        )
    if reject_on_tail_cut and tail_energetic_end:
        issues.append(
            f"ENERGETIC TAIL END: end RMS {tail_end_rms_dbfs:.1f} dBFS "
            f"> {float(maximum_energetic_tail_rms_dbfs):.1f} dBFS"
        )

    if lra_reduction > 1.5 and maximum_lra_reduction_lu is None:
        warnings.append(f"LRA reduced by {lra_reduction:.2f} LU")
    if processed.trailing_silence_ms + 20.0 < source.trailing_silence_ms and duration_delta_ms <= 0:
        warnings.append("output tail is shorter than source tail; listen for reverb cutoff")

    status = "FAIL" if issues else ("WARN" if warnings else "PASS")
    return QualityGateResult(
        status=status,
        issues=tuple(issues),
        warnings=tuple(warnings),
        residual_delay_samples=residual_delay,
        duration_delta_ms=float(duration_delta_ms),
        low_band_stereo_correlation=low_band_corr,
        lra_reduction_lu=lra_reduction,
        crest_factor_loss_db=crest_factor_loss,
        lra_guard_triggered=lra_guard_triggered,
        tail_end_rms_dbfs=tail_end_rms_dbfs,
        tail_last_sample_dbfs=tail_last_sample_dbfs,
        tail_hard_cut=tail_hard_cut,
        tail_energetic_end=tail_energetic_end,
        source=source,
        processed=processed,
    )
