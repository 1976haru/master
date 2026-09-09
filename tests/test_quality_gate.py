from __future__ import annotations

import numpy as np
import soundfile as sf

from haru_mastering.alignment import DelayDiagnostic
from haru_mastering.analysis import analyze_file
from haru_mastering.auto_finish import apply_click_safe_fade
from haru_mastering.quality_gate import (
    classify_delay_diagnostic,
    classify_tail_silence_difference,
    evaluate_master,
    lra_dynamics_risk,
)


def _music_like_noise(sr: int, seconds: int, seed: int, *, safe_tail: bool = True) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mono = rng.normal(0.0, 0.03, size=sr * seconds)
    side = rng.normal(0.0, 0.003, size=sr * seconds)
    audio = np.column_stack([mono + side, mono - side])
    audio = audio - np.mean(audio, axis=0, keepdims=True)
    if safe_tail:
        fade_frames = min(audio.shape[0], int(round(sr * 0.10)))
        audio[-fade_frames:] *= np.linspace(1.0, 0.0, fade_frames)[:, None]
        audio[-1] = 0.0
    return audio


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
    assert result.delay_classification == "PASS"
    assert result.low_band_stereo_correlation >= 0.70
    assert result.tail_hard_cut is False


def test_quality_gate_keeps_four_sample_estimator_shift_as_info(tmp_path):
    sr = 48000
    audio = _music_like_noise(sr, 4, 11)
    shifted = np.vstack([audio[4:], np.zeros((4, 2), dtype=np.float64)])
    source = tmp_path / "source.wav"
    processed = tmp_path / "processed.wav"
    sf.write(source, audio, sr, subtype="PCM_24")
    sf.write(processed, shifted, sr, subtype="PCM_24")

    metrics = analyze_file(processed)
    result = evaluate_master(
        source,
        processed,
        target_lufs_i=metrics.lufs_i,
        true_peak_ceiling_dbtp=metrics.true_peak_dbtp + 0.1,
        delay_window_seconds=0.5,
    )

    assert result.status == "PASS", result.issues
    assert result.residual_delay_samples == -4
    assert result.delay_classification == "INFO"
    assert "below correction threshold" in result.delay_note


def test_delay_between_nine_and_forty_seven_is_report_only():
    diagnostic = DelayDiagnostic(
        delay_samples=20,
        window_estimates_samples=(20, 20, 19, 20, 21),
        window_peak_correlations=(0.9, 0.9, 0.9, 0.9, 0.9),
        confidence=0.97,
        consistent=True,
        spread_samples=2,
    )
    classification, note = classify_delay_diagnostic(diagnostic)
    assert classification == "WARN"
    assert "no audio shift applied" in note


def test_quality_gate_detects_240_sample_delay(tmp_path):
    sr = 48000
    audio = _music_like_noise(sr, 4, 7)
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
        delay_window_seconds=0.5,
    )

    assert result.status == "FAIL"
    assert result.residual_delay_samples == 240
    assert result.delay_classification == "FAIL"
    assert result.delay_consistent is True
    assert result.delay_confidence >= 0.70
    assert any("residual processing delay" in issue for issue in result.issues)


def test_quality_gate_detects_and_repairs_hard_cut_tail(tmp_path):
    sr = 48000
    audio = _music_like_noise(sr, 2, 99, safe_tail=False)
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
    assert result.status == "FAIL"
    assert result.tail_hard_cut is True
    assert any(issue.startswith("TAIL HARD CUT") for issue in result.issues)

    apply_click_safe_fade(processed, fade_ms=25.0)
    repaired_metrics = analyze_file(processed)
    repaired = evaluate_master(
        source,
        processed,
        target_lufs_i=repaired_metrics.lufs_i,
        true_peak_ceiling_dbtp=repaired_metrics.true_peak_dbtp + 0.1,
    )
    assert repaired.tail_hard_cut is False
    assert not any(issue.startswith("TAIL HARD CUT") for issue in repaired.issues)


def test_minor_safe_tail_silence_difference_is_info_not_warn():
    classification, note = classify_tail_silence_difference(
        source_trailing_silence_ms=904.35,
        processed_trailing_silence_ms=875.85,
        duration_delta_ms=0.0,
        tail_hard_cut=False,
        tail_energetic_end=False,
        tail_last_sample_dbfs=float("-inf"),
    )
    assert classification == "INFO"
    assert "28.5 ms" in note
    assert "silent and safe" in note


def test_larger_tail_silence_difference_remains_warn():
    classification, note = classify_tail_silence_difference(
        source_trailing_silence_ms=950.0,
        processed_trailing_silence_ms=850.0,
        duration_delta_ms=0.0,
        tail_hard_cut=False,
        tail_energetic_end=False,
        tail_last_sample_dbfs=float("-inf"),
    )
    assert classification == "WARN"
    assert "100.0 ms" in note


def test_unsafe_tail_difference_remains_warn_even_below_fifty_ms():
    classification, _ = classify_tail_silence_difference(
        source_trailing_silence_ms=904.35,
        processed_trailing_silence_ms=875.85,
        duration_delta_ms=0.0,
        tail_hard_cut=True,
        tail_energetic_end=False,
        tail_last_sample_dbfs=-20.0,
    )
    assert classification == "WARN"


def test_large_lra_change_is_safe_when_final_dynamics_are_healthy():
    assert lra_dynamics_risk(
        lra_reduction_lu=1.07,
        final_lra_lu=4.43,
        crest_factor_loss_db=-1.26,
        maximum_lra_reduction_lu=0.60,
        minimum_final_lra_lu=3.50,
        maximum_crest_factor_loss_db=0.75,
    ) is False


def test_large_lra_change_fails_when_final_lra_collapses():
    assert lra_dynamics_risk(
        lra_reduction_lu=1.10,
        final_lra_lu=2.80,
        crest_factor_loss_db=0.10,
        maximum_lra_reduction_lu=0.60,
        minimum_final_lra_lu=3.50,
        maximum_crest_factor_loss_db=0.75,
    ) is True


def test_large_lra_change_fails_when_crest_collapses():
    assert lra_dynamics_risk(
        lra_reduction_lu=0.95,
        final_lra_lu=4.20,
        crest_factor_loss_db=1.10,
        maximum_lra_reduction_lu=0.60,
        minimum_final_lra_lu=3.50,
        maximum_crest_factor_loss_db=0.75,
    ) is True
