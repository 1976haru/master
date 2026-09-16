from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import soundfile as sf

from haru_mastering.analysis import AudioMetrics
from haru_mastering.fullness import FullnessDecision, peak_safety_trim_db
from haru_mastering.preflight import decide_preflight
from haru_mastering.quality_gate import classify_tail_silence_difference


def _metrics(
    *,
    lufs: float,
    tp: float,
    lra: float,
    crest: float = 8.0,
    clipped: int = 0,
) -> AudioMetrics:
    return AudioMetrics(
        sample_rate_hz=48000,
        channels=2,
        frames=48000,
        duration_seconds=1.0,
        lufs_i=lufs,
        lra_lu=lra,
        sample_peak_dbfs=min(tp, 0.0),
        true_peak_dbtp=tp,
        rms_dbfs=-22.0,
        crest_factor_db=crest,
        dc_offset=(0.0, 0.0),
        clipped_sample_count=clipped,
        stereo_correlation=0.95,
        side_to_mid_db=-12.0,
        leading_silence_ms=0.0,
        trailing_silence_ms=900.0,
        band_energy_db={},
    )


PROFILE = {
    "targetLufsI": -14.0,
    "truePeakCeilingDbtp": -1.20,
    "minimumTargetLufsI": -16.0,
    "maxProjectedPeakReductionDb": 1.5,
    "maximumLoudnessConcessionLu": 2.0,
    "compressionTransparentMarginLu": 0.5,
    "compressionReducedMarginLu": 1.0,
    "compressionReducedScale": 0.35,
}


def _decide(metrics: AudioMetrics):
    return decide_preflight(
        metrics,
        PROFILE,
        configured_target_lufs=-14.0,
        true_peak_ceiling_dbtp=-1.20,
        minimum_final_lra_lu=3.5,
    )


def test_preflight_reduces_target_when_peak_pressure_is_high():
    decision = _decide(_metrics(lufs=-15.57, tp=0.55, lra=5.68, clipped=9))

    assert decision.adaptive_target_lufs < -14.0
    assert decision.projected_peak_reduction_db > 3.0
    assert "source peak pressure" in decision.reasons


def test_preflight_keeps_target_when_headroom_is_safe():
    decision = _decide(_metrics(lufs=-15.50, tp=-4.0, lra=5.0))

    assert decision.adaptive_target_lufs == -14.0
    assert decision.compression_mode == "PROFILE"


def test_preflight_bypasses_compression_for_low_lra_source():
    decision = _decide(_metrics(lufs=-15.50, tp=-2.67, lra=3.75))

    assert decision.adaptive_target_lufs == -14.0
    assert decision.dynamic_margin_lu == 0.25
    assert decision.compression_mode == "TRANSPARENT"
    assert decision.compression_scale == 0.0


def test_blue_seat_profile_does_not_force_minus14():
    decision = _decide(_metrics(lufs=-15.57, tp=0.55, lra=5.68, clipped=9))

    assert -16.0 <= decision.adaptive_target_lufs <= -15.7
    assert decision.loudness_concession_lu > 1.0


def test_river_between_stations_peak_pressure():
    decision = _decide(_metrics(lufs=-15.55, tp=1.03, lra=5.03, clipped=9))

    assert decision.projected_peak_reduction_db > 3.5
    assert decision.adaptive_target_lufs == -16.0
    assert decision.source_peak_stressed is True
    assert decision.gain_only_recommended is True
    assert decision.effective_target_lufs < -16.0


def test_back_to_window_low_lra_compression_protection():
    decision = _decide(_metrics(lufs=-15.50, tp=-2.67, lra=3.75))

    assert decision.projected_peak_reduction_db < 0.1
    assert decision.compression_mode == "TRANSPARENT"
    assert decision.gain_only_recommended is True


def test_peak_stressed_target_can_require_safety_floor_review():
    decision = _decide(_metrics(lufs=-15.0, tp=3.5, lra=5.0, clipped=1))

    assert decision.source_peak_stressed is True
    assert decision.safety_floor_requires_review is True
    assert decision.effective_target_lufs == -18.0


def test_v39_final_csv_schema_preserves_legacy_fullness_and_adaptive_fields():
    import Suno15_Mastering_v3_9 as app

    required = {
        "final_LRA",
        "final_lufs_delta_lu",
        "final_lufs_within_tolerance",
        "codec_strategy",
        "final_metrics_sync_version",
        "app_version",
        "fullness_mode",
        "fullness_strength_percent",
        "fullness_auto_reduced",
        "fullness_retry_count",
        "configured_target_LUFS",
        "adaptive_target_LUFS",
        "effective_target_LUFS",
        "compression_mode",
        "final_sound_mode",
        "final_fullness_strength",
        "release_disposition",
    }

    assert required.issubset(set(app.TRACK_REPORT_FIELDS))


def test_gain_only_fallback_updates_runtime_effective_target():
    import Suno15_Mastering_v3_9 as app

    state = app.RuntimeTargetState(-14.0, -14.45, -15.99, -15.99)
    gate = {"target_lufs_i": -15.99}
    profile = {"targetLufsI": -15.99}
    decision = SimpleNamespace(effective_target_lufs=-16.00)

    target = app.AppV39._sync_runtime_target(
        state,
        gate,
        profile,
        decision,
        reason="dynamics_gain_only_fallback",
    )

    assert target == -16.00
    assert gate["target_lufs_i"] == -16.00
    assert profile["targetLufsI"] == -16.00
    assert state.reason == "dynamics_gain_only_fallback"


def test_attempted_steps_reports_gain_only_and_dc_cleanup():
    import Suno15_Mastering_v3_9 as app

    steps = app._attempted_steps_from_row(
        {
            "gain_only_render_count": "1",
            "dc_correction_count": "1",
            "fullness_render_count": "0",
            "codec_check_count": "0",
        }
    )

    assert "다이내믹 보존형 Gain-only 마스터링" in steps
    assert "DC offset correction" in steps


def test_v39_fullness_refresh_preserves_existing_final_metrics(tmp_path):
    import csv
    import Suno15_Mastering_v3_9 as app

    output = tmp_path / "out"
    output.mkdir()
    csv_path = output / "mastering_report.csv"
    fields = [
        "track",
        "final_LRA",
        "final_LUFS",
        "final_lufs_delta_lu",
        "fullness_mode",
        "app_version",
        "final_metrics_sync_version",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "track": "track.wav",
                "final_LRA": "3.75",
                "final_LUFS": "-15.73",
                "final_lufs_delta_lu": "+0.01",
                "fullness_mode": "RICH",
                "app_version": "v3.8",
                "final_metrics_sync_version": "v3.7.2",
            }
        )

    app.v38.patch_csv_with_fullness(output, metadata={})
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["final_LRA"] == "3.75"
    assert row["final_LUFS"] == "-15.73"
    assert row["final_lufs_delta_lu"] == "+0.01"
    assert row["fullness_mode"] == "RICH"
    assert row["app_version"] == "v3.9"
    assert row["final_metrics_sync_version"] == "v3.9"


def test_true_peak_only_fullness_issue_uses_micro_trim():
    metrics = _metrics(lufs=-14.0, tp=-1.10, lra=4.2)

    trim_db = peak_safety_trim_db(
        metrics,
        true_peak_ceiling_dbtp=-1.20,
        safety_margin_db=0.05,
        maximum_trim_db=0.50,
    )

    assert trim_db == -0.15


def test_fullness_survives_small_true_peak_overage(tmp_path, monkeypatch):
    import Suno15_Mastering_v3_9 as app

    sr = 48000
    amplitude = 10 ** (-1.10 / 20.0)
    audio = np.full((sr // 10, 2), amplitude, dtype=np.float64)
    source = tmp_path / "source.wav"
    base = tmp_path / "base.wav"
    destination = tmp_path / "master.wav"
    sf.write(source, audio, sr, subtype="PCM_24")
    sf.write(base, audio, sr, subtype="PCM_24")

    instance = app.AppV39.__new__(app.AppV39)
    instance.after = lambda *_args: None
    instance._stage_log = lambda *_args: None
    instance._fullness_mode = lambda *_args: "RICH"
    instance._repair_tail = lambda *_args: SimpleNamespace(mode="none")
    instance._fullness_metadata = {}
    instance._fullness_render_count = 0

    before = _metrics(lufs=-14.0, tp=-1.10, lra=4.2)
    source_ctx = app.SourceContext(audio=audio, sample_rate=sr, metrics=before, raw={})
    base_ctx = app.AudioContext(audio=audio, sample_rate=sr, metrics=before)
    counters = app.TrackCounters(fullness_render_limit=1)
    decision = FullnessDecision("RICH", 50, 0.0, 0.0, 0.0, 0.0)

    def fake_decision(*_args, **_kwargs):
        return decision

    def fake_render(_base, dst, render_decision, _base_ctx, _timing, render_counters, **_kwargs):
        sf.write(dst, audio, sr, subtype="PCM_24")
        render_counters.fullness_render_count += 1
        return SimpleNamespace(
            decision=render_decision,
            after=before,
            processed_audio=audio,
            processed_sample_rate=sr,
        )

    def fake_evaluate(_source, _candidate, _gate, _source_ctx, eval_counters, **kwargs):
        eval_counters.quality_gate_count += 1
        eval_counters.normal_quality_gate_count += 1
        processed = kwargs.get("processed_metrics") or before
        if processed.true_peak_dbtp > -1.20:
            return SimpleNamespace(
                status="FAIL",
                issues=("true peak exceeded: -1.10 dBTP > -1.20 dBTP",),
                warnings=(),
                processed=processed,
            )
        return SimpleNamespace(status="PASS", issues=(), warnings=(), processed=processed)

    monkeypatch.setattr(instance, "_fullness_decision", fake_decision)
    monkeypatch.setattr(instance, "_render_fullness_candidate", fake_render)
    monkeypatch.setattr(instance, "_evaluate_candidate", fake_evaluate)

    candidate = instance._finish_candidate(
        source,
        base,
        destination,
        "CG_TOKYO_CHILL__CHILL_RAP",
        {"true_peak_ceiling_dbtp": -1.20, "true_peak_oversample": 4},
        {},
        {"fullness": {"defaultStrengthPercent": 50}},
        source_ctx,
        base_ctx,
        [],
        counters,
        max_fullness_passes=1,
        track_index=4,
        track_total=15,
    )

    assert candidate.result.status == "PASS"
    assert counters.accepted_sound_mode == "RICH"
    assert counters.accepted_fullness_strength == 50
    assert counters.accepted_peak_trim_db < 0.0
    assert counters.fullness_render_count == 1


def test_safe_silent_tail_67ms_is_info():
    classification, note = classify_tail_silence_difference(
        source_trailing_silence_ms=900.0,
        processed_trailing_silence_ms=832.9,
        duration_delta_ms=0.0,
        tail_hard_cut=False,
        tail_energetic_end=False,
        tail_last_sample_dbfs=float("-inf"),
        tail_end_rms_dbfs=-145.0,
    )

    assert classification == "INFO"
    assert "67.1 ms" in note


def test_energetic_tail_67ms_still_warns():
    classification, _note = classify_tail_silence_difference(
        source_trailing_silence_ms=900.0,
        processed_trailing_silence_ms=832.9,
        duration_delta_ms=0.0,
        tail_hard_cut=False,
        tail_energetic_end=True,
        tail_last_sample_dbfs=-90.0,
        tail_end_rms_dbfs=-28.0,
    )

    assert classification == "WARN"


def test_report_only_claims_steps_actually_executed():
    import Suno15_Mastering_v3_9 as app

    text = app._automatic_limit_text(
        "02 Blue Seat by the Door.wav",
        ["DYNAMICS RISK"],
        "Tokyo Chill + Chill Rap",
        {
            "transparent_render_count": "1",
            "fullness_render_count": "0",
            "peak_trim_count": "0",
            "tail_fix_mode": "none",
            "codec_check_count": "0",
            "codec_ceiling_rerender_count": "0",
        },
    )

    assert "transparent mastering" in text
    assert "Codec safety check" not in text
    assert "Codec ceiling rerender" not in text


def test_warn_release_disposition_safe_only():
    import Suno15_Mastering_v3_9 as app

    safe = SimpleNamespace(
        issues=(),
        warnings=("silent trailing-silence difference 67.1 ms; final tail is fully quiet and safe",),
    )
    unsafe = SimpleNamespace(
        issues=(),
        warnings=("ENERGETIC TAIL END: end RMS -28.0 dBFS > -35.0 dBFS",),
    )

    assert app._release_disposition(safe, codec_safe=True) == "RELEASE_READY_WITH_WARNING"
    assert app._release_disposition(unsafe, codec_safe=True) == "NEEDS_REVIEW"
