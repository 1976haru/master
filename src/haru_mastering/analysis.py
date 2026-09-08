from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import resample_poly


_EPS = np.finfo(np.float64).tiny
_DEFAULT_BANDS = (
    (20, 60),
    (60, 120),
    (120, 250),
    (250, 500),
    (500, 1000),
    (1000, 2000),
    (2000, 5000),
    (5000, 10000),
    (10000, 20000),
)


@dataclass(frozen=True)
class AudioMetrics:
    sample_rate_hz: int
    channels: int
    frames: int
    duration_seconds: float
    lufs_i: float
    lra_lu: float
    sample_peak_dbfs: float
    true_peak_dbtp: float
    rms_dbfs: float
    crest_factor_db: float
    dc_offset: tuple[float, ...]
    clipped_sample_count: int
    stereo_correlation: float
    side_to_mid_db: float
    leading_silence_ms: float
    trailing_silence_ms: float
    band_energy_db: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_audio_2d(audio: np.ndarray) -> np.ndarray:
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2:
        raise ValueError("Audio must have shape (frames,) or (frames, channels).")
    if array.shape[0] == 0:
        raise ValueError("Audio is empty.")
    if not np.all(np.isfinite(array)):
        raise ValueError("Audio contains NaN or infinity.")
    return array


def _db(value: float) -> float:
    if value <= 0 or not np.isfinite(value):
        return float("-inf")
    return float(20.0 * np.log10(max(value, _EPS)))


def _band_energies(mono: np.ndarray, sample_rate: int) -> dict[str, float]:
    n = mono.shape[0]
    window = np.hanning(n)
    spectrum = np.fft.rfft(mono * window)
    frequencies = np.fft.rfftfreq(n, d=1.0 / sample_rate)

    coherent_gain = max(float(window.sum()), _EPS)
    amplitude = np.abs(spectrum) / coherent_gain
    power = amplitude**2

    result: dict[str, float] = {}
    nyquist = sample_rate / 2.0
    for low, high in _DEFAULT_BANDS:
        upper = min(float(high), nyquist)
        mask = (frequencies >= low) & (frequencies < upper)
        label = f"{low}-{high}Hz"
        if not np.any(mask):
            result[label] = float("-inf")
            continue
        band_rms = float(np.sqrt(np.mean(power[mask])))
        result[label] = _db(band_rms)
    return result


def _silence_edges(audio: np.ndarray, sample_rate: int, threshold_dbfs: float) -> tuple[float, float]:
    threshold = 10.0 ** (threshold_dbfs / 20.0)
    envelope = np.max(np.abs(audio), axis=1)
    active = np.flatnonzero(envelope > threshold)
    if active.size == 0:
        duration_ms = audio.shape[0] * 1000.0 / sample_rate
        return duration_ms, duration_ms

    leading_ms = active[0] * 1000.0 / sample_rate
    trailing_frames = audio.shape[0] - 1 - active[-1]
    trailing_ms = trailing_frames * 1000.0 / sample_rate
    return float(leading_ms), float(trailing_ms)


def analyze_array(
    audio: np.ndarray,
    sample_rate: int,
    *,
    true_peak_oversample: int = 4,
    silence_threshold_dbfs: float = -75.0,
) -> AudioMetrics:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")
    if true_peak_oversample < 1:
        raise ValueError("true_peak_oversample must be at least 1.")

    data = _as_audio_2d(audio)
    frames, channels = data.shape
    mono = np.mean(data, axis=1)

    meter = pyln.Meter(sample_rate)
    try:
        lufs_i = float(meter.integrated_loudness(data))
    except ValueError:
        lufs_i = float("-inf")

    try:
        lra_lu = float(meter.loudness_range(data))
    except (AttributeError, ValueError):
        lra_lu = 0.0

    sample_peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data**2)))
    crest_factor = _db(sample_peak) - _db(rms) if rms > 0 else 0.0

    if true_peak_oversample == 1:
        oversampled = data
    else:
        oversampled = resample_poly(
            data,
            up=true_peak_oversample,
            down=1,
            axis=0,
            padtype="line",
        )
    true_peak = float(np.max(np.abs(oversampled)))

    if channels >= 2:
        left = data[:, 0]
        right = data[:, 1]
        left_std = float(np.std(left))
        right_std = float(np.std(right))
        if left_std <= _EPS or right_std <= _EPS:
            stereo_correlation = 1.0
        else:
            stereo_correlation = float(np.corrcoef(left, right)[0, 1])

        mid = 0.5 * (left + right)
        side = 0.5 * (left - right)
        mid_rms = float(np.sqrt(np.mean(mid**2)))
        side_rms = float(np.sqrt(np.mean(side**2)))
        side_to_mid_db = _db(side_rms / max(mid_rms, _EPS))
    else:
        stereo_correlation = 1.0
        side_to_mid_db = float("-inf")

    leading_ms, trailing_ms = _silence_edges(data, sample_rate, silence_threshold_dbfs)

    return AudioMetrics(
        sample_rate_hz=int(sample_rate),
        channels=int(channels),
        frames=int(frames),
        duration_seconds=float(frames / sample_rate),
        lufs_i=lufs_i,
        lra_lu=lra_lu,
        sample_peak_dbfs=_db(sample_peak),
        true_peak_dbtp=_db(true_peak),
        rms_dbfs=_db(rms),
        crest_factor_db=float(crest_factor),
        dc_offset=tuple(float(value) for value in np.mean(data, axis=0)),
        clipped_sample_count=int(np.count_nonzero(np.abs(data) >= 1.0)),
        stereo_correlation=stereo_correlation,
        side_to_mid_db=side_to_mid_db,
        leading_silence_ms=leading_ms,
        trailing_silence_ms=trailing_ms,
        band_energy_db=_band_energies(mono, sample_rate),
    )


def analyze_file(
    path: str | Path,
    *,
    true_peak_oversample: int = 4,
    silence_threshold_dbfs: float = -75.0,
) -> AudioMetrics:
    audio_path = Path(path)
    data, sample_rate = sf.read(audio_path, always_2d=True, dtype="float64")
    return analyze_array(
        data,
        sample_rate,
        true_peak_oversample=true_peak_oversample,
        silence_threshold_dbfs=silence_threshold_dbfs,
    )
