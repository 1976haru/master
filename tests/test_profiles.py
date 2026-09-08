import json

import pytest

from haru_mastering.profiles import ProfileError, load_profiles, resolve_profile


def test_profile_inheritance_and_global_merge(tmp_path):
    payload = {
        "global": {
            "workingSampleRateHz": 48000,
            "outputBitDepth": 24,
        },
        "profiles": {
            "base": {
                "targetLufsI": -14.0,
                "truePeakCeilingDbtp": -1.5,
                "maxAutomaticEqDb": 1.0,
                "maxBroadbandGainReductionDb": 1.5,
                "maxLraReductionLu": 0.5,
                "maxStereoWidthChangePercent": 5,
                "nested": {"a": 1, "b": 2},
            },
            "child": {
                "inherits": "base",
                "truePeakCeilingDbtp": -1.2,
                "nested": {"b": 9},
            },
        },
    }
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_profiles(path)
    resolved = resolve_profile(loaded, "child")

    assert resolved["workingSampleRateHz"] == 48000
    assert resolved["targetLufsI"] == -14.0
    assert resolved["truePeakCeilingDbtp"] == -1.2
    assert resolved["nested"] == {"a": 1, "b": 9}
    assert resolved["profileName"] == "child"


def test_unknown_profile_raises(tmp_path):
    payload = {"global": {}, "profiles": {"one": {}}}
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProfileError, match="Unknown profile"):
        resolve_profile(load_profiles(path), "missing")
