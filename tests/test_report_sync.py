from __future__ import annotations

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_file
from haru_mastering.auto_finish import inspect_tail
from haru_mastering.quality_gate import QualityGateResult
from haru_mastering.report import QUALITY_REPORT_VERSION, _refresh_final_metrics


def test_report_refreshes_tail_from_actual_final_wav(tmp_path):
    sr = 48000
    rng = np.random.default_rng(360)
    source_audio = rng.normal(0.0, 0.03, size=(sr * 2, 2))
    fade_frames = int(0.20 * sr)
    source_audio[-fade_frames:] *= np.linspace(1.0, 0.0, fade_frames)[:, None]
    source_audio[-1] = 0.0

    source_path = tmp_path / "sync_source.wav"
    final_path = tmp_path / "sync_source_MASTER.wav"
    sf.write(source_path, source_audio, sr, subtype="PCM_24")
    sf.write(final_path, source_audio * 0.5, sr, subtype="PCM_24")

    source_metrics = analyze_file(source_path)
    stale_processed = source_metrics
    stale_result = QualityGateResult(
        status="PASS",
        issues=(),
        warnings=(),
        residual_delay_samples=0,
        delay_window_estimates_samples=(0, 0, 0, 0, 0),
        delay_confidence=1.0,
        delay_consistent=True,
        delay_classification="PASS",
        delay_note="",
        delay_auto_aligned=False,
        delay_original_samples=None,
        duration_delta_ms=0.0,
        low_band_stereo_correlation=1.0,
        lra_reduction_lu=0.0,
        crest_factor_loss_db=0.0,
        lra_guard_triggered=False,
        tail_end_rms_dbfs=-10.0,
        tail_last_sample_dbfs=-10.0,
        tail_hard_cut=True,
        tail_energetic_end=True,
        source=source_metrics,
        processed=stale_processed,
        tail_note="minor trailing-silence difference 28.5 ms; final tail is silent and safe",
    )

    refreshed = _refresh_final_metrics(tmp_path, "sync_source.wav", stale_result)
    actual = analyze_file(final_path)
    final_tail = inspect_tail(
        final_path,
        window_ms=100.0,
        end_rms_threshold_dbfs=-50.0,
        last_sample_threshold_dbfs=-60.0,
        energetic_end_threshold_dbfs=-35.0,
    )

    assert QUALITY_REPORT_VERSION == "v3.6.1"
    assert abs(refreshed.processed.lufs_i - actual.lufs_i) < 1e-9
    assert abs(refreshed.processed.true_peak_dbtp - actual.true_peak_dbtp) < 1e-9
    assert abs(refreshed.processed.lra_lu - actual.lra_lu) < 1e-9
    assert abs(refreshed.tail_end_rms_dbfs - final_tail.end_rms_dbfs) < 1e-9
    assert refreshed.tail_last_sample_dbfs == final_tail.last_sample_dbfs
    assert refreshed.tail_hard_cut is final_tail.hard_cut
    assert refreshed.tail_energetic_end is final_tail.energetic_end
    assert refreshed.tail_note.startswith("minor trailing-silence")
    assert any("codec safety attenuation applied" in item for item in refreshed.warnings)
