from __future__ import annotations

from haru_mastering.profile_catalog import (
    CHANNEL_PROFILES,
    GENRE_PROFILES,
    compose_legacy_genre,
    compose_runtime_profile,
    composite_key,
)


def test_channel_profiles_and_genre_profiles_are_separate():
    channel_labels = {profile.label for profile in CHANNEL_PROFILES.values()}
    genre_labels = {profile.label for profile in GENRE_PROFILES.values()}

    assert "올드팝 라운지" in channel_labels
    assert "한국 시니어" in channel_labels
    assert "일본 시니어" in channel_labels
    assert "Tokyo Chill / 일본 20~30대" in channel_labels

    assert "올드팝 라운지" not in genre_labels
    assert "한국 시니어" not in genre_labels
    assert "일본 시니어" not in genre_labels
    assert "SHOWA" not in genre_labels

    assert "K-POP" in genre_labels
    assert "재즈" in genre_labels
    assert "발라드" in genre_labels
    assert "60~80s Pop / Oldies" in genre_labels


def test_channel_genre_composition_keeps_roles_distinct():
    combined = compose_legacy_genre("OLD_POP_LOUNGE", "JAZZ")

    assert combined["label"] == "올드팝 라운지 + 재즈"
    assert combined["target_i"] == CHANNEL_PROFILES["OLD_POP_LOUNGE"].target_lufs_i
    assert combined["target_tp"] == CHANNEL_PROFILES["OLD_POP_LOUNGE"].true_peak_ceiling_dbtp
    assert combined["eq"] == list(GENRE_PROFILES["JAZZ"].eq)
    assert "다이내믹 보존" in combined["character"]


def test_runtime_profile_contains_channel_and_genre_metadata():
    base = {
        "targetLufsI": -14.0,
        "truePeakCeilingDbtp": -1.5,
        "maxLraReductionLu": 0.8,
        "intent": [],
    }
    profile = compose_runtime_profile(base, "TOKYO_CHILL", "CHILL_RAP")

    assert profile["profileName"] == composite_key("TOKYO_CHILL", "CHILL_RAP")
    assert profile["channelProfileKey"] == "TOKYO_CHILL"
    assert profile["genreProfileKey"] == "CHILL_RAP"
    assert profile["targetLufsI"] == CHANNEL_PROFILES["TOKYO_CHILL"].target_lufs_i
    assert profile["fullness"]["saturationMaximumWetPercent"] <= 4.0

