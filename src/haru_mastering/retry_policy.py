from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .analysis import AudioMetrics
from .quality_gate import lra_dynamics_risk


@dataclass(frozen=True)
class DynamicsStats:
    lra_reduction_lu: float
    crest_factor_loss_db: float
    risky: bool


@dataclass(frozen=True)
class TrackRetryPolicy:
    resolved_maximum_auto_rerenders: int
    dynamics_base_rerenders: int
    codec_maximum_auto_rerenders: int
    fullness_render_limit: int
    quality_gate_normal_limit: int
    quality_gate_fullness_retry_limit: int
    quality_gate_transparent_limit: int


def build_track_retry_policy(
    *,
    mode: str,
    resolved_maximum_auto_rerenders: int,
    max_fullness_render_passes: int,
) -> TrackRetryPolicy:
    quality_mode = str(mode or "").upper() == "QUALITY+"
    resolved = max(0, int(resolved_maximum_auto_rerenders))
    fullness_limit = min(2 if quality_mode else 1, int(max_fullness_render_passes))
    return TrackRetryPolicy(
        resolved_maximum_auto_rerenders=resolved,
        dynamics_base_rerenders=0,
        codec_maximum_auto_rerenders=min(2, resolved) if quality_mode else 0,
        fullness_render_limit=fullness_limit,
        quality_gate_normal_limit=1,
        quality_gate_fullness_retry_limit=2 if quality_mode else 1,
        quality_gate_transparent_limit=3 if quality_mode else 1,
    )


def dynamics_stats(
    source: AudioMetrics,
    processed: AudioMetrics,
    gate_kwargs: Mapping[str, object],
) -> DynamicsStats:
    lra_reduction = (
        float(source.lra_lu - processed.lra_lu)
        if np.isfinite(source.lra_lu) and np.isfinite(processed.lra_lu)
        else 0.0
    )
    crest_loss = (
        float(source.crest_factor_db - processed.crest_factor_db)
        if np.isfinite(source.crest_factor_db) and np.isfinite(processed.crest_factor_db)
        else 0.0
    )
    maximum_lra = gate_kwargs.get("maximum_lra_reduction_lu")
    risky = False
    if maximum_lra is not None:
        risky = lra_dynamics_risk(
            lra_reduction_lu=lra_reduction,
            final_lra_lu=processed.lra_lu,
            crest_factor_loss_db=crest_loss,
            maximum_lra_reduction_lu=float(maximum_lra),
            minimum_final_lra_lu=float(gate_kwargs.get("minimum_final_lra_lu", 3.5)),
            maximum_crest_factor_loss_db=float(
                gate_kwargs.get("maximum_crest_factor_loss_db", 0.75)
            ),
        )
    return DynamicsStats(
        lra_reduction_lu=lra_reduction,
        crest_factor_loss_db=crest_loss,
        risky=bool(risky),
    )


def classify_dynamics_origin(
    *,
    source: AudioMetrics,
    base: AudioMetrics,
    final: AudioMetrics,
    gate_kwargs: Mapping[str, object],
) -> str:
    base_stats = dynamics_stats(source, base, gate_kwargs)
    if base_stats.risky:
        return "base"
    final_stats = dynamics_stats(source, final, gate_kwargs)
    if final_stats.risky:
        return "fullness"
    return "none"


def performance_level(total_seconds: float) -> str:
    total = float(total_seconds)
    if total > 240.0:
        return "error"
    if total > 120.0:
        return "warning"
    return ""


def slowest_stage(stage_seconds: Mapping[str, float]) -> tuple[str, float]:
    if not stage_seconds:
        return "", 0.0
    name, seconds = max(stage_seconds.items(), key=lambda item: float(item[1]))
    return str(name), float(seconds)
