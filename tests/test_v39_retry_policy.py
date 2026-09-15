from __future__ import annotations

from haru_mastering.analysis import AudioMetrics
from haru_mastering.retry_policy import (
    build_track_retry_policy,
    classify_dynamics_origin,
    dynamics_stats,
    performance_level,
    slowest_stage,
)


def _metrics(*, lra: float, crest: float, true_peak: float = -1.4) -> AudioMetrics:
    return AudioMetrics(
        sample_rate_hz=48000,
        channels=2,
        frames=48000 * 180,
        duration_seconds=180.0,
        lufs_i=-14.0,
        lra_lu=lra,
        sample_peak_dbfs=true_peak,
        true_peak_dbtp=true_peak,
        rms_dbfs=-18.0,
        crest_factor_db=crest,
        dc_offset=(0.0, 0.0),
        clipped_sample_count=0,
        stereo_correlation=0.95,
        side_to_mid_db=-18.0,
        leading_silence_ms=0.0,
        trailing_silence_ms=500.0,
        band_energy_db={},
    )


GATE = {
    "maximum_lra_reduction_lu": 0.80,
    "minimum_final_lra_lu": 3.50,
    "maximum_crest_factor_loss_db": 0.75,
}


def test_maximum_auto_rerenders_four_is_capped_for_v39_dynamics_policy():
    policy = build_track_retry_policy(
        mode="QUALITY+",
        resolved_maximum_auto_rerenders=4,
        max_fullness_render_passes=2,
    )

    assert policy.resolved_maximum_auto_rerenders == 4
    assert policy.dynamics_base_rerenders == 0
    assert policy.fullness_render_limit == 2
    assert policy.codec_maximum_auto_rerenders == 2
    assert policy.quality_gate_normal_limit == 1
    assert policy.quality_gate_fullness_retry_limit == 2
    assert policy.quality_gate_transparent_limit == 3


def test_v39_runtime_keeps_configured_dynamics_limit_separate_from_codec_cap():
    import Suno15_Mastering_v3_9 as app

    key = app.composite_key("TOKYO_CHILL", "CHILL_RAP")
    _gate, auto, _profile = app.v32._settings(key)

    assert auto["maximumAutoRerenders"] == 2
    assert auto["codecCeilingStepDb"] == 0.5


def test_tokyo_chill_chillrap_dynamics_retry_is_bounded_by_origin():
    source = _metrics(lra=4.50, crest=9.0)
    base = _metrics(lra=4.16, crest=8.8)
    final = _metrics(lra=3.45, crest=8.7, true_peak=-1.01)

    assert dynamics_stats(source, base, GATE).risky is False
    final_stats = dynamics_stats(source, final, GATE)

    assert round(final_stats.lra_reduction_lu, 2) == 1.05
    assert classify_dynamics_origin(source=source, base=base, final=final, gate_kwargs=GATE) == "fullness"


def test_base_dynamics_risk_goes_to_transparent_fallback_classification():
    source = _metrics(lra=4.80, crest=9.0)
    base = _metrics(lra=3.20, crest=8.9)
    final = _metrics(lra=3.00, crest=8.8)

    assert dynamics_stats(source, base, GATE).risky is True
    assert classify_dynamics_origin(source=source, base=base, final=final, gate_kwargs=GATE) == "base"


def test_performance_warning_levels_and_slowest_stage():
    assert performance_level(119.9) == ""
    assert performance_level(120.1) == "warning"
    assert performance_level(240.1) == "error"

    assert slowest_stage({"base": 12.0, "Quality Gate": 46.2}) == ("Quality Gate", 46.2)
