from __future__ import annotations

import numpy as np
import soundfile as sf

from haru_mastering.reference import build_reference_plan, ffmpeg_equalizer_chain


def test_reference_plan_is_bounded(tmp_path):
    sr = 48000
    t = np.arange(sr * 2, dtype=np.float64) / sr
    source_audio = (
        0.08 * np.sin(2 * np.pi * 220 * t)
        + 0.03 * np.sin(2 * np.pi * 3200 * t)
    )
    reference_audio = (
        0.05 * np.sin(2 * np.pi * 220 * t)
        + 0.06 * np.sin(2 * np.pi * 3200 * t)
    )
    source = tmp_path / "source.wav"
    reference = tmp_path / "reference.wav"
    sf.write(source, np.column_stack([source_audio, source_audio]), sr, subtype="PCM_24")
    sf.write(reference, np.column_stack([reference_audio, reference_audio]), sr, subtype="PCM_24")

    plan = build_reference_plan(source, reference, max_correction_db=0.8)

    assert plan.corrections
    assert all(abs(item.gain_db) <= 0.8 for item in plan.corrections)
    chain = ffmpeg_equalizer_chain(plan)
    assert "equalizer=" in chain
