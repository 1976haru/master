import numpy as np
import soundfile as sf

from haru_mastering.alignment import (
    align_audio_file,
    compensate_delay,
    estimate_delay_diagnostic,
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


def test_multi_window_delay_diagnostic_is_confident_for_real_delay():
    sample_rate = 48000
    rng = np.random.default_rng(123)
    reference = rng.normal(0.0, 0.08, size=(sample_rate * 8, 2))
    delay = 240
    processed = np.vstack([np.zeros((delay, 2)), reference[:-delay]])

    diagnostic = estimate_delay_diagnostic(
        reference,
        processed,
        sample_rate,
        max_delay_ms=20,
        window_count=5,
        window_seconds=1.0,
    )

    assert diagnostic.delay_samples == delay
    assert diagnostic.consistent is True
    assert diagnostic.confidence >= 0.70
    assert len(diagnostic.window_estimates_samples) >= 3


def test_align_audio_file_preserves_length_and_removes_delay(tmp_path):
    sample_rate = 48000
    rng = np.random.default_rng(321)
    reference = rng.normal(0.0, 0.05, size=(sample_rate * 2, 2))
    delay = 240
    processed = np.vstack([np.zeros((delay, 2)), reference[:-delay]])
    path = tmp_path / "processed.wav"
    sf.write(path, processed, sample_rate, subtype="PCM_24")

    align_audio_file(path, delay)
    aligned, aligned_sr = sf.read(path, always_2d=True, dtype="float64")

    assert aligned_sr == sample_rate
    assert aligned.shape == processed.shape
    np.testing.assert_allclose(aligned[:-delay], reference[:-delay], atol=2e-7)


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
