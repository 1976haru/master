from __future__ import annotations

import numpy as np
from scipy.signal import correlate, correlation_lags


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
    if window_frames < 16:
        raise ValueError("Audio is too short to estimate delay.")

    ref = ref[:window_frames] - np.mean(ref[:window_frames])
    proc = proc[:window_frames] - np.mean(proc[:window_frames])

    ref_norm = np.linalg.norm(ref)
    proc_norm = np.linalg.norm(proc)
    if ref_norm == 0 or proc_norm == 0:
        raise ValueError("Delay cannot be estimated from silent audio.")

    correlation = correlate(proc / proc_norm, ref / ref_norm, mode="full", method="fft")
    lags = correlation_lags(proc.size, ref.size, mode="full")

    max_delay_samples = int(round(sample_rate * max_delay_ms / 1000.0))
    allowed = np.abs(lags) <= max_delay_samples
    if not np.any(allowed):
        raise ValueError("No candidate lags are inside max_delay_ms.")

    allowed_indices = np.flatnonzero(allowed)
    best_index = allowed_indices[int(np.argmax(correlation[allowed]))]
    return int(lags[best_index])


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
