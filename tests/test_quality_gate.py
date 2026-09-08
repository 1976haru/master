from __future__ import annotations

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_file
from haru_mastering.quality_gate import evaluate_master


def _music_like_noise(sr: int, seconds: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mono = rng.normal(0.0, 0.03, size=sr * seconds)
    side = rng.normal(0.0, 0.003, size=sr * seconds)
    audio = np.column_stack([mono + side, mono - side])
    return audio - np.mean(audio, axis=0, keepdims=True)


def test_quality_gate_passes_identical_audio(tmp_path):
    sr = 48000
    audio = _music_like_noise(sr, 2, 42)
    source = tmp_path / "source.wav"
    processed = tmp_path / "processed.wav"
    sf.write(source, audio, sr, subtype="PCM_24")
    sf.write(processed, audio, sr, subtype="PCM_24")

    metrics = analyze_file(processed)
    result = evaluate_master(
        source,
        processed,
        target_lufs_i=metrics.lufs_i,
        true_peak_ceiling_dbtp=metrics.true_peak_dbtp + 0.1,
    )

    assert result.status == "PASS", result.issues
    assert result.residual_delay_samples == 0
    assert result.low_band_stereo_correlation >= 0.70


def test_quality_gate_detects_240_sample_delay(tmp_path):
    sr = 48000
    audio = _music_like_noise(sr, 2, 7)
    delayed = np.vstack([np.zeros((240, 2)), audio[:-240]])
    source = tmp_path / "source.wav"
    processed = tmp_path / "processed.wav"
    sf.write(source, audio, sr, subtype="PCM_24")
    sf.write(processed, delayed, sr, subtype="PCM_24")

    metrics = analyze_file(processed)
    result = evaluate_master(
        source,
        processed,
        target_lufs_i=metrics.lufs_i,
        true_peak_ceiling_dbtp=metrics.true_peak_dbtp + 0.1,
    )

    assert result.status == "FAIL"
    assert result.residual_delay_samples == 240
    assert any("residual processing delay" in issue for issue in result.issues)
