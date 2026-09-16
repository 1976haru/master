from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from .analysis import AudioMetrics, analyze_array


@dataclass(frozen=True)
class TransparentGainDecision:
    desired_gain_db: float
    peak_safe_gain_db: float
    applied_gain_db: float
    effective_target_lufs: float
    projected_final_tp_dbtp: float
    limited_by_peak: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide_gain_only(
    *,
    source_lufs: float,
    source_true_peak_dbtp: float,
    target_lufs: float,
    true_peak_ceiling_dbtp: float,
    safety_margin_db: float = 0.05,
) -> TransparentGainDecision:
    desired = float(target_lufs) - float(source_lufs)
    peak_safe = (
        float(true_peak_ceiling_dbtp)
        - max(0.0, float(safety_margin_db))
        - float(source_true_peak_dbtp)
    )
    applied = min(desired, peak_safe)
    limited = applied < desired - 1e-9
    reason = "peak safety" if limited else "constant gain"
    return TransparentGainDecision(
        desired_gain_db=round(desired, 3),
        peak_safe_gain_db=round(peak_safe, 3),
        applied_gain_db=round(applied, 3),
        effective_target_lufs=round(float(source_lufs) + applied, 3),
        projected_final_tp_dbtp=round(float(source_true_peak_dbtp) + applied, 3),
        limited_by_peak=limited,
        reason=reason,
    )


def render_gain_only(
    source: str | Path,
    destination: str | Path,
    *,
    gain_db: float,
    sample_rate: int | None = None,
    subtype: str = "PCM_24",
    true_peak_oversample: int = 4,
) -> tuple[bool, str, AudioMetrics | None, np.ndarray | None, int | None]:
    """Render source with constant gain only; no dynamics DSP is involved."""
    try:
        audio, source_rate = sf.read(Path(source), always_2d=True, dtype="float64")
        output_rate = int(sample_rate or source_rate)
        if output_rate != int(source_rate):
            return False, "gain-only render cannot resample audio", None, None, None
        scaled = np.asarray(audio, dtype=np.float64) * (10.0 ** (float(gain_db) / 20.0))
        if not np.all(np.isfinite(scaled)):
            return False, "gain-only render produced non-finite samples", None, None, None
        if np.max(np.abs(scaled), initial=0.0) > 1.0:
            return False, "gain-only render would clip", None, None, None
        sf.write(Path(destination), scaled, output_rate, subtype=subtype)
        metrics = analyze_array(
            scaled,
            output_rate,
            true_peak_oversample=int(true_peak_oversample),
        )
        return True, "", metrics, scaled, output_rate
    except Exception as exc:
        return False, str(exc), None, None, None
