from __future__ import annotations

import math
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_file
from haru_mastering.auto_finish import inspect_tail
from haru_mastering.codec_preview import check_codec_safety
from haru_mastering.fullness import decide, process
from haru_mastering.quality_gate import evaluate_master


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "ab_v38_synthetic"


def _gain_db(audio: np.ndarray, gain_db: float) -> np.ndarray:
    return audio * (10.0 ** (float(gain_db) / 20.0))


def _make_old_pop_like(sample_rate: int, seconds: int) -> np.ndarray:
    t = np.arange(sample_rate * seconds, dtype=np.float64) / sample_rate
    envelope = 0.75 + 0.20 * np.sin(2.0 * np.pi * 0.33 * t)
    mono = envelope * (
        0.008 * np.sin(2.0 * np.pi * 95.0 * t)
        + 0.009 * np.sin(2.0 * np.pi * 180.0 * t)
        + 0.008 * np.sin(2.0 * np.pi * 320.0 * t)
        + 0.055 * np.sin(2.0 * np.pi * 1400.0 * t)
        + 0.012 * np.sin(2.0 * np.pi * 3200.0 * t)
    )
    side = 0.004 * np.sin(2.0 * np.pi * 760.0 * t)
    audio = np.column_stack((mono + side, mono - side))
    fade = min(audio.shape[0], int(sample_rate * 1.00))
    audio[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    audio[-int(sample_rate * 0.15) :] = 0.0
    audio[-1] = 0.0
    return audio


def _write_lufs_matched(path: Path, target_lufs: float = -14.0) -> None:
    sr = 48000
    audio = _make_old_pop_like(sr, 8)
    raw = OUT / "raw.wav"
    sf.write(raw, audio, sr, subtype="PCM_24")
    metrics = analyze_file(raw)
    audio = _gain_db(audio, target_lufs - metrics.lufs_i)
    sf.write(path, audio, sr, subtype="PCM_24")


def _tail_label(path: Path) -> str:
    tail = inspect_tail(
        path,
        window_ms=100.0,
        end_rms_threshold_dbfs=-50.0,
        last_sample_threshold_dbfs=-60.0,
        energetic_end_threshold_dbfs=-35.0,
    )
    return "SAFE" if not tail.hard_cut and not tail.energetic_end else "RISK"


def _band(metrics, label: str) -> str:
    value = metrics.band_energy_db.get(label, float("-inf"))
    return f"{value:.2f}" if math.isfinite(value) else "-inf"


def _print_row(name: str, path: Path, *, low_corr: float, codec: str) -> None:
    metrics = analyze_file(path)
    print(
        ",".join(
            [
                name,
                f"{metrics.lufs_i:.2f}",
                f"{metrics.true_peak_dbtp:.2f}",
                f"{metrics.lra_lu:.2f}",
                f"{metrics.crest_factor_db:.2f}",
                f"{metrics.rms_dbfs:.2f}",
                _band(metrics, "60-120Hz"),
                _band(metrics, "120-250Hz"),
                _band(metrics, "250-500Hz"),
                f"{metrics.stereo_correlation:.3f}",
                f"{low_corr:.3f}",
                str(metrics.clipped_sample_count),
                _tail_label(path),
                codec,
            ]
        )
    )


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / "old_pop_v372_same_lufs.wav"
    full = OUT / "old_pop_v38_fullness.wav"
    _write_lufs_matched(base)
    base_metrics = analyze_file(base)
    decision = decide(base_metrics, genre_key="OLD POP", mode="RICH", strength_percent=100)
    render = process(base, full, decision)

    base_gate = evaluate_master(
        base,
        base,
        target_lufs_i=base_metrics.lufs_i,
        true_peak_ceiling_dbtp=-1.5,
        maximum_lra_reduction_lu=0.6,
        true_peak_tolerance_db=99.0,
    )
    full_gate = evaluate_master(
        base,
        full,
        target_lufs_i=base_metrics.lufs_i,
        true_peak_ceiling_dbtp=-1.5,
        maximum_lra_reduction_lu=0.6,
        true_peak_tolerance_db=99.0,
    )
    ffmpeg = shutil.which("ffmpeg")
    base_codec = check_codec_safety(base, true_peak_ceiling_dbtp=-1.5, tolerance_db=0.05, ffmpeg=ffmpeg)
    full_codec = check_codec_safety(full, true_peak_ceiling_dbtp=-1.5, tolerance_db=0.05, ffmpeg=ffmpeg)

    print(f"Fullness decision: {decision.to_dict()}")
    print(f"Level match gain dB: {render.level_match_gain_db:+.3f}")
    print(
        "version,final_LUFS,True_Peak,LRA,crest_factor,RMS,"
        "60-120Hz,120-250Hz,250-500Hz,stereo_corr,low_band_corr,"
        "clipping,Tail,codec_preview"
    )
    _print_row(
        "v3.7.2_synthetic",
        base,
        low_corr=base_gate.low_band_stereo_correlation,
        codec="SAFE" if base_codec.safe else "RISK",
    )
    _print_row(
        "v3.8_fullness_synthetic",
        full,
        low_corr=full_gate.low_band_stereo_correlation,
        codec="SAFE" if full_codec.safe else "RISK",
    )
    print(f"Output folder: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
