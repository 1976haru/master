from __future__ import annotations

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_array, analyze_file
from haru_mastering.transparent import decide_gain_only, render_gain_only


def _fixture() -> np.ndarray:
    sample_rate = 48000
    t = np.arange(sample_rate * 4, dtype=np.float64) / sample_rate
    envelope = 0.12 + 0.55 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.7 * t))
    left = envelope * np.sin(2 * np.pi * (220 + 30 * np.sin(2 * np.pi * 0.3 * t)) * t)
    right = envelope * np.sin(2 * np.pi * (330 + 20 * np.sin(2 * np.pi * 0.2 * t)) * t + 0.2)
    return np.column_stack((left, right))


def test_gain_only_decision_respects_peak_safety_margin():
    decision = decide_gain_only(
        source_lufs=-15.5,
        source_true_peak_dbtp=-2.67,
        target_lufs=-14.0,
        true_peak_ceiling_dbtp=-1.20,
        safety_margin_db=0.05,
    )

    assert decision.applied_gain_db < 1.5
    assert decision.effective_target_lufs < -14.0
    assert decision.projected_final_tp_dbtp <= -1.25


def test_gain_only_preserves_lra_and_crest_for_positive_gain(tmp_path):
    sample_rate = 48000
    audio = _fixture()
    source = tmp_path / "source.wav"
    destination = tmp_path / "positive.wav"
    sf.write(source, audio, sample_rate, subtype="PCM_24")

    before = analyze_array(audio, sample_rate)
    ok, error, after, _processed, _rate = render_gain_only(
        source,
        destination,
        gain_db=1.0,
        true_peak_oversample=4,
    )

    assert ok, error
    assert after is not None
    assert abs(after.lra_lu - before.lra_lu) <= 0.05
    assert abs(after.crest_factor_db - before.crest_factor_db) <= 0.10
    assert abs((after.lufs_i - before.lufs_i) - 1.0) <= 0.05
    assert abs((after.true_peak_dbtp - before.true_peak_dbtp) - 1.0) <= 0.05


def test_gain_only_preserves_lra_and_crest_for_negative_gain(tmp_path):
    sample_rate = 48000
    audio = _fixture()
    source = tmp_path / "source.wav"
    destination = tmp_path / "negative.wav"
    sf.write(source, audio, sample_rate, subtype="PCM_24")

    before = analyze_file(source)
    ok, error, after, _processed, _rate = render_gain_only(
        source,
        destination,
        gain_db=-2.0,
        true_peak_oversample=4,
    )

    assert ok, error
    assert after is not None
    assert abs(after.lra_lu - before.lra_lu) <= 0.05
    assert abs(after.crest_factor_db - before.crest_factor_db) <= 0.10
    assert abs((after.lufs_i - before.lufs_i) + 2.0) <= 0.05
    assert abs((after.true_peak_dbtp - before.true_peak_dbtp) + 2.0) <= 0.05
