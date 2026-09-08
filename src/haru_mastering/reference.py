from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .analysis import analyze_file


@dataclass(frozen=True)
class ReferenceCorrection:
    band: str
    center_hz: float
    gain_db: float


@dataclass(frozen=True)
class ReferencePlan:
    corrections: tuple[ReferenceCorrection, ...]
    source_lufs_i: float
    reference_lufs_i: float
    max_correction_db: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_lufs_i": self.source_lufs_i,
            "reference_lufs_i": self.reference_lufs_i,
            "max_correction_db": self.max_correction_db,
            "corrections": [asdict(item) for item in self.corrections],
        }


_BAND_CENTERS = {
    "20-60Hz": 35.0,
    "60-120Hz": 85.0,
    "120-250Hz": 175.0,
    "250-500Hz": 350.0,
    "500-1000Hz": 700.0,
    "1000-2000Hz": 1400.0,
    "2000-5000Hz": 3200.0,
    "5000-10000Hz": 7000.0,
    "10000-20000Hz": 14000.0,
}


def _smooth(values: np.ndarray) -> np.ndarray:
    if values.size < 3:
        return values.copy()
    padded = np.pad(values, (1, 1), mode="edge")
    return 0.25 * padded[:-2] + 0.50 * padded[1:-1] + 0.25 * padded[2:]


def build_reference_plan(
    source_path: str | Path,
    reference_path: str | Path,
    *,
    max_correction_db: float = 1.0,
    ignore_sub_below_hz: float = 45.0,
) -> ReferencePlan:
    if max_correction_db <= 0:
        raise ValueError("max_correction_db must be positive")

    source = analyze_file(source_path)
    reference = analyze_file(reference_path)
    labels = [label for label in _BAND_CENTERS if label in source.band_energy_db]

    differences = np.array(
        [reference.band_energy_db[label] - source.band_energy_db[label] for label in labels],
        dtype=np.float64,
    )
    finite = np.isfinite(differences)
    if not np.any(finite):
        raise ValueError("No usable spectral bands for reference matching")

    # Loudness matching is handled elsewhere. Remove the broad average difference so this
    # routine only suggests tonal-shape changes rather than a disguised gain boost.
    centered = differences.copy()
    centered[finite] -= float(np.mean(centered[finite]))
    centered[~finite] = 0.0
    centered = _smooth(centered)
    centered = np.clip(centered, -float(max_correction_db), float(max_correction_db))

    corrections: list[ReferenceCorrection] = []
    for label, gain in zip(labels, centered, strict=True):
        center = _BAND_CENTERS[label]
        if center < ignore_sub_below_hz:
            gain = min(float(gain), 0.0)
        if abs(float(gain)) < 0.10:
            continue
        corrections.append(
            ReferenceCorrection(band=label, center_hz=center, gain_db=round(float(gain), 2))
        )

    return ReferencePlan(
        corrections=tuple(corrections),
        source_lufs_i=source.lufs_i,
        reference_lufs_i=reference.lufs_i,
        max_correction_db=float(max_correction_db),
    )


def ffmpeg_equalizer_chain(plan: ReferencePlan) -> str:
    filters = [
        f"equalizer=f={item.center_hz:.1f}:t=q:w=1.0:g={item.gain_db:.2f}"
        for item in plan.corrections
    ]
    return ",".join(filters)
