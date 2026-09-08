import numpy as np

from haru_mastering.alignment import (
    compensate_delay,
    estimate_delay_samples,
    pad_tail,
    trim_padded_tail,
)


def test_delay_estimation_and_compensation():
    sample_rate = 48000
    rng = np.random.default_rng(42)
    reference = rng.normal(0.0, 0.1, size=(sample_rate, 2))
    delay = 240
    processed = np.vstack([np.zeros((delay, 2)), reference])

    measured = estimate_delay_samples(
        reference,
        processed,
        sample_rate,
        max_delay_ms=20,
        analysis_seconds=0.9,
    )
    assert measured == delay

    aligned = compensate_delay(processed, measured, target_frames=reference.shape[0])
    np.testing.assert_allclose(aligned, reference, atol=1e-10)


def test_tail_padding_and_safe_trim():
    sample_rate = 1000
    audio = np.ones((1000, 2), dtype=np.float64) * 0.1
    padded = pad_tail(audio, sample_rate, padding_ms=500)
    assert padded.shape == (1500, 2)

    trimmed = trim_padded_tail(
        padded,
        sample_rate,
        threshold_dbfs=-75,
        safety_ms=100,
        minimum_frames=audio.shape[0],
    )
    assert trimmed.shape == (1100, 2)
