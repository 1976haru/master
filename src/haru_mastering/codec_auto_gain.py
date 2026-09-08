from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import soundfile as sf

from .codec_preview import CodecSafetyResult


@dataclass(frozen=True)
class CodecAutoGainResult:
    safety: CodecSafetyResult
    total_gain_reduction_db: float
    passes: int
    exhausted: bool


def calculate_codec_gain_reduction_db(
    measured_true_peak_dbtp: float,
    true_peak_ceiling_dbtp: float,
    *,
    safety_margin_db: float = 0.10,
    minimum_step_db: float = 0.05,
    maximum_step_db: float = 1.50,
) -> float:
    """Return the smallest bounded attenuation needed for a codec-safe peak.

    Example: measured -1.12 dBTP, ceiling -1.50 dBTP and 0.10 dB
    safety margin -> target -1.60 dBTP -> 0.48 dB attenuation.
    """
    measured = float(measured_true_peak_dbtp)
    target = float(true_peak_ceiling_dbtp) - max(0.0, float(safety_margin_db))
    needed = measured - target
    if not math.isfinite(needed) or needed <= 0.0:
        return 0.0
    return min(
        max(0.0, float(maximum_step_db)),
        max(max(0.0, float(minimum_step_db)), needed),
    )


def apply_gain_reduction(
    path: str | Path,
    reduction_db: float,
) -> Path:
    """Apply transparent broadband attenuation while preserving WAV format."""
    target = Path(path)
    reduction = max(0.0, float(reduction_db))
    if reduction <= 0.0:
        return target

    audio, sample_rate = sf.read(target, always_2d=True, dtype="float64")
    if audio.shape[0] == 0:
        return target

    gain = 10.0 ** (-reduction / 20.0)
    adjusted = audio * gain
    info = sf.info(target)
    subtype = info.subtype if info.subtype else "PCM_24"
    temp = target.with_name(target.stem + ".codecgain.tmp.wav")
    sf.write(temp, adjusted, sample_rate, subtype=subtype)
    temp.replace(target)
    return target


def ensure_codec_safety_with_auto_gain(
    source_path: str | Path,
    *,
    checker: Callable[..., CodecSafetyResult],
    true_peak_ceiling_dbtp: float,
    tolerance_db: float = 0.05,
    ffmpeg: str | None = None,
    maximum_passes: int = 3,
    safety_margin_db: float = 0.10,
    minimum_step_db: float = 0.05,
    maximum_single_reduction_db: float = 1.50,
    maximum_total_reduction_db: float = 2.00,
) -> CodecAutoGainResult:
    """Measure AAC/MP3 peaks, attenuate only as much as needed, and recheck."""
    target = Path(source_path)
    result = checker(
        target,
        true_peak_ceiling_dbtp=float(true_peak_ceiling_dbtp),
        tolerance_db=float(tolerance_db),
        ffmpeg=ffmpeg,
    )
    total = 0.0
    passes = 0
    max_passes = max(0, int(maximum_passes))
    max_total = max(0.0, float(maximum_total_reduction_db))

    while not result.safe and passes < max_passes and total < max_total - 1e-9:
        step = calculate_codec_gain_reduction_db(
            result.maximum_true_peak_dbtp,
            true_peak_ceiling_dbtp,
            safety_margin_db=safety_margin_db,
            minimum_step_db=minimum_step_db,
            maximum_step_db=maximum_single_reduction_db,
        )
        step = min(step, max_total - total)
        if step <= 1e-9:
            break

        apply_gain_reduction(target, step)
        total += step
        passes += 1
        result = checker(
            target,
            true_peak_ceiling_dbtp=float(true_peak_ceiling_dbtp),
            tolerance_db=float(tolerance_db),
            ffmpeg=ffmpeg,
        )

    return CodecAutoGainResult(
        safety=result,
        total_gain_reduction_db=total,
        passes=passes,
        exhausted=(not result.safe),
    )
