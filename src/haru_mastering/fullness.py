from __future__ import annotations

import math
import shutil
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, sosfiltfilt

from .analysis import AudioMetrics, analyze_array, analyze_file


BANDS: tuple[tuple[int, int], ...] = (
    (20, 60),
    (60, 120),
    (120, 250),
    (250, 500),
    (500, 1000),
    (1000, 2000),
    (2000, 5000),
)

FULLNESS_STRENGTH_STEPS = (100, 75, 50, 25, 0)
FAST_FULLNESS_STRENGTH_STEPS = (100, 0)
QUALITY_FULLNESS_STRENGTH_STEPS = (100, 50, 0)
MAX_FULLNESS_RENDER_PASSES = 2
_EPS = np.finfo(np.float64).tiny


@dataclass(frozen=True)
class FullnessDecision:
    mode: str
    strength_percent: int
    warmth_gain_db: float
    body_gain_db: float
    saturation_wet_percent: float
    density_wet_percent: float
    bypassed_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FullnessRender:
    decision: FullnessDecision
    before: AudioMetrics
    after: AudioMetrics
    level_match_gain_db: float
    clipped_sample_count: int
    processed_audio: np.ndarray | None = None
    processed_sample_rate: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.to_dict(),
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "level_match_gain_db": self.level_match_gain_db,
            "clipped_sample_count": self.clipped_sample_count,
            "processed_sample_rate": self.processed_sample_rate,
        }


def _finite_mean(values: list[float]) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return float("-inf")
    return float(sum(finite) / len(finite))


def _finite_max(values: list[float]) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return float("-inf")
    return float(max(finite))


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _scale_for_strength(value: float, strength_percent: int) -> float:
    return float(value) * _clamp(float(strength_percent) / 100.0, 0.0, 1.0)


def _genre_upper(value: str) -> str:
    return str(value or "GENERAL").strip().upper()


SATURATION_LIMITS: dict[str, float] = {
    "OLD POP": 6.0,
    "SENIOR KR": 5.0,
    "SENIOR JP": 4.0,
    "SHOWA JP": 4.0,
    "ENKA JP": 4.0,
    "BALLAD": 5.0,
    "J-BALLAD": 5.0,
    "SOUL": 6.0,
    "R&B": 5.0,
    "K-POP": 3.0,
    "KIDS POP": 2.0,
    "JAZZ": 2.0,
    "ACOUSTIC": 2.0,
    "INSTRUMENTAL": 2.0,
    "GENERAL": 3.0,
}

DENSITY_LIMITS: dict[str, float] = {
    "OLD POP": 5.0,
    "SENIOR KR": 4.0,
    "SENIOR JP": 3.0,
    "SHOWA JP": 3.0,
    "ENKA JP": 3.0,
    "SOUL": 5.0,
    "BALLAD": 4.0,
    "J-BALLAD": 4.0,
    "K-POP": 2.0,
    "KIDS POP": 1.5,
    "JAZZ": 1.0,
    "ACOUSTIC": 1.0,
    "INSTRUMENTAL": 1.0,
    "GENERAL": 2.0,
}

DEFAULT_RICH_GENRES = {
    "OLD POP",
    "SENIOR KR",
    "SENIOR JP",
    "SHOWA JP",
    "BALLAD",
    "J-BALLAD",
    "SOUL",
    "K-POP",
    "KIDS POP",
}


def default_fullness_mode(genre_key: str) -> str:
    return "RICH" if _genre_upper(genre_key) in DEFAULT_RICH_GENRES else "NATURAL"


def analyze(path: str | Path) -> AudioMetrics:
    return analyze_file(path)


def decide(
    metrics: AudioMetrics,
    *,
    genre_key: str = "GENERAL",
    mode: str = "RICH",
    strength_percent: int = 100,
    profile: Mapping[str, Any] | None = None,
) -> FullnessDecision:
    mode_name = str(mode or "NATURAL").upper()
    strength = int(_clamp(int(strength_percent), 0, 100))
    genre = _genre_upper(genre_key)
    if mode_name != "RICH" or strength <= 0:
        return FullnessDecision(
            mode="NATURAL",
            strength_percent=0,
            warmth_gain_db=0.0,
            body_gain_db=0.0,
            saturation_wet_percent=0.0,
            density_wet_percent=0.0,
            bypassed_reason="natural_mode",
        )

    bands = metrics.band_energy_db
    warmth = _finite_mean([bands.get("60-120Hz", float("-inf")), bands.get("120-250Hz", float("-inf"))])
    body = _finite_mean([bands.get("120-250Hz", float("-inf")), bands.get("250-500Hz", float("-inf"))])
    presence_floor = _finite_max(
        [
            bands.get("500-1000Hz", float("-inf")),
            bands.get("1000-2000Hz", float("-inf")),
            bands.get("2000-5000Hz", float("-inf")),
        ]
    )

    warmth_gain = 0.0
    body_gain = 0.0
    if math.isfinite(warmth) and math.isfinite(presence_floor):
        warmth_gap = presence_floor - warmth
        if warmth_gap > 2.5:
            warmth_gain = _clamp((warmth_gap - 2.5) * 0.20, 0.0, 0.8)
        elif warmth_gap < -5.0:
            warmth_gain = _clamp((warmth_gap + 5.0) * 0.12, -0.5, 0.0)

    if math.isfinite(body) and math.isfinite(presence_floor):
        body_gap = presence_floor - body
        if body_gap > 3.0:
            body_gain = _clamp((body_gap - 3.0) * 0.16, 0.0, 0.5)
        elif body_gap < -4.0:
            body_gain = _clamp((body_gap + 4.0) * 0.10, -0.5, 0.0)

    fullness_cfg = profile.get("fullness") if isinstance(profile, Mapping) else None
    if isinstance(fullness_cfg, Mapping):
        warmth_gain *= float(fullness_cfg.get("warmthScale", 1.0))
        body_gain *= float(fullness_cfg.get("bodyScale", 1.0))

    saturation_limit = SATURATION_LIMITS.get(genre, SATURATION_LIMITS["GENERAL"])
    if profile:
        saturation_cfg = profile.get("saturation") if isinstance(profile, Mapping) else None
        if isinstance(saturation_cfg, Mapping) and saturation_cfg.get("enabled", True):
            saturation_limit = min(
                saturation_limit,
                float(saturation_cfg.get("maximumWetPercent", saturation_limit)),
            )
        elif isinstance(saturation_cfg, Mapping):
            saturation_limit = 0.0
        if isinstance(fullness_cfg, Mapping):
            saturation_limit = min(
                saturation_limit,
                float(fullness_cfg.get("saturationMaximumWetPercent", saturation_limit)),
            )

    density_limit = DENSITY_LIMITS.get(genre, DENSITY_LIMITS["GENERAL"])
    if isinstance(fullness_cfg, Mapping):
        density_limit = min(
            density_limit,
            float(fullness_cfg.get("densityMaximumWetPercent", density_limit)),
        )
    return FullnessDecision(
        mode="RICH",
        strength_percent=strength,
        warmth_gain_db=round(_scale_for_strength(warmth_gain, strength), 3),
        body_gain_db=round(_scale_for_strength(body_gain, strength), 3),
        saturation_wet_percent=round(_scale_for_strength(saturation_limit, strength), 3),
        density_wet_percent=round(_scale_for_strength(density_limit, strength), 3),
        bypassed_reason="",
    )


def _db(value: float) -> float:
    if value <= 0 or not math.isfinite(value):
        return float("-inf")
    return 20.0 * math.log10(max(float(value), _EPS))


def _rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0


def _band(audio: np.ndarray, sample_rate: int, low_hz: float, high_hz: float) -> np.ndarray:
    nyquist = float(sample_rate) / 2.0
    low = max(float(low_hz), 5.0) / nyquist
    high = min(float(high_hz), nyquist * 0.95) / nyquist
    if low <= 0.0 or high >= 1.0 or low >= high:
        return np.zeros_like(audio)
    sos = butter(2, (low, high), btype="bandpass", output="sos")
    try:
        return sosfiltfilt(sos, audio, axis=0)
    except ValueError:
        return sosfilt(sos, audio, axis=0)


def _apply_band_gain(audio: np.ndarray, sample_rate: int, low_hz: float, high_hz: float, gain_db: float) -> np.ndarray:
    if abs(float(gain_db)) < 1e-6:
        return audio
    band = _band(audio, sample_rate, low_hz, high_hz)
    amount = 10.0 ** (float(gain_db) / 20.0) - 1.0
    return audio + band * amount


def _level_compensated_saturation(audio: np.ndarray, wet_percent: float) -> np.ndarray:
    wet = _clamp(float(wet_percent) / 100.0, 0.0, 1.0)
    if wet <= 0.0:
        return audio
    drive = 1.35
    shaped = np.tanh(audio * drive) / math.tanh(drive)
    before = _rms(audio)
    after = _rms(shaped)
    if before > 0.0 and after > 0.0:
        shaped = shaped * (before / after)
    return audio * (1.0 - wet) + shaped * wet


def _parallel_density(audio: np.ndarray, wet_percent: float) -> np.ndarray:
    wet = _clamp(float(wet_percent) / 100.0, 0.0, 1.0)
    if wet <= 0.0:
        return audio
    threshold = 10.0 ** (-18.0 / 20.0)
    ratio = 1.25
    magnitude = np.abs(audio)
    over = magnitude > threshold
    compressed = audio.copy()
    compressed[over] = np.sign(audio[over]) * (
        threshold + (magnitude[over] - threshold) / ratio
    )
    before = _rms(audio)
    after = _rms(compressed)
    if before > 0.0 and after > 0.0:
        compressed = compressed * (before / after)
    return audio * (1.0 - wet) + compressed * wet


def _match_integrated_loudness(audio: np.ndarray, sample_rate: int, target_lufs: float) -> tuple[np.ndarray, float]:
    current = analyze_array(audio, sample_rate).lufs_i
    if math.isfinite(target_lufs) and math.isfinite(current):
        gain_db = float(target_lufs - current)
    else:
        gain_db = 0.0
    if abs(gain_db) <= 1e-6:
        return audio, 0.0
    return audio * (10.0 ** (gain_db / 20.0)), gain_db


def process_array(
    audio: np.ndarray,
    sample_rate: int,
    decision: FullnessDecision,
    *,
    source_lufs: float | None = None,
) -> tuple[np.ndarray, float]:
    processed = np.asarray(audio, dtype=np.float64).copy()
    if decision.strength_percent <= 0 or decision.mode != "RICH":
        return processed, 0.0

    processed = _apply_band_gain(processed, sample_rate, 90.0, 220.0, decision.warmth_gain_db)
    processed = _apply_band_gain(processed, sample_rate, 220.0, 450.0, decision.body_gain_db)
    processed = _level_compensated_saturation(processed, decision.saturation_wet_percent)
    processed = _parallel_density(processed, decision.density_wet_percent)
    before_lufs = (
        float(source_lufs)
        if source_lufs is not None and math.isfinite(float(source_lufs))
        else analyze_array(audio, sample_rate).lufs_i
    )
    processed, level_gain = _match_integrated_loudness(processed, sample_rate, before_lufs)

    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    if peak >= 0.999:
        safety_gain_db = _db(0.998 / peak)
        processed = processed * (10.0 ** (safety_gain_db / 20.0))
        level_gain += safety_gain_db
    return processed, float(level_gain)


def process(
    source_path: str | Path,
    destination_path: str | Path,
    decision: FullnessDecision,
    *,
    subtype: str = "PCM_24",
    source_metrics: AudioMetrics | None = None,
    source_audio: np.ndarray | None = None,
    source_sample_rate: int | None = None,
    analyze_after: bool = True,
    return_audio: bool = False,
) -> FullnessRender:
    src = Path(source_path)
    dst = Path(destination_path)
    if decision.strength_percent <= 0 or decision.mode != "RICH":
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        before = source_metrics or analyze_file(src)
        after = before if src.resolve() == dst.resolve() else (source_metrics or analyze_file(dst))
        audio = None
        sample_rate = None
        if return_audio:
            if source_audio is not None and source_sample_rate is not None:
                audio = np.asarray(source_audio, dtype=np.float64)
                sample_rate = int(source_sample_rate)
            else:
                audio, sample_rate = sf.read(dst, always_2d=True, dtype="float64")
        return FullnessRender(
            decision,
            before,
            after,
            0.0,
            after.clipped_sample_count,
            audio,
            sample_rate,
        )

    if source_audio is None or source_sample_rate is None:
        audio, sample_rate = sf.read(src, always_2d=True, dtype="float64")
    else:
        audio = np.asarray(source_audio, dtype=np.float64)
        sample_rate = int(source_sample_rate)
    before = source_metrics or analyze_array(audio, sample_rate)
    processed, level_gain = process_array(
        audio,
        sample_rate,
        decision,
        source_lufs=before.lufs_i,
    )
    sf.write(dst, processed, sample_rate, subtype=subtype)
    after = analyze_array(processed, sample_rate) if analyze_after else before
    return FullnessRender(
        decision=decision,
        before=before,
        after=after,
        level_match_gain_db=level_gain,
        clipped_sample_count=after.clipped_sample_count,
        processed_audio=processed if return_audio else None,
        processed_sample_rate=sample_rate if return_audio else None,
    )


def retry_strength_for_guard_reasons(reasons: list[str] | tuple[str, ...]) -> int:
    text = " / ".join(str(reason).lower() for reason in reasons)
    if not text:
        return 50
    if "codec" in text:
        return 100
    if "lra" in text and "risk" in text:
        return 60
    if "crest" in text:
        return 50
    if "low-band stereo correlation" in text:
        return 60
    if "true peak" in text:
        return 50
    if "clipped" in text or "clipping" in text:
        return 50
    return 50


def reduce_decision_for_guard_reasons(
    decision: FullnessDecision,
    reasons: list[str] | tuple[str, ...],
    *,
    strength_percent: int | None = None,
) -> FullnessDecision:
    strength = retry_strength_for_guard_reasons(reasons) if strength_percent is None else int(strength_percent)
    strength = int(_clamp(strength, 0, 100))
    if strength <= 0 or decision.mode != "RICH":
        return FullnessDecision(
            mode="NATURAL",
            strength_percent=0,
            warmth_gain_db=0.0,
            body_gain_db=0.0,
            saturation_wet_percent=0.0,
            density_wet_percent=0.0,
            bypassed_reason="guard_reduced_to_off",
        )

    scale = strength / max(float(decision.strength_percent), 1.0)
    text = " / ".join(str(reason).lower() for reason in reasons)
    warmth = float(decision.warmth_gain_db) * scale
    body = float(decision.body_gain_db) * scale
    saturation = float(decision.saturation_wet_percent) * scale
    density = float(decision.density_wet_percent) * scale

    if "low-band stereo correlation" in text:
        warmth *= 0.35
        body *= 0.35
    if "clipped" in text or "clipping" in text:
        saturation *= 0.50
        density *= 0.50
    if "true peak" in text:
        saturation *= 0.70
        density *= 0.70
    if "lra" in text or "crest" in text:
        density *= 0.65

    return replace(
        decision,
        strength_percent=strength,
        warmth_gain_db=round(warmth, 3),
        body_gain_db=round(body, 3),
        saturation_wet_percent=round(saturation, 3),
        density_wet_percent=round(density, 3),
    )
