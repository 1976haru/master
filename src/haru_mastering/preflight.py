from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .analysis import AudioMetrics


@dataclass(frozen=True)
class PreflightDecision:
    configured_target_lufs: float
    adaptive_target_lufs: float
    projected_true_peak_dbtp: float
    projected_peak_reduction_db: float
    compression_mode: str
    compression_scale: float
    dynamic_margin_lu: float
    loudness_adapted: bool
    compression_adapted: bool
    reasons: tuple[str, ...]
    source_peak_stressed: bool = False
    ordinary_adaptive_target_lufs: float | None = None
    effective_target_lufs: float | None = None
    gain_only_recommended: bool = False
    peak_treatment_budget_db: float = 1.5
    absolute_safety_floor_lufs: float = -18.0
    safety_floor_requires_review: bool = False

    @property
    def loudness_concession_lu(self) -> float:
        return max(0.0, float(self.configured_target_lufs - self.adaptive_target_lufs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["loudness_concession_lu"] = self.loudness_concession_lu
        return payload


def _finite(value: float, fallback: float) -> float:
    number = float(value)
    return number if math.isfinite(number) else float(fallback)


def decide_preflight(
    metrics: AudioMetrics,
    profile: Mapping[str, Any],
    *,
    configured_target_lufs: float,
    true_peak_ceiling_dbtp: float,
    minimum_final_lra_lu: float = 3.5,
) -> PreflightDecision:
    """Choose track-local loudness and compression before the first render.

    This uses metrics that the worker already has, so it must not trigger an
    additional full-file analysis.
    """
    configured = float(configured_target_lufs)
    ceiling = float(true_peak_ceiling_dbtp)
    source_lufs = _finite(metrics.lufs_i, configured)
    source_tp = _finite(metrics.true_peak_dbtp, ceiling)
    source_lra = _finite(metrics.lra_lu, float(minimum_final_lra_lu))

    max_concession = float(profile.get("maximumLoudnessConcessionLu", 2.0))
    minimum_target = float(
        profile.get("minimumTargetLufsI", configured - max(0.0, max_concession))
    )
    peak_budget = float(profile.get("maxProjectedPeakReductionDb", 1.5))
    source_peak_stressed = metrics.clipped_sample_count > 0 or source_tp >= 0.0
    peak_treatment_budget = float(
        profile.get("peakStressedMaxProjectedPeakReductionDb", 0.8)
        if source_peak_stressed
        else peak_budget
    )
    absolute_floor = float(profile.get("absoluteMinimumSafetyTargetLufsI", -18.0))

    gain_to_target = configured - source_lufs
    projected_tp = source_tp + gain_to_target
    projected_reduction = max(0.0, projected_tp - ceiling)

    adaptive = configured
    reasons: list[str] = []
    if source_peak_stressed:
        reasons.append("source peak pressure")
    if projected_reduction > peak_treatment_budget:
        excess = projected_reduction - peak_treatment_budget
        adaptive = max(minimum_target, configured - excess)
        if adaptive < configured - 0.01:
            reasons.append("projected peak reduction budget")

    dynamic_margin = source_lra - float(minimum_final_lra_lu)
    transparent_margin = float(profile.get("compressionTransparentMarginLu", 0.5))
    reduced_margin = float(profile.get("compressionReducedMarginLu", 1.0))
    reduced_scale = float(profile.get("compressionReducedScale", 0.35))

    if dynamic_margin <= transparent_margin:
        compression_mode = "TRANSPARENT"
        compression_scale = 0.0
        reasons.append("low source LRA")
    elif dynamic_margin <= reduced_margin:
        compression_mode = "REDUCED"
        compression_scale = max(0.0, min(1.0, reduced_scale))
        reasons.append("narrow source dynamics")
    else:
        compression_mode = "PROFILE"
        compression_scale = 1.0

    ordinary_adaptive = float(adaptive)
    gain_only_recommended = compression_mode == "TRANSPARENT" or source_peak_stressed
    effective = ordinary_adaptive
    safety_floor_requires_review = False
    if gain_only_recommended:
        peak_safe_target = source_lufs + (
            ceiling - float(profile.get("truePeakSafetyMarginDb", 0.05)) - source_tp
        )
        if source_peak_stressed:
            effective = min(ordinary_adaptive, peak_safe_target)
            safety_floor_requires_review = effective < absolute_floor - 1e-9
            effective = max(absolute_floor, effective)
            if effective < ordinary_adaptive - 0.01:
                reasons.append("gain-only peak safety")
        else:
            effective = min(ordinary_adaptive, peak_safe_target)
        if safety_floor_requires_review:
            reasons.append("safety floor requires review")

    return PreflightDecision(
        configured_target_lufs=configured,
        adaptive_target_lufs=round(float(adaptive), 3),
        projected_true_peak_dbtp=round(float(projected_tp), 3),
        projected_peak_reduction_db=round(float(projected_reduction), 3),
        compression_mode=compression_mode,
        compression_scale=round(float(compression_scale), 3),
        dynamic_margin_lu=round(float(dynamic_margin), 3),
        loudness_adapted=adaptive < configured - 0.01,
        compression_adapted=compression_mode != "PROFILE",
        reasons=tuple(dict.fromkeys(reasons)),
        source_peak_stressed=source_peak_stressed,
        ordinary_adaptive_target_lufs=round(ordinary_adaptive, 3),
        effective_target_lufs=round(float(effective), 3),
        gain_only_recommended=gain_only_recommended,
        peak_treatment_budget_db=round(peak_treatment_budget, 3),
        absolute_safety_floor_lufs=round(absolute_floor, 3),
        safety_floor_requires_review=safety_floor_requires_review,
    )
