from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from .analysis import AudioMetrics, analyze_array


@dataclass(frozen=True)
class DcCleanupResult:
    applied: bool
    before_max_abs: float
    after_max_abs: float
    channel_offsets: tuple[float, ...]
    metrics: AudioMetrics
    processed_audio: np.ndarray
    processed_sample_rate: int


def remove_dc_offset(
    path: str | Path,
    *,
    audio: np.ndarray | None = None,
    sample_rate: int | None = None,
    maximum_dc_offset: float = 0.0001,
    true_peak_oversample: int = 4,
) -> DcCleanupResult:
    target = Path(path)
    if audio is None:
        data, rate = sf.read(target, always_2d=True, dtype="float64")
    else:
        data = np.asarray(audio, dtype=np.float64)
        rate = int(sample_rate or 0)
    if data.ndim != 2 or data.shape[0] == 0 or rate <= 0:
        raise ValueError("DC cleanup requires non-empty 2D audio and a sample rate")

    offsets = np.mean(data, axis=0)
    before = float(np.max(np.abs(offsets), initial=0.0))
    cleaned = data - offsets[None, :]
    after_metrics = analyze_array(
        cleaned,
        rate,
        true_peak_oversample=int(true_peak_oversample),
    )
    info = sf.info(target) if target.exists() else None
    subtype = info.subtype if info and info.subtype else "PCM_24"
    if np.max(np.abs(cleaned), initial=0.0) > 1.0:
        raise ValueError("DC cleanup would produce clipped samples")
    temp = target.with_name(target.stem + ".dcclean.tmp.wav")
    sf.write(temp, cleaned, rate, subtype=subtype)
    temp.replace(target)
    return DcCleanupResult(
        applied=before > float(maximum_dc_offset),
        before_max_abs=before,
        after_max_abs=max((abs(float(value)) for value in after_metrics.dc_offset), default=0.0),
        channel_offsets=tuple(float(value) for value in offsets),
        metrics=after_metrics,
        processed_audio=cleaned,
        processed_sample_rate=rate,
    )
