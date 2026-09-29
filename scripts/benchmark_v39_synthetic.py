from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_array, analyze_file
from haru_mastering.fullness import decide as decide_fullness
from haru_mastering.fullness import process as process_fullness
from haru_mastering.fullness import reduce_decision_for_guard_reasons
from haru_mastering.retry_policy import (
    build_track_retry_policy,
    classify_dynamics_origin,
    dynamics_stats,
)


ROOT = Path(__file__).resolve().parents[1]
V372 = ROOT / "Suno15_Mastering_v3_7_2.pyw"
V39 = ROOT / "Suno15_Mastering_v3_9.pyw"


def _load(path: Path, name: str):
    loader = SourceFileLoader(name, str(path))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {path}")
    module = module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def _write_synthetic(path: Path, seconds: int) -> None:
    sr = 48000
    t = np.arange(sr * seconds, dtype=np.float64) / sr
    left = (
        0.045 * np.sin(2.0 * np.pi * 110.0 * t)
        + 0.030 * np.sin(2.0 * np.pi * 220.0 * t)
        + 0.025 * np.sin(2.0 * np.pi * 880.0 * t)
    )
    right = (
        0.043 * np.sin(2.0 * np.pi * 110.0 * t + 0.01)
        + 0.028 * np.sin(2.0 * np.pi * 330.0 * t)
        + 0.023 * np.sin(2.0 * np.pi * 1320.0 * t)
    )
    fade = min(sr, left.shape[0])
    left[-fade:] *= np.linspace(1.0, 0.0, fade)
    right[-fade:] *= np.linspace(1.0, 0.0, fade)
    sf.write(path, np.column_stack((left, right)), sr, subtype="PCM_24")


def _codec_once(app, path: Path, profile: dict) -> tuple[float, bool]:
    start = time.perf_counter()
    result = app.v32.check_codec_safety(
        path,
        true_peak_ceiling_dbtp=float(profile["truePeakCeilingDbtp"]),
        tolerance_db=0.05,
        ffmpeg=app.legacy.get_ffmpeg(),
    )
    return time.perf_counter() - start, bool(result.safe)


def _benchmark_v372(app, source: Path, destination: Path) -> dict:
    genre = "OLD POP"
    legacy = app.v371.v37.legacy
    v32 = app.v371.v37.v32
    gate_kwargs, _auto_cfg, profile = v32._settings(genre)
    ffmpeg = legacy.get_ffmpeg()
    metrics = analyze_file(source)
    factor = legacy.adaptive_factor(metrics.lra_lu)

    start = time.perf_counter()
    first, first_err = legacy.first_pass(ffmpeg, source, genre, factor)
    if not first:
        raise RuntimeError(first_err[-2000:] if first_err else "v3.7.2 first pass failed")
    ok, err = legacy.master_two_pass(ffmpeg, source, destination, genre, factor, first)
    if not ok:
        raise RuntimeError(err[-2000:] if err else "v3.7.2 render failed")
    render_sec = time.perf_counter() - start

    start = time.perf_counter()
    result = v32.evaluate_master(source, destination, **gate_kwargs)
    gate_sec = time.perf_counter() - start
    codec_sec, codec_safe = _codec_once(app.v371.v37, destination, profile)
    total = render_sec + gate_sec + codec_sec
    return {
        "version": "v3.7.2",
        "render_sec": render_sec,
        "quality_gate_sec": gate_sec,
        "codec_sec": codec_sec,
        "total_sec": total,
        "status": result.status,
        "codec_safe": codec_safe,
    }


def _benchmark_v39(app, source: Path, base: Path, destination: Path) -> dict:
    app.install_v39_runtime()
    key = app.composite_key("OLD_POP_LOUNGE", "POP")
    gate_kwargs, _auto_cfg, profile = app.v32._settings(key)
    ffmpeg = app.legacy.get_ffmpeg()
    source_audio, source_sr = sf.read(source, always_2d=True, dtype="float64")
    source_metrics = analyze_array(source_audio, source_sr)
    factor = app.legacy.adaptive_factor(source_metrics.lra_lu)

    start = time.perf_counter()
    first, first_err = app.legacy.first_pass(ffmpeg, source, key, factor)
    if not first:
        raise RuntimeError(first_err[-2000:] if first_err else "v3.9 first pass failed")
    ok, err = app.legacy.master_two_pass(ffmpeg, source, base, key, factor, first)
    if not ok:
        raise RuntimeError(err[-2000:] if err else "v3.9 render failed")
    render_sec = time.perf_counter() - start

    start = time.perf_counter()
    base_audio, base_sr = sf.read(base, always_2d=True, dtype="float64")
    base_metrics = analyze_array(base_audio, base_sr)
    decision = decide_fullness(base_metrics, genre_key=key, mode="RICH", profile=profile)
    fullness_analysis_sec = time.perf_counter() - start

    fullness_render_count = 0
    fullness_render_sec = 0.0
    quality_gate_sec = 0.0
    quality_gate_count = 0
    result = None
    reasons: list[str] = []
    for attempt in range(2):
        start = time.perf_counter()
        render = process_fullness(
            base,
            destination,
            decision,
            source_metrics=base_metrics,
            source_audio=base_audio,
            source_sample_rate=base_sr,
            analyze_after=True,
            return_audio=True,
        )
        fullness_render_sec += time.perf_counter() - start
        fullness_render_count += 1

        start = time.perf_counter()
        result = app.v32.evaluate_master(
            source,
            destination,
            **gate_kwargs,
            source_audio=source_audio,
            source_sample_rate=source_sr,
            source_metrics=source_metrics,
            processed_audio=render.processed_audio,
            processed_sample_rate=render.processed_sample_rate,
            processed_metrics=render.after,
        )
        quality_gate_sec += time.perf_counter() - start
        quality_gate_count += 1
        reasons = list(result.issues)
        if not reasons:
            break
        if attempt == 0:
            decision = reduce_decision_for_guard_reasons(decision, reasons)

    if result is not None and reasons:
        destination.write_bytes(base.read_bytes())
        start = time.perf_counter()
        result = app.v32.evaluate_master(
            source,
            destination,
            **gate_kwargs,
            source_audio=source_audio,
            source_sample_rate=source_sr,
            source_metrics=source_metrics,
            processed_audio=base_audio,
            processed_sample_rate=base_sr,
            processed_metrics=base_metrics,
        )
        quality_gate_sec += time.perf_counter() - start
        quality_gate_count += 1

    codec_sec, codec_safe = _codec_once(app, destination, profile)
    total = render_sec + fullness_analysis_sec + fullness_render_sec + quality_gate_sec + codec_sec
    return {
        "version": "v3.9",
        "render_sec": render_sec,
        "fullness_analysis_sec": fullness_analysis_sec,
        "fullness_render_sec": fullness_render_sec,
        "fullness_render_count": fullness_render_count,
        "quality_gate_sec": quality_gate_sec,
        "quality_gate_count": quality_gate_count,
        "codec_sec": codec_sec,
        "codec_check_count": 1,
        "total_sec": total,
        "status": result.status if result is not None else "UNKNOWN",
        "codec_safe": codec_safe,
    }


def _metric_like(*, lra: float, crest: float, true_peak: float = -1.4):
    from haru_mastering.analysis import AudioMetrics

    return AudioMetrics(
        sample_rate_hz=48000,
        channels=2,
        frames=48000 * 180,
        duration_seconds=180.0,
        lufs_i=-14.0,
        lra_lu=lra,
        sample_peak_dbfs=true_peak,
        true_peak_dbtp=true_peak,
        rms_dbfs=-18.0,
        crest_factor_db=crest,
        dc_offset=(0.0, 0.0),
        clipped_sample_count=0,
        stereo_correlation=0.95,
        side_to_mid_db=-18.0,
        leading_silence_ms=0.0,
        trailing_silence_ms=500.0,
        band_energy_db={},
    )


def _benchmark_v39_dynamics_fixture() -> dict:
    start = time.perf_counter()
    gate = {
        "maximum_lra_reduction_lu": 0.80,
        "minimum_final_lra_lu": 3.50,
        "maximum_crest_factor_loss_db": 0.75,
    }
    source = _metric_like(lra=4.60, crest=9.0)
    base = _metric_like(lra=4.25, crest=8.8)
    final_100 = _metric_like(lra=3.45, crest=8.7, true_peak=-1.01)
    final_60 = _metric_like(lra=3.95, crest=8.8, true_peak=-1.22)
    policy = build_track_retry_policy(
        mode="QUALITY+",
        resolved_maximum_auto_rerenders=4,
        max_fullness_render_passes=2,
    )
    origin = classify_dynamics_origin(source=source, base=base, final=final_100, gate_kwargs=gate)
    candidate_metrics = {100: final_100, 60: final_60}
    strength = 100
    fullness_render_count = 0
    quality_gate_count = 0
    retry_passes = False
    while fullness_render_count < policy.fullness_render_limit:
        fullness_render_count += 1
        quality_gate_count += 1
        candidate = candidate_metrics[strength]
        if not dynamics_stats(source, candidate, gate).risky:
            retry_passes = True
            break
        if strength == 100:
            strength = 60
        else:
            break
    elapsed = time.perf_counter() - start
    return {
        "fixture": "Tokyo Chill + Chill Rap dynamics risk",
        "elapsed_sec": elapsed,
        "dynamics_origin": origin,
        "first_strength_percent": 100,
        "retry_strength_percent": 60,
        "retry_passes": retry_passes,
        "base_render_count": 1,
        "fullness_render_count": fullness_render_count,
        "quality_gate_count": quality_gate_count,
        "codec_check_count": 1,
        "transparent_render_count": 0,
    }


def main() -> int:
    seconds = int(os.environ.get("HARU_BENCH_SECONDS", "180"))
    v372 = _load(V372, "haru_bench_v372")
    v39 = _load(V39, "haru_bench_v39")
    ffmpeg = v39.legacy.get_ffmpeg()
    if not ffmpeg:
        print("FFmpeg not found; benchmark skipped.")
        return 0

    with tempfile.TemporaryDirectory(prefix="haru_v39_bench_") as tmp:
        work = Path(tmp)
        source = work / f"synthetic_{seconds}s.wav"
        _write_synthetic(source, seconds)
        old = _benchmark_v372(v372, source, work / "v372.wav")
        new = _benchmark_v39(v39, source, work / "v39_base.wav", work / "v39.wav")
        dynamics_fixture = _benchmark_v39_dynamics_fixture()

    payload = {
        "synthetic_seconds": seconds,
        "baseline": old,
        "latest": new,
        "dynamics_risk_fixture": dynamics_fixture,
        "speedup_ratio": (
            old["total_sec"] / new["total_sec"] if new["total_sec"] > 0 else None
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
