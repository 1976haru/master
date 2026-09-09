from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping


class ProfileError(ValueError):
    """Raised when a channel profile file is invalid."""


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, Mapping)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_profiles(path: str | Path) -> dict[str, Any]:
    profile_path = Path(path)
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileError(f"Profile file not found: {profile_path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(
            f"Invalid JSON in profile file {profile_path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(payload, dict):
        raise ProfileError("Profile root must be a JSON object.")
    if not isinstance(payload.get("global"), dict):
        raise ProfileError("Profile file must contain a 'global' object.")
    if not isinstance(payload.get("profiles"), dict) or not payload["profiles"]:
        raise ProfileError("Profile file must contain a non-empty 'profiles' object.")

    return payload


def resolve_profile(payload: Mapping[str, Any], profile_name: str) -> dict[str, Any]:
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping):
        raise ProfileError("Missing profiles mapping.")
    if profile_name not in profiles:
        available = ", ".join(sorted(str(name) for name in profiles))
        raise ProfileError(f"Unknown profile '{profile_name}'. Available: {available}")

    visiting: set[str] = set()

    def resolve(name: str) -> dict[str, Any]:
        if name in visiting:
            chain = " -> ".join([*visiting, name])
            raise ProfileError(f"Circular profile inheritance detected: {chain}")

        raw = profiles.get(name)
        if not isinstance(raw, Mapping):
            raise ProfileError(f"Profile '{name}' must be an object.")

        visiting.add(name)
        parent_name = raw.get("inherits")
        if parent_name is None:
            merged = copy.deepcopy(dict(raw))
        else:
            if not isinstance(parent_name, str) or parent_name not in profiles:
                raise ProfileError(
                    f"Profile '{name}' inherits unknown profile '{parent_name}'."
                )
            merged = _deep_merge(resolve(parent_name), raw)

        visiting.remove(name)
        merged.pop("inherits", None)
        return merged

    resolved = _deep_merge(payload["global"], resolve(profile_name))
    _validate_resolved_profile(profile_name, resolved)
    resolved["profileName"] = profile_name
    return resolved


def _validate_resolved_profile(name: str, profile: Mapping[str, Any]) -> None:
    required_numeric = (
        "workingSampleRateHz",
        "outputBitDepth",
        "targetLufsI",
        "truePeakCeilingDbtp",
        "maxAutomaticEqDb",
        "maxBroadbandGainReductionDb",
        "maxLraReductionLu",
        "maxStereoWidthChangePercent",
    )
    missing = [key for key in required_numeric if key not in profile]
    if missing:
        raise ProfileError(f"Profile '{name}' is missing fields: {', '.join(missing)}")

    for key in required_numeric:
        if not isinstance(profile[key], (int, float)):
            raise ProfileError(f"Profile '{name}' field '{key}' must be numeric.")

    if profile["workingSampleRateHz"] <= 0:
        raise ProfileError("workingSampleRateHz must be positive.")
    if profile["outputBitDepth"] not in (16, 24, 32):
        raise ProfileError("outputBitDepth must be 16, 24, or 32.")
    if profile["truePeakCeilingDbtp"] > 0:
        raise ProfileError("truePeakCeilingDbtp must not be above 0 dBTP.")
    if profile["maxAutomaticEqDb"] < 0:
        raise ProfileError("maxAutomaticEqDb must be non-negative.")
