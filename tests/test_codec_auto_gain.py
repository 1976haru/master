from __future__ import annotations

import math

import numpy as np
import soundfile as sf

from haru_mastering.codec_auto_gain import (
    apply_gain_reduction,
    calculate_codec_gain_reduction_db,
    ensure_codec_safety_with_auto_gain,
)
from haru_mastering.codec_preview import CodecSafetyResult


def _sample_peak_dbfs(path) -> float:
    audio, _ = sf.read(path, always_2d=True, dtype="float64")
    peak = float(np.max(np.abs(audio)))
    return 20.0 * math.log10(max(peak, 1e-15))


def test_calculate_codec_gain_reduction_matches_measured_overshoot():
    reduction = calculate_codec_gain_reduction_db(
        -1.12,
        -1.50,
        safety_margin_db=0.10,
    )
    assert abs(reduction - 0.48) < 1e-9


def test_apply_gain_reduction_is_transparent_and_predictable(tmp_path):
    sr = 48000
    t = np.arange(sr, dtype=np.float64) / sr
    mono = 0.8 * np.sin(2.0 * np.pi * 440.0 * t)
    path = tmp_path / "tone.wav"
    sf.write(path, np.column_stack([mono, mono]), sr, subtype="PCM_24")
    before = _sample_peak_dbfs(path)

    apply_gain_reduction(path, 0.50)
    after = _sample_peak_dbfs(path)

    assert abs((before - after) - 0.50) < 0.01


def test_auto_gain_rechecks_until_codec_safe(tmp_path):
    sr = 48000
    t = np.arange(sr, dtype=np.float64) / sr
    mono = 0.88 * np.sin(2.0 * np.pi * 997.0 * t)
    path = tmp_path / "codec_risk.wav"
    sf.write(path, np.column_stack([mono, mono]), sr, subtype="PCM_24")

    def fake_checker(source_path, *, true_peak_ceiling_dbtp, tolerance_db, ffmpeg=None):
        peak = _sample_peak_dbfs(source_path)
        return CodecSafetyResult(
            safe=peak <= true_peak_ceiling_dbtp + tolerance_db,
            maximum_true_peak_dbtp=peak,
            details=(("FAKE", peak),),
        )

    outcome = ensure_codec_safety_with_auto_gain(
        path,
        checker=fake_checker,
        true_peak_ceiling_dbtp=-1.50,
        tolerance_db=0.05,
        maximum_passes=3,
        safety_margin_db=0.10,
    )

    assert outcome.safety.safe is True
    assert outcome.passes >= 1
    assert 0.0 < outcome.total_gain_reduction_db <= 2.0
    assert outcome.safety.maximum_true_peak_dbtp <= -1.55
