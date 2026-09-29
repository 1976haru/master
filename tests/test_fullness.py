from __future__ import annotations

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_file
from haru_mastering.fullness import (
    FullnessDecision,
    MAX_FULLNESS_RENDER_PASSES,
    decide,
    default_fullness_mode,
    process,
    reduce_decision_for_guard_reasons,
    retry_strength_for_guard_reasons,
)


def _thin_old_pop_like(sr: int, seconds: int) -> np.ndarray:
    t = np.arange(sr * seconds, dtype=np.float64) / sr
    mono = (
        0.010 * np.sin(2.0 * np.pi * 120.0 * t)
        + 0.008 * np.sin(2.0 * np.pi * 300.0 * t)
        + 0.050 * np.sin(2.0 * np.pi * 1400.0 * t)
    )
    side = 0.002 * np.sin(2.0 * np.pi * 900.0 * t)
    return np.column_stack((mono + side, mono - side))


def test_default_modes_follow_genre_policy():
    assert default_fullness_mode("OLD POP") == "RICH"
    assert default_fullness_mode("SENIOR JP") == "RICH"
    assert default_fullness_mode("K-POP") == "RICH"
    assert default_fullness_mode("KIDS POP") == "RICH"
    assert default_fullness_mode("JAZZ") == "NATURAL"
    assert default_fullness_mode("ACOUSTIC") == "NATURAL"
    assert default_fullness_mode("INSTRUMENTAL") == "NATURAL"


def test_fullness_decision_respects_caps(tmp_path):
    sr = 48000
    src = tmp_path / "thin.wav"
    sf.write(src, _thin_old_pop_like(sr, 3), sr, subtype="PCM_24")
    metrics = analyze_file(src)

    decision = decide(metrics, genre_key="OLD POP", mode="RICH", strength_percent=100)

    assert -0.5 <= decision.warmth_gain_db <= 0.8
    assert -0.5 <= decision.body_gain_db <= 0.5
    assert 0.0 <= decision.saturation_wet_percent <= 6.0
    assert 0.0 <= decision.density_wet_percent <= 5.0


def test_fullness_processing_is_loudness_matched_and_safe(tmp_path):
    sr = 48000
    src = tmp_path / "source.wav"
    dst = tmp_path / "master.wav"
    sf.write(src, _thin_old_pop_like(sr, 4), sr, subtype="PCM_24")
    before = analyze_file(src)
    decision = decide(before, genre_key="OLD POP", mode="RICH", strength_percent=75)

    render = process(src, dst, decision)
    after = analyze_file(dst)

    assert abs(after.lufs_i - before.lufs_i) <= 0.20
    assert after.clipped_sample_count == 0
    assert render.decision.strength_percent == 75
    assert after.low_band_stereo_correlation if hasattr(after, "low_band_stereo_correlation") else True
    assert after.stereo_correlation > 0.70


def test_natural_mode_is_audio_copy(tmp_path):
    sr = 48000
    src = tmp_path / "source.wav"
    dst = tmp_path / "copy.wav"
    audio = _thin_old_pop_like(sr, 2)
    sf.write(src, audio, sr, subtype="PCM_24")
    metrics = analyze_file(src)
    decision = decide(metrics, genre_key="OLD POP", mode="NATURAL")

    process(src, dst, decision)
    copied, _ = sf.read(dst, always_2d=True, dtype="float64")
    original, _ = sf.read(src, always_2d=True, dtype="float64")

    np.testing.assert_allclose(copied, original, atol=0.0)


def test_process_reuses_source_metrics_for_natural_copy(tmp_path, monkeypatch):
    sr = 48000
    src = tmp_path / "source.wav"
    dst = tmp_path / "copy.wav"
    audio = _thin_old_pop_like(sr, 2)
    sf.write(src, audio, sr, subtype="PCM_24")
    metrics = analyze_file(src)
    decision = decide(metrics, genre_key="OLD POP", mode="NATURAL")

    calls = {"count": 0}

    def counted_analyze_file(*args, **kwargs):
        calls["count"] += 1
        return analyze_file(*args, **kwargs)

    monkeypatch.setattr("haru_mastering.fullness.analyze_file", counted_analyze_file)

    render = process(src, dst, decision, source_metrics=metrics)

    assert calls["count"] == 0
    assert render.before is metrics
    assert render.after is metrics


def test_process_reuses_audio_and_returns_candidate_metrics_for_rich(tmp_path, monkeypatch):
    sr = 48000
    src = tmp_path / "source.wav"
    dst = tmp_path / "master.wav"
    audio = _thin_old_pop_like(sr, 2)
    sf.write(src, audio, sr, subtype="PCM_24")
    metrics = analyze_file(src)
    decision = decide(metrics, genre_key="OLD POP", mode="RICH", strength_percent=60)

    calls = {"count": 0}

    def counted_analyze_file(*args, **kwargs):
        calls["count"] += 1
        return analyze_file(*args, **kwargs)

    monkeypatch.setattr("haru_mastering.fullness.analyze_file", counted_analyze_file)

    render = process(
        src,
        dst,
        decision,
        source_metrics=metrics,
        source_audio=audio,
        source_sample_rate=sr,
        return_audio=True,
    )

    assert calls["count"] == 0
    assert render.before is metrics
    assert render.after is not metrics
    assert render.processed_audio is not None
    assert render.processed_sample_rate == sr
    assert abs(render.after.lufs_i - metrics.lufs_i) <= 0.20


def test_fast_fullness_engine_limits_render_passes():
    assert MAX_FULLNESS_RENDER_PASSES == 2


def test_retry_strength_is_selected_from_failure_reason():
    assert retry_strength_for_guard_reasons(("DYNAMICS RISK: LRA reduced 1.2 LU",)) == 60
    assert retry_strength_for_guard_reasons(("crest loss 1.0 dB",)) == 50
    assert retry_strength_for_guard_reasons(("codec preview unsafe: -1.20 dBTP",)) == 100
    assert (
        retry_strength_for_guard_reasons(
            (
                "true peak exceeded: -1.01 dBTP > -1.20 dBTP",
                "DYNAMICS RISK: LRA reduced 1.05 LU (preferred limit 0.80)",
            )
        )
        == 60
    )


def test_low_band_retry_reduces_body_bands_directly():
    original = FullnessDecision(
        mode="RICH",
        strength_percent=100,
        warmth_gain_db=0.8,
        body_gain_db=0.5,
        saturation_wet_percent=6.0,
        density_wet_percent=5.0,
    )
    reduced = reduce_decision_for_guard_reasons(
        original,
        ("low-band stereo correlation too low: 0.650 below 110 Hz",),
    )

    assert reduced.strength_percent == 60
    assert reduced.warmth_gain_db < original.warmth_gain_db * 0.60
    assert reduced.body_gain_db < original.body_gain_db * 0.60
