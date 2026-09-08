from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from haru_mastering.auto_finish import (
    apply_click_safe_fade,
    inspect_tail,
    organize_release_files,
    repair_tail_automatically,
    write_beginner_summary,
)


def test_click_safe_fade_closes_last_sample(tmp_path):
    sr = 48000
    t = np.arange(sr, dtype=np.float64) / sr
    tone = 0.05 * np.sin(2.0 * np.pi * 220.0 * t)
    audio = np.column_stack([tone, tone])
    path = tmp_path / "hardcut.wav"
    sf.write(path, audio, sr, subtype="PCM_24")

    before = inspect_tail(path)
    assert before.hard_cut is True

    apply_click_safe_fade(path, fade_ms=25.0)
    after = inspect_tail(path)
    repaired, _ = sf.read(path, always_2d=True, dtype="float64")

    assert after.hard_cut is False
    assert np.max(np.abs(repaired[-1])) == 0.0
    assert repaired.shape == audio.shape


def test_energetic_ending_gets_long_musical_fade(tmp_path):
    sr = 48000
    t = np.arange(sr, dtype=np.float64) / sr
    tone = 0.05 * np.sin(2.0 * np.pi * 220.0 * t)
    path = tmp_path / "energetic.wav"
    sf.write(path, np.column_stack([tone, tone]), sr, subtype="PCM_24")

    repaired = repair_tail_automatically(
        path,
        energetic_end_threshold_dbfs=-35.0,
        energetic_fade_ms=400.0,
    )
    audio, _ = sf.read(path, always_2d=True, dtype="float64")

    assert repaired.mode == "musical_tail_fade"
    assert repaired.before.energetic_end is True
    assert repaired.after.energetic_end is False
    assert repaired.after.end_rms_dbfs <= -35.0
    assert np.max(np.abs(audio[-1])) == 0.0


def test_quiet_hard_cut_uses_short_click_fade(tmp_path):
    sr = 48000
    audio = np.full((sr, 2), 0.008, dtype=np.float64)
    path = tmp_path / "quiet_cut.wav"
    sf.write(path, audio, sr, subtype="PCM_24")

    repaired = repair_tail_automatically(
        path,
        energetic_end_threshold_dbfs=-35.0,
        hard_cut_fade_ms=25.0,
    )

    assert repaired.before.hard_cut is True
    assert repaired.before.energetic_end is False
    assert repaired.mode == "click_safe_fade"
    assert repaired.after.hard_cut is False


def test_release_tree_separates_pass_and_review(tmp_path):
    good = tmp_path / "good_MASTER.wav"
    bad = tmp_path / "bad_MASTER.wav"
    good.write_bytes(b"good")
    bad.write_bytes(b"bad")

    paths = organize_release_files(tmp_path, [(good, "PASS"), (bad, "FAIL")])

    assert (paths["release"] / good.name).read_bytes() == b"good"
    assert (paths["review"] / bad.name).read_bytes() == b"bad"
    assert not (paths["release"] / bad.name).exists()


def test_beginner_summary_is_actionable(tmp_path):
    summary = write_beginner_summary(
        tmp_path,
        pass_count=15,
        review_count=0,
        auto_fixed_count=2,
        codec_safe_count=15,
        total_count=15,
    )
    text = summary.read_text(encoding="utf-8")
    assert "배포 가능" in text
    assert "01_RELEASE_READY" in text
    assert "자동 수정 완료: 2" in text
