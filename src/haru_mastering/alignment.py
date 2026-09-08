from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import correlate, correlation_lags


@dataclass(frozen=True)
class DelayDiagnostic:
    delay_samples: int
    window_estimates_samples: tuple[int, ...]
    window_peak_correlations: tuple[float, ...]
    confidence: float
    consistent: bool
    spread_samples: int


def _as_2d(audio: np.ndarray) -> np.ndarray:
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2:
        raise ValueError("Audio must have shape (frames,) or (frames, channels).")
    if not np.all(np.isfinite(array)):
        raise ValueError("Audio contains NaN or infinity.")
    return array


def _mono(audio: np.ndarray) -> np.ndarray:
    return np.mean(_as_2d(audio), axis=1)


def _estimate_window_delay(
    reference: np.ndarray,
    processed: np.ndarray,
    *,
    maximum_delay_samples: int,
) -> tuple[int, float]:
    ref = np.asarray(reference, dtype=np.float64)
    proc = np.asarray(processed, dtype=np.float64)
    frames = min(ref.size, proc.size)
    if frames < 16:
        raise ValueError("Audio window is too short to estimate delay.")

    ref = ref[:frames] - np.mean(ref[:frames])
    proc = proc[:frames] - np.mean(proc[:frames])
    ref_norm = float(np.linalg.norm(ref))
    proc_norm = float(np.linalg.norm(proc))
    if ref_norm <= 1e-15 or proc_norm <= 1e-15:
        raise ValueError("Delay cannot be estimated from a silent window.")

    correlation = correlate(proc / proc_norm, ref / ref_norm, mode="full", method="fft")
    lags = correlation_lags(proc.size, ref.size, mode="full")
    allowed = np.abs(lags) <= int(maximum_delay_samples)
    if not np.any(allowed):
        raise ValueError("No candidate lags are inside max_delay_ms.")

    allowed_indices = np.flatnonzero(allowed)
    local_index = int(np.argmax(correlation[allowed]))
    best_index = int(allowed_indices[local_index])
    return int(lags[best_index]), float(correlation[best_index])


def estimate_delay_samples(
    reference: np.ndarray,
    processed: np.ndarray,
    sample_rate: int,
    *,
    max_delay_ms: float = 100.0,
    analysis_seconds: float = 30.0,
) -> int:
    """Estimate delay where a positive value means processed audio starts later."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")
    if max_delay_ms < 0:
        raise ValueError("max_delay_ms must be non-negative.")
    if analysis_seconds <= 0:
        raise ValueError("analysis_seconds must be positive.")

    ref = _mono(reference)
    proc = _mono(processed)
    window_frames = min(
        ref.shape[0],
        proc.shape[0],
        max(1, int(round(sample_rate * analysis_seconds))),
    )
    maximum_delay_samples = int(round(sample_rate * max_delay_ms / 1000.0))
    delay, _ = _estimate_window_delay(
        ref[:window_frames],
        proc[:window_frames],
        maximum_delay_samples=maximum_delay_samples,
    )
    return delay


def estimate_delay_diagnostic(
    reference: np.ndarray,
    processed: np.ndarray,
    sample_rate: int,
    *,
    max_delay_ms: float = 100.0,
    window_count: int = 5,
    window_seconds: float = 6.0,
    consistency_tolerance_samples: int = 3,
) -> DelayDiagnostic:
    """Estimate delay at several positions and report confidence.

    A single correlation window can move a few samples because minimum-phase EQ,
    compression and the shape of the first transient alter the waveform.  This
    diagnostic samples the whole song and uses the median lag.  Large offsets
    are considered trustworthy only when most windows agree.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")
    if max_delay_ms < 0:
        raise ValueError("max_delay_ms must be non-negative.")
    if window_count <= 0:
        raise ValueError("window_count must be positive.")
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive.")
    if consistency_tolerance_samples < 0:
        raise ValueError("consistency_tolerance_samples must be non-negative.")

    ref = _mono(reference)
    proc = _mono(processed)
    total_frames = min(ref.size, proc.size)
    if total_frames < 16:
        raise ValueError("Audio is too short to estimate delay.")

    requested_window = max(16, int(round(sample_rate * float(window_seconds))))
    window_frames = min(total_frames, requested_window)
    maximum_start = max(0, total_frames - window_frames)
    count = min(int(window_count), max(1, total_frames // max(16, window_frames // 2)))
    if maximum_start == 0 or count == 1:
        starts = np.array([0], dtype=np.int64)
    else:
        starts = np.linspace(0, maximum_start, num=count, dtype=np.int64)

    maximum_delay_samples = int(round(sample_rate * max_delay_ms / 1000.0))
    estimates: list[int] = []
    peaks: list[float] = []
    for start in starts:
        end = int(start) + window_frames
        try:
            lag, peak = _estimate_window_delay(
                ref[int(start):end],
                proc[int(start):end],
                maximum_delay_samples=maximum_delay_samples,
            )
        except ValueError:
            continue
        estimates.append(int(lag))
        peaks.append(float(peak))

    if not estimates:
        raise ValueError("Delay could not be estimated from any analysis window.")

    median_delay = int(round(float(np.median(estimates))))
    deviations = np.abs(np.asarray(estimates, dtype=np.int64) - median_delay)
    inliers = deviations <= int(consistency_tolerance_samples)
    agreement = float(np.mean(inliers))
    inlier_estimates = np.asarray(estimates, dtype=np.int64)[inliers]
    spread = int(np.ptp(inlier_estimates)) if inlier_estimates.size > 1 else 0

    peak_values = np.asarray(peaks, dtype=np.float64)
    peak_quality = float(np.median(np.clip(peak_values[inliers], 0.0, 1.0))) if np.any(inliers) else 0.0
    confidence = float(np.clip(0.70 * agreement + 0.30 * peak_quality, 0.0, 1.0))
    minimum_agreement = 0.60 if len(estimates) >= 3 else 1.0
    consistent = bool(
        agreement >= minimum_agreement
        and spread <= max(1, int(consistency_tolerance_samples) * 2)
    )

    return DelayDiagnostic(
        delay_samples=median_delay,
        window_estimates_samples=tuple(estimates),
        window_peak_correlations=tuple(peaks),
        confidence=confidence,
        consistent=consistent,
        spread_samples=spread,
    )


def compensate_delay(
    processed: np.ndarray,
    delay_samples: int,
    *,
    target_frames: int | None = None,
) -> np.ndarray:
    """Remove positive delay or pad a negative delay while preserving channels."""
    data = _as_2d(processed)
    channels = data.shape[1]

    if delay_samples > 0:
        aligned = data[min(delay_samples, data.shape[0]) :]
    elif delay_samples < 0:
        aligned = np.vstack(
            [np.zeros((-delay_samples, channels), dtype=data.dtype), data]
        )
    else:
        aligned = data.copy()

    if target_frames is not None:
        if target_frames < 0:
            raise ValueError("target_frames must be non-negative.")
        if aligned.shape[0] < target_frames:
            aligned = np.vstack(
                [
                    aligned,
                    np.zeros((target_frames - aligned.shape[0], channels), dtype=aligned.dtype),
                ]
            )
        else:
            aligned = aligned[:target_frames]

    return aligned


def align_audio_file(
    processed_path: str | Path,
    delay_samples: int,
) -> Path:
    """Apply confirmed sample alignment to a rendered copy, never to the source."""
    target = Path(processed_path)
    audio, sample_rate = sf.read(target, always_2d=True, dtype="float64")
    aligned = compensate_delay(audio, int(delay_samples), target_frames=audio.shape[0])
    info = sf.info(target)
    subtype = info.subtype or "PCM_24"
    temporary = target.with_name(target.stem + ".align.tmp.wav")
    sf.write(temporary, aligned, sample_rate, subtype=subtype)
    temporary.replace(target)
    return target


def pad_tail(audio: np.ndarray, sample_rate: int, *, padding_ms: float = 500.0) -> np.ndarray:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")
    if padding_ms < 0:
        raise ValueError("padding_ms must be non-negative.")

    data = _as_2d(audio)
    padding_frames = int(round(sample_rate * padding_ms / 1000.0))
    if padding_frames == 0:
        return data.copy()
    return np.vstack(
        [data, np.zeros((padding_frames, data.shape[1]), dtype=data.dtype)]
    )


def trim_padded_tail(
    audio: np.ndarray,
    sample_rate: int,
    *,
    threshold_dbfs: float = -75.0,
    safety_ms: float = 100.0,
    minimum_frames: int = 0,
) -> np.ndarray:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")
    if safety_ms < 0:
        raise ValueError("safety_ms must be non-negative.")
    if minimum_frames < 0:
        raise ValueError("minimum_frames must be non-negative.")

    data = _as_2d(audio)
    threshold = 10.0 ** (threshold_dbfs / 20.0)
    envelope = np.max(np.abs(data), axis=1)
    active = np.flatnonzero(envelope > threshold)

    if active.size == 0:
        end = min(data.shape[0], minimum_frames)
    else:
        safety_frames = int(round(sample_rate * safety_ms / 1000.0))
        end = min(data.shape[0], int(active[-1]) + 1 + safety_frames)
        end = max(end, min(data.shape[0], minimum_frames))

    return data[:end].copy()
