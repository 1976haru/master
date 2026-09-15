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
    base_metrics = analyze_file(base)
    decision = decide_fullness(base_metrics, genre_key=key, mode="RICH", profile=profile)
    fullness_analysis_sec = time.perf_counter() - start

    fullness_render_count = 0
    fullness_render_sec = 0.0
    quality_gate_sec = 0.0
    result = None
    reasons: list[str] = []
    for attempt in range(2):
        start = time.perf_counter()
        process_fullness(
            base,
            destination,
            decision,
            source_metrics=base_metrics,
            analyze_after=False,
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
        )
        quality_gate_sec += time.perf_counter() - start
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
        )
        quality_gate_sec += time.perf_counter() - start

    codec_sec, codec_safe = _codec_once(app, destination, profile)
    total = render_sec + fullness_analysis_sec + fullness_render_sec + quality_gate_sec + codec_sec
    return {
        "version": "v3.9",
        "render_sec": render_sec,
        "fullness_analysis_sec": fullness_analysis_sec,
        "fullness_render_sec": fullness_render_sec,
        "fullness_render_count": fullness_render_count,
        "quality_gate_sec": quality_gate_sec,
        "codec_sec": codec_sec,
        "total_sec": total,
        "status": result.status if result is not None else "UNKNOWN",
        "codec_safe": codec_safe,
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

    payload = {
        "synthetic_seconds": seconds,
        "baseline": old,
        "latest": new,
        "speedup_ratio": (
            old["total_sec"] / new["total_sec"] if new["total_sec"] > 0 else None
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
