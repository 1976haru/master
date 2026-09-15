from __future__ import annotations

from types import SimpleNamespace

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


def test_codec_rerender_after_quality_gate_budget_does_not_crash(tmp_path, monkeypatch):
    import Suno15_Mastering_v3_9 as app

    source = tmp_path / "04 Three Stops Together.wav"
    base = tmp_path / "base.wav"
    destination = tmp_path / "master.wav"
    source.write_text("source", encoding="ascii")
    base.write_text("base", encoding="ascii")

    instance = app.AppV39.__new__(app.AppV39)
    instance.after = lambda *_args: None
    instance._stage_status = lambda *_args: None
    instance._stage_log = lambda *_args: None
    instance._repair_tail = lambda *_args: SimpleNamespace(mode="none")

    metrics = _metrics(lra=4.16, crest=8.8)
    source_ctx = SimpleNamespace(audio=None, sample_rate=48000, metrics=metrics)
    base_ctx = SimpleNamespace(audio=None, sample_rate=48000, metrics=metrics)
    counters = app.TrackCounters(
        fullness_render_limit=2,
        normal_quality_gate_limit=3,
        codec_quality_gate_limit=2,
    )
    counters.quality_gate_count = 3
    counters.normal_quality_gate_count = 3
    counters.accepted_sound_mode = "NATURAL"
    counters.accepted_fullness_strength = 0

    def fake_evaluate_master(*_args, **_kwargs):
        return SimpleNamespace(status="PASS", issues=(), warnings=(), processed=metrics)

    monkeypatch.setattr(app.v32, "evaluate_master", fake_evaluate_master)

    result, _tail, _timing = instance._reapply_accepted_candidate(
        source,
        base,
        destination,
        "CG_TOKYO_CHILL__CHILL_RAP",
        {},
        {},
        {},
        source_ctx,
        base_ctx,
        [],
        counters,
        track_index=4,
        track_total=15,
    )

    assert result.status == "PASS"
    assert counters.codec_quality_gate_count == 1
    assert counters.normal_quality_gate_count == 3
    assert counters.codec_quality_gate_count == 1
    assert counters.quality_gate_count == 4
    assert counters.fullness_render_count == 0
    assert counters.codec_sound_reapply_count == 0


def test_codec_rerender_reuses_accepted_rich_strength_without_normal_fullness_retry(
    tmp_path,
    monkeypatch,
):
    import Suno15_Mastering_v3_9 as app

    source = tmp_path / "source.wav"
    base = tmp_path / "base.wav"
    destination = tmp_path / "master.wav"
    source.write_text("source", encoding="ascii")
    base.write_text("base", encoding="ascii")

    instance = app.AppV39.__new__(app.AppV39)
    instance.after = lambda *_args: None
    instance._stage_status = lambda *_args: None
    instance._stage_log = lambda *_args: None
    instance._repair_tail = lambda *_args: SimpleNamespace(mode="none")
    metrics = _metrics(lra=4.16, crest=8.8)
    source_ctx = SimpleNamespace(audio=None, sample_rate=48000, metrics=metrics)
    base_ctx = SimpleNamespace(audio=None, sample_rate=48000, metrics=metrics)
    counters = app.TrackCounters(fullness_render_limit=2)
    counters.accepted_sound_mode = "RICH"
    counters.accepted_fullness_strength = 50
    calls = []

    def fake_render(*args, **kwargs):
        calls.append((kwargs.get("count_scope"), args[2].strength_percent))
        counters.codec_sound_reapply_count += 1
        return SimpleNamespace(
            processed_audio=None,
            processed_sample_rate=None,
            after=metrics,
        )

    def fake_evaluate(self, *_args, gate_scope="normal", **_kwargs):
        return SimpleNamespace(status="PASS", issues=(), warnings=(), processed=metrics)

    monkeypatch.setattr(instance, "_render_fullness_candidate", fake_render)
    monkeypatch.setattr(app.AppV39, "_evaluate_candidate", fake_evaluate)

    instance._reapply_accepted_candidate(
        source,
        base,
        destination,
        "CG_TOKYO_CHILL__CHILL_RAP",
        {},
        {},
        {},
        source_ctx,
        base_ctx,
        [],
        counters,
        track_index=4,
        track_total=15,
    )

    assert calls == [("codec", 50)]
    assert counters.fullness_render_count == 0
    assert counters.codec_sound_reapply_count == 1


def test_worker_continues_to_next_track_after_track_exception(tmp_path, monkeypatch):
    import Suno15_Mastering_v3_9 as app

    first = tmp_path / "04 Three Stops Together.wav"
    second = tmp_path / "05 Next Track.wav"
    first.write_text("source", encoding="ascii")
    second.write_text("source", encoding="ascii")

    class Value:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    instance = app.AppV39.__new__(app.AppV39)
    instance.channel_var = Value("TOKYO_CHILL")
    instance.genre_var = Value("CHILL_RAP")
    instance.quality_var = Value("QUALITY+")
    instance._fullness_mode = lambda *_args: "NATURAL"
    instance.progress_var = Value(0)
    instance.status_var = Value("")
    instance.start_btn = SimpleNamespace(config=lambda *_args, **_kwargs: None)
    logs = []
    instance.append_log = lambda text: logs.append(str(text))
    instance.after = lambda _delay, callback, *args: callback(*args)
    instance._stage_status = lambda *_args: None
    instance._stage_log = lambda *_args: None
    instance._refresh_v39_reports = lambda *_args: None

    metrics = _metrics(lra=4.16, crest=8.8)
    source_ctx = app.SourceContext(
        audio=None,
        sample_rate=48000,
        metrics=metrics,
        raw=app._metrics_as_raw(metrics),
    )
    result = SimpleNamespace(status="PASS", issues=(), warnings=(), processed=metrics)
    candidate = app.CandidateFinish(
        True,
        "",
        result,
        None,
        app.TrackTiming(),
        0,
        [],
        None,
    )
    source_calls = []

    def fake_source_context(path):
        source_calls.append(path.name)
        if path == first:
            raise ValueError("fixture track error")
        return source_ctx

    def fake_render_base(_source, base, *_args):
        base.write_text("base", encoding="ascii")
        return True, ""

    monkeypatch.setattr(app, "install_v39_runtime", lambda: None)
    monkeypatch.setattr(
        app.v32,
        "_settings",
        lambda _key: (
            {"maximum_lra_reduction_lu": 0.8},
            {
                "maximumAutoRerenders": 2,
                "transparentFallbackEnabled": True,
                "codecPreviewEnabled": False,
            },
            {"truePeakCeilingDbtp": -1.2},
        ),
    )
    monkeypatch.setattr(instance, "_source_context", fake_source_context)
    monkeypatch.setattr(instance, "_render_base", fake_render_base)
    monkeypatch.setattr(instance, "_audio_context", lambda _path: app.AudioContext(None, 48000, metrics))
    monkeypatch.setattr(instance, "_finish_candidate", lambda *_args, **_kwargs: candidate)
    organized = []

    def fake_organize(out_dir, _rows):
        organized.append(out_dir)
        return {
            "release": tmp_path / "release",
            "review": tmp_path / "review",
            "report": tmp_path / "report",
            "codec": tmp_path / "codec",
        }

    monkeypatch.setattr(
        app,
        "organize_release_files",
        fake_organize,
    )
    for directory in (tmp_path / "release", tmp_path / "review", tmp_path / "report", tmp_path / "codec"):
        directory.mkdir()
    monkeypatch.setattr(app, "write_quality_reports", lambda *_args: (None, None))
    monkeypatch.setattr(app, "write_beginner_summary", lambda *_args, **_kwargs: tmp_path / "summary.txt")
    monkeypatch.setattr(app.legacy.messagebox, "showinfo", lambda *_args, **_kwargs: None)

    instance._worker(tmp_path, [first, second])

    assert source_calls == [first.name, second.name]
    assert any("[01/02] ERROR: ValueError: fixture track error" in line for line in logs)
    assert any("[02/02]" in line and "완료" in line for line in logs)
    assert organized
    assert (organized[0] / "ERROR_01_04 Three Stops Together.txt").exists()
