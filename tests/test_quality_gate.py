from __future__ import annotations

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_file
from haru_mastering.quality_gate import evaluate_master


def test_quality_gate_passes_identical_audio(tmp_path):
    sr = 48000
    rng = np.random.default_rng(42)
    audio = rng.normal(0.0, 0.03, size=(sr * 2, 2))
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

    assert result.status == "PASS"
    assert result.residual_delay_samples == 0


def test_quality_gate_detects_240_sample_delay(tmp_path):
    sr = 48000
    rng = np.random.default_rng(7)
    audio = rng.normal(0.0, 0.03, size=(sr * 2, 2))
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
