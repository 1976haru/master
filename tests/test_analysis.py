import numpy as np

from haru_mastering.analysis import analyze_array


def test_analyze_stereo_sine():
    sample_rate = 48000
    seconds = 1.0
    frames = int(sample_rate * seconds)
    t = np.arange(frames) / sample_rate
    sine = 0.1 * np.sin(2 * np.pi * 440 * t)
    audio = np.column_stack([sine, sine])

    metrics = analyze_array(audio, sample_rate)

    assert metrics.sample_rate_hz == sample_rate
    assert metrics.channels == 2
    assert metrics.frames == frames
    assert metrics.clipped_sample_count == 0
    assert metrics.stereo_correlation > 0.999
    assert -20.2 < metrics.sample_peak_dbfs < -19.8
    assert metrics.true_peak_dbtp <= -19.7
    assert metrics.leading_silence_ms < 1.0
    assert metrics.trailing_silence_ms < 1.0


def test_silence_is_handled():
    sample_rate = 48000
    audio = np.zeros((sample_rate, 1), dtype=np.float64)
    metrics = analyze_array(audio, sample_rate)

    assert metrics.lufs_i == float("-inf")
    assert metrics.sample_peak_dbfs == float("-inf")
    assert metrics.clipped_sample_count == 0
    assert metrics.leading_silence_ms == 1000.0
    assert metrics.trailing_silence_ms == 1000.0
