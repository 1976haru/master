from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from .alignment import estimate_delay_samples
from .analysis import AudioMetrics, analyze_array


@dataclass(frozen=True)
class QualityGateResult:
    status: str
    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    residual_delay_samples: int | None
    duration_delta_ms: float
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
    reject_on_duration_loss: bool = True,
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

    if source_sr != processed_sr:
        issues.append(f"sample rate mismatch: {source_sr} -> {processed_sr} Hz")
        residual_delay = None
    else:
        try:
            residual_delay = estimate_delay_samples(
                source_audio,
                processed_audio,
                source_sr,
                max_delay_ms=max_delay_ms,
            )
        except ValueError as exc:
            residual_delay = None
            warnings.append(f"delay measurement unavailable: {exc}")

    duration_delta_ms = (processed.duration_seconds - source.duration_seconds) * 1000.0

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
        issues.append(
            f"stereo correlation too low: {processed.stereo_correlation:.3f}"
        )
    if residual_delay is not None and abs(residual_delay) > int(maximum_residual_delay_samples):
        issues.append(
            f"residual processing delay: {residual_delay} samples "
            f"(limit ±{maximum_residual_delay_samples})"
        )
    if reject_on_duration_loss and duration_delta_ms < -1.0:
        issues.append(f"unexpected duration loss: {duration_delta_ms:.2f} ms")

    # Large LRA collapse is not always a hard failure, but it is useful for listening review.
    lra_change = processed.lra_lu - source.lra_lu
    if lra_change < -1.5:
        warnings.append(f"LRA reduced by {-lra_change:.2f} LU")
    if processed.trailing_silence_ms + 20.0 < source.trailing_silence_ms and duration_delta_ms <= 0:
        warnings.append("output tail is shorter than source tail; listen for reverb cutoff")

    status = "FAIL" if issues else ("WARN" if warnings else "PASS")
    return QualityGateResult(
        status=status,
        issues=tuple(issues),
        warnings=tuple(warnings),
        residual_delay_samples=residual_delay,
        duration_delta_ms=float(duration_delta_ms),
        source=source,
        processed=processed,
    )
