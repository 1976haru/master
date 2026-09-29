from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from haru_mastering.noise_repair import (
    NoiseRepairSettings,
    analyze_audio,
    available_filters,
    repair_file,
    summary,
    write_noise_report,
)


SR = 48000


def music_like(seconds: float = 4.0, level: float = 0.08) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    envelope = 0.65 + 0.35 * np.sin(2 * np.pi * 0.7 * t) ** 2
    mono = level * envelope * (
        np.sin(2 * np.pi * 220 * t) + 0.45 * np.sin(2 * np.pi * 440 * t)
    )
    return np.column_stack([mono, mono * 0.97])


def test_clean_music_is_bypassed():
    result = analyze_audio(music_like(), SR)
    assert result.decision == "CLEAN"
    assert result.detected_types == []


def test_white_noise_in_quiet_signal_detects_hiss():
    rng = np.random.default_rng(1234)
    audio = music_like(level=0.012) + rng.normal(0, 0.006, (SR * 4, 2))
    result = analyze_audio(audio, SR)
    assert "HISS" in result.detected_types
    assert result.decision in {"LIGHT_REPAIR", "MEDIUM_REPAIR"}


def test_click_in_quiet_intro_is_detected():
    audio = music_like(level=0.012)
    for position in range(SR // 2, len(audio), SR):
        audio[position : position + 2] += 0.65
    result = analyze_audio(audio, SR)
    assert "CLICK_CRACKLE" in result.detected_types


def test_sixty_hz_hum_is_detected():
    t = np.arange(SR * 4) / SR
    hum = 0.012 * np.sin(2 * np.pi * 60 * t) + 0.004 * np.sin(2 * np.pi * 120 * t)
    audio = music_like(level=0.004) + hum[:, None]
    result = analyze_audio(audio, SR)
    assert "HUM" in result.detected_types


def test_clean_quiet_intro_and_normal_body_stays_clean():
    intro = np.zeros((SR * 2, 2))
    body = music_like(seconds=3.0, level=0.1)
    result = analyze_audio(np.vstack([intro, body]), SR, intro_seconds=2.0)
    assert result.decision == "CLEAN"


def test_off_returns_exact_source_path_without_output(tmp_path: Path):
    source = tmp_path / "source.wav"
    output = tmp_path / "repair.wav"
    sf.write(source, music_like(), SR, subtype="PCM_24")
    result = repair_file(source, output, shutil.which("ffmpeg"), NoiseRepairSettings(mode="OFF"))
    assert result.output == str(source)
    assert result.applied_mode == "OFF"
    assert not output.exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is unavailable")
def test_hiss_repair_preserves_duration_channels_and_no_clipping(tmp_path: Path):
    rng = np.random.default_rng(7)
    source = tmp_path / "hiss.wav"
    output = tmp_path / "repair.wav"
    audio = music_like(level=0.012) + rng.normal(0, 0.006, (SR * 4, 2))
    sf.write(source, audio, SR, subtype="PCM_24")
    result = repair_file(source, output, shutil.which("ffmpeg"), NoiseRepairSettings(mode="AUTO"))
    assert result.result in {"REPAIRED_LIGHT", "REPAIRED_MEDIUM"}
    repaired, repaired_sr = sf.read(output, always_2d=True)
    assert repaired_sr == SR
    assert repaired.shape == audio.shape
    assert np.max(np.abs(repaired)) < 1.0


def test_filter_detection_and_report(tmp_path: Path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        assert {"afftdn", "adeclick"} <= available_filters(ffmpeg)
    source = tmp_path / "clean.wav"
    sf.write(source, music_like(), SR)
    result = repair_file(source, tmp_path / "unused.wav", ffmpeg, NoiseRepairSettings(mode="OFF"))
    report = write_noise_report(tmp_path / "reports" / "noise_repair_report.csv", [result])
    assert report.exists()
    assert "Filename" in report.read_text(encoding="utf-8-sig")
    assert summary([result])["CLEAN"] == 1
