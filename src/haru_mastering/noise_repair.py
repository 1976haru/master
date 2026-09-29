from __future__ import annotations

import csv
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import soundfile as sf
from scipy import signal


NOISE_REPAIR_MODES = {"OFF", "AUTO", "LIGHT", "MEDIUM"}
DETECTED_TYPES = {"HISS", "STATIC", "CLICK_CRACKLE", "HUM", "HIGH_FREQ_ARTIFACT"}
REPORT_FIELDS = (
    "Track", "Filename", "IntroNoiseScore", "DetectedType", "RepairMode",
    "ReductionStrength", "BeforeRMS", "AfterRMS", "HighFreqDelta", "Result",
    "Recommendation", "Warnings",
)


@dataclass(frozen=True)
class NoiseRepairSettings:
    mode: str = "AUTO"
    intro_first: bool = True
    intro_seconds: float = 15.0

    def normalized(self) -> "NoiseRepairSettings":
        mode = str(self.mode or "AUTO").upper()
        return NoiseRepairSettings(
            mode=mode if mode in NOISE_REPAIR_MODES else "AUTO",
            intro_first=bool(self.intro_first),
            intro_seconds=min(30.0, max(5.0, float(self.intro_seconds or 15.0))),
        )


@dataclass
class SegmentFeatures:
    rms_dbfs: float
    peak_dbfs: float
    high_ratio: float
    very_high_ratio: float
    flatness: float
    transient_rate: float
    hum_50_score: float
    hum_60_score: float
    quiet_ratio: float


@dataclass
class NoiseAnalysis:
    decision: str = "CLEAN"
    score: float = 0.0
    detected_types: list[str] = field(default_factory=list)
    intro: SegmentFeatures | None = None
    middle: SegmentFeatures | None = None
    tail: SegmentFeatures | None = None
    recommendation: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class IntegrityMetrics:
    rms_dbfs: float
    peak_dbfs: float
    high_ratio: float
    duration_seconds: float
    channels: int
    clipped_samples: int


@dataclass
class NoiseRepairResult:
    source: str
    output: str
    analysis: NoiseAnalysis
    requested_mode: str
    applied_mode: str
    result: str
    reduction_db: float = 0.0
    before_rms: float = float("nan")
    after_rms: float = float("nan")
    high_freq_delta_db: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def report_row(self, track: int | str = "") -> dict[str, str]:
        kinds = "/".join(self.analysis.detected_types) or "NONE"
        return {
            "Track": str(track),
            "Filename": Path(self.source).name,
            "IntroNoiseScore": f"{self.analysis.score:.1f}",
            "DetectedType": kinds,
            "RepairMode": self.applied_mode,
            "ReductionStrength": f"{self.reduction_db:.1f} dB" if self.reduction_db else "BYPASS",
            "BeforeRMS": _fmt(self.before_rms),
            "AfterRMS": _fmt(self.after_rms),
            "HighFreqDelta": f"{self.high_freq_delta_db:.2f} dB",
            "Result": self.result,
            "Recommendation": self.analysis.recommendation,
            "Warnings": " | ".join([*self.analysis.warnings, *self.warnings]),
        }


def _fmt(value: float) -> str:
    return "" if not math.isfinite(value) else f"{value:.2f}"


def _db(value: float, floor: float = -120.0) -> float:
    return max(floor, 20.0 * math.log10(max(float(value), 10 ** (floor / 20.0))))


def _mono(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float64)
    if values.ndim == 1:
        return values
    return np.mean(values, axis=1)


def _band_power(freqs: np.ndarray, power: np.ndarray, low: float, high: float) -> float:
    mask = (freqs >= low) & (freqs < high)
    return float(np.sum(power[mask])) if np.any(mask) else 0.0


def _hum_score(freqs: np.ndarray, power: np.ndarray, fundamental: float) -> float:
    total = max(_band_power(freqs, power, 35.0, 500.0), 1e-20)
    selected = 0.0
    for harmonic in range(1, 7):
        center = fundamental * harmonic
        selected += _band_power(freqs, power, center - 1.5, center + 1.5)
    nearby = max(_band_power(freqs, power, 35.0, 500.0) - selected, 1e-20)
    concentration = selected / total
    contrast = selected / nearby
    return float(np.clip(100.0 * concentration * min(2.0, contrast), 0.0, 100.0))


def extract_features(audio: np.ndarray, sample_rate: int) -> SegmentFeatures:
    mono = _mono(audio)
    if mono.size < 32:
        return SegmentFeatures(-120.0, -120.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    mono = mono - np.mean(mono)
    rms = float(np.sqrt(np.mean(np.square(mono))))
    peak = float(np.max(np.abs(mono)))
    nperseg = min(4096, mono.size)
    freqs, psd = signal.welch(mono, fs=sample_rate, nperseg=nperseg, noverlap=nperseg // 2)
    total = max(float(np.sum(psd)), 1e-20)
    high = _band_power(freqs, psd, 7000.0, min(16000.0, sample_rate / 2.0)) / total
    very_high = _band_power(freqs, psd, 11000.0, min(19000.0, sample_rate / 2.0)) / total
    positive = psd[psd > 1e-20]
    flatness = float(np.exp(np.mean(np.log(positive))) / np.mean(positive)) if positive.size else 0.0
    diff = np.diff(mono)
    robust = max(float(np.median(np.abs(diff - np.median(diff)))) * 1.4826, 1e-8)
    spikes = np.abs(diff) > max(0.025, robust * 12.0)
    transient_rate = float(np.count_nonzero(spikes) / max(len(diff), 1) * sample_rate)
    frame = max(64, int(sample_rate * 0.05))
    usable = mono[: (len(mono) // frame) * frame]
    if usable.size:
        frame_rms = np.sqrt(np.mean(usable.reshape(-1, frame) ** 2, axis=1))
        quiet_ratio = float(np.mean(frame_rms < 10 ** (-35.0 / 20.0)))
    else:
        quiet_ratio = 1.0
    return SegmentFeatures(
        _db(rms), _db(peak), high, very_high, flatness, transient_rate,
        _hum_score(freqs, psd, 50.0), _hum_score(freqs, psd, 60.0), quiet_ratio,
    )


def _slice(audio: np.ndarray, sample_rate: int, start: float, length: float) -> np.ndarray:
    first = max(0, int(start * sample_rate))
    last = min(len(audio), first + max(1, int(length * sample_rate)))
    return audio[first:last]


def analyze_audio(audio: np.ndarray, sample_rate: int, *, intro_seconds: float = 15.0, intro_first: bool = True) -> NoiseAnalysis:
    duration = len(audio) / float(sample_rate)
    intro = extract_features(_slice(audio, sample_rate, 0.0, min(intro_seconds, duration)), sample_rate)
    sample_length = min(8.0, max(2.0, duration / 5.0))
    middle = extract_features(_slice(audio, sample_rate, max(0.0, duration / 2 - sample_length / 2), sample_length), sample_rate)
    tail = extract_features(_slice(audio, sample_rate, max(0.0, duration - sample_length), sample_length), sample_rate)
    detected: list[str] = []
    score = 0.0

    # Hiss needs a quiet context, persistence and noise-like spectral shape. This protects
    # bright cymbals, breath and guitar attacks that are tonal/transient rather than flat.
    hiss_context = intro.rms_dbfs < -21.0 and intro.quiet_ratio > 0.08
    hiss_strength = max(0.0, (intro.high_ratio - 0.055) * 180.0) + max(0.0, (intro.flatness - 0.08) * 45.0)
    if hiss_context and intro.high_ratio > 0.06 and intro.flatness > 0.07 and hiss_strength >= 8.0:
        detected.append("HISS")
        score += min(42.0, hiss_strength)
        if middle.high_ratio > 0.09 and middle.flatness > 0.06:
            detected.append("STATIC")
            score += 8.0

    if intro.transient_rate >= 0.8 and intro.rms_dbfs < -18.0:
        detected.append("CLICK_CRACKLE")
        score += min(32.0, 8.0 + intro.transient_rate * 4.0)

    hum_value = max(intro.hum_50_score, intro.hum_60_score)
    if intro.rms_dbfs < -16.0 and hum_value >= 18.0:
        detected.append("HUM")
        score += min(35.0, hum_value * 0.9)

    body_vhf = max(middle.very_high_ratio, tail.very_high_ratio)
    if intro.very_high_ratio > 0.18 and intro.flatness > 0.12 and body_vhf > 0.12:
        detected.append("HIGH_FREQ_ARTIFACT")
        score += 26.0

    detected = list(dict.fromkeys(detected))
    if intro_first and not detected:
        score *= 0.5
    score = float(np.clip(score, 0.0, 100.0))
    if "HIGH_FREQ_ARTIFACT" in detected:
        decision, recommendation = "NEEDS_REVIEW", "REGENERATE / SUNO EDIT 권장"
    elif score >= 52.0:
        decision, recommendation = "MEDIUM_REPAIR", "복원 후 인트로 확인"
    elif score >= 12.0:
        decision, recommendation = "LIGHT_REPAIR", "복원 후 인트로 확인"
    else:
        decision, recommendation = "CLEAN", ""
    return NoiseAnalysis(decision, score, detected, intro, middle, tail, recommendation)


def analyze_file(path: str | Path, *, intro_seconds: float = 15.0, intro_first: bool = True) -> NoiseAnalysis:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float64")
    return analyze_audio(audio, sample_rate, intro_seconds=intro_seconds, intro_first=intro_first)


def integrity_metrics(path: str | Path) -> IntegrityMetrics:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float64")
    features = extract_features(audio, sample_rate)
    return IntegrityMetrics(
        features.rms_dbfs, features.peak_dbfs, features.high_ratio,
        len(audio) / float(sample_rate), int(audio.shape[1]), int(np.count_nonzero(np.abs(audio) >= 1.0)),
    )


def available_filters(ffmpeg: str) -> set[str]:
    try:
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=15,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    text = completed.stdout + completed.stderr
    return {name for name in ("afftdn", "adeclick", "adeclip", "bandreject") if name in text}


def _repair_chain(analysis: NoiseAnalysis, mode: str, filters: set[str]) -> tuple[list[str], list[str], float]:
    chain: list[str] = []
    warnings: list[str] = []
    reduction = 3.5 if mode == "LIGHT" else 6.0
    if "CLICK_CRACKLE" in analysis.detected_types:
        if "adeclick" in filters:
            chain.append("adeclick=window=55:overlap=75:threshold=2.5:burst=2:method=a")
        else:
            warnings.append("adeclick unavailable; click repair skipped")
    if {"HISS", "STATIC"} & set(analysis.detected_types):
        if "afftdn" in filters:
            # nf is deliberately mild. tn tracks slow changes without an aggressive fixed profile.
            chain.append(f"afftdn=nr={reduction:.1f}:nf=-50:tn=1:gs=5")
        else:
            warnings.append("afftdn unavailable; broadband repair skipped")
    if "HUM" in analysis.detected_types:
        fundamental = 60.0 if analysis.intro and analysis.intro.hum_60_score >= analysis.intro.hum_50_score else 50.0
        if "bandreject" in filters:
            harmonics = 2 if mode == "LIGHT" else 3
            chain.extend(f"bandreject=f={fundamental * n:.1f}:width_type=h:width=3" for n in range(1, harmonics + 1))
        else:
            warnings.append("bandreject unavailable; hum repair skipped")
    return chain, warnings, reduction


def _run_ffmpeg(ffmpeg: str, source: Path, output: Path, chain: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
         "-af", ",".join(chain), "-c:a", "pcm_s24le", str(output)],
        capture_output=True, text=True, encoding="utf-8", errors="ignore",
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )
    return completed.returncode == 0, completed.stderr.strip()


def _unsafe_change(before: IntegrityMetrics, after: IntegrityMetrics) -> list[str]:
    warnings: list[str] = []
    if abs(before.duration_seconds - after.duration_seconds) > 0.01:
        warnings.append("duration changed")
    if before.channels != after.channels:
        warnings.append("channel count changed")
    if after.clipped_samples > before.clipped_samples or after.peak_dbfs > 0.01:
        warnings.append("new clipping")
    if abs(after.rms_dbfs - before.rms_dbfs) > 4.5:
        warnings.append("RMS change exceeds 4.5 dB")
    high_delta = _db(after.high_ratio) - _db(before.high_ratio)
    if high_delta < -2.5:
        warnings.append("high-frequency loss exceeds 2.5 dB")
    return warnings


def repair_file(source: str | Path, output: str | Path, ffmpeg: str | None, settings: NoiseRepairSettings) -> NoiseRepairResult:
    source_path, output_path = Path(source), Path(output)
    cfg = settings.normalized()
    if cfg.mode == "OFF":
        return NoiseRepairResult(
            str(source_path), str(source_path), NoiseAnalysis(), cfg.mode, "OFF", "CLEAN"
        )
    analysis = analyze_file(source_path, intro_seconds=cfg.intro_seconds, intro_first=cfg.intro_first)
    before = integrity_metrics(source_path)
    if cfg.mode == "AUTO" and analysis.decision == "CLEAN":
        return NoiseRepairResult(str(source_path), str(source_path), analysis, cfg.mode, "OFF", "CLEAN", before_rms=before.rms_dbfs, after_rms=before.rms_dbfs)
    if cfg.mode == "AUTO" and analysis.decision == "NEEDS_REVIEW":
        return NoiseRepairResult(str(source_path), str(source_path), analysis, cfg.mode, "OFF", "NEEDS_REVIEW", before_rms=before.rms_dbfs, after_rms=before.rms_dbfs)
    applied = cfg.mode if cfg.mode in {"LIGHT", "MEDIUM"} else analysis.decision.replace("_REPAIR", "")
    if not ffmpeg:
        return NoiseRepairResult(str(source_path), str(source_path), analysis, cfg.mode, "OFF", "NEEDS_REVIEW", before_rms=before.rms_dbfs, after_rms=before.rms_dbfs, warnings=["FFmpeg unavailable; repair skipped"])
    filters = available_filters(ffmpeg)
    chain, warnings, reduction = _repair_chain(analysis, applied, filters)
    if not chain:
        result = "NEEDS_REVIEW" if analysis.detected_types else "CLEAN"
        return NoiseRepairResult(str(source_path), str(source_path), analysis, cfg.mode, "OFF", result, before_rms=before.rms_dbfs, after_rms=before.rms_dbfs, warnings=warnings)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok, error = _run_ffmpeg(ffmpeg, source_path, output_path, chain)
    if not ok:
        output_path.unlink(missing_ok=True)
        warnings.append(f"repair failed: {error[-300:]}")
        return NoiseRepairResult(str(source_path), str(source_path), analysis, cfg.mode, "OFF", "NEEDS_REVIEW", before_rms=before.rms_dbfs, after_rms=before.rms_dbfs, warnings=warnings)
    after = integrity_metrics(output_path)
    guard = _unsafe_change(before, after)
    if guard and applied == "MEDIUM":
        output_path.unlink(missing_ok=True)
        light_chain, light_warnings, reduction = _repair_chain(analysis, "LIGHT", filters)
        warnings.extend([*guard, "MEDIUM reduced to LIGHT by integrity guard", *light_warnings])
        ok, error = _run_ffmpeg(ffmpeg, source_path, output_path, light_chain)
        applied = "LIGHT"
        if ok:
            after = integrity_metrics(output_path)
            guard = _unsafe_change(before, after)
    if not ok or guard:
        output_path.unlink(missing_ok=True)
        warnings.extend(guard or [f"repair failed: {error[-300:]}"])
        analysis.recommendation = "REGENERATE / SUNO EDIT 권장"
        return NoiseRepairResult(str(source_path), str(source_path), analysis, cfg.mode, "OFF", "NEEDS_REVIEW", before_rms=before.rms_dbfs, after_rms=before.rms_dbfs, warnings=warnings)
    high_delta = _db(after.high_ratio) - _db(before.high_ratio)
    return NoiseRepairResult(
        str(source_path), str(output_path), analysis, cfg.mode, applied,
        f"REPAIRED_{applied}", reduction, before.rms_dbfs, after.rms_dbfs, high_delta, warnings,
    )


def write_noise_report(path: str | Path, results: Iterable[NoiseRepairResult]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for index, result in enumerate(results, 1):
            writer.writerow(result.report_row(index))
    return target


def summary(results: Iterable[NoiseRepairResult]) -> dict[str, int]:
    counts = {"CLEAN": 0, "REPAIRED_LIGHT": 0, "REPAIRED_MEDIUM": 0, "NEEDS_REVIEW": 0}
    for result in results:
        counts[result.result if result.result in counts else "NEEDS_REVIEW"] += 1
    return counts


def load_settings(path: str | Path) -> NoiseRepairSettings:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        payload = {}
    return NoiseRepairSettings(
        mode=payload.get("noise_repair_mode", "AUTO"),
        intro_first=payload.get("noise_repair_intro_first", True),
        intro_seconds=payload.get("noise_repair_intro_seconds", 15.0),
    ).normalized()


def save_settings(path: str | Path, settings: NoiseRepairSettings) -> None:
    target = Path(path)
    payload: dict = {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        pass
    cfg = settings.normalized()
    payload.update({
        "noise_repair_mode": cfg.mode,
        "noise_repair_intro_first": cfg.intro_first,
        "noise_repair_intro_seconds": cfg.intro_seconds,
    })
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)
