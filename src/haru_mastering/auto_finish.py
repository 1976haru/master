from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class TailMetrics:
    end_rms_dbfs: float
    last_sample_dbfs: float
    hard_cut: bool
    energetic_end: bool = False


@dataclass(frozen=True)
class TailRepairResult:
    mode: str
    fade_ms: float
    before: TailMetrics
    after: TailMetrics


def _dbfs(value: float) -> float:
    value = abs(float(value))
    if value <= 1e-15:
        return float("-inf")
    return 20.0 * math.log10(value)


def inspect_tail(
    path: str | Path,
    *,
    window_ms: float = 100.0,
    end_rms_threshold_dbfs: float = -50.0,
    last_sample_threshold_dbfs: float = -60.0,
    energetic_end_threshold_dbfs: float | None = None,
) -> TailMetrics:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float64")
    if audio.shape[0] == 0:
        return TailMetrics(float("-inf"), float("-inf"), False, False)
    frames = max(1, int(round(sample_rate * float(window_ms) / 1000.0)))
    tail = audio[-frames:]
    rms = float(np.sqrt(np.mean(np.square(tail)))) if tail.size else 0.0
    last = float(np.max(np.abs(audio[-1])))
    end_rms_dbfs = _dbfs(rms)
    last_sample_dbfs = _dbfs(last)
    hard_cut = (
        end_rms_dbfs > float(end_rms_threshold_dbfs)
        and last_sample_dbfs > float(last_sample_threshold_dbfs)
    )
    energetic_end = (
        energetic_end_threshold_dbfs is not None
        and end_rms_dbfs > float(energetic_end_threshold_dbfs)
    )
    return TailMetrics(end_rms_dbfs, last_sample_dbfs, hard_cut, energetic_end)


def apply_click_safe_fade(
    path: str | Path,
    *,
    fade_ms: float = 25.0,
) -> Path:
    target = Path(path)
    audio, sample_rate = sf.read(target, always_2d=True, dtype="float64")
    if audio.shape[0] == 0:
        return target
    fade_frames = min(audio.shape[0], max(2, int(round(sample_rate * float(fade_ms) / 1000.0))))
    ramp = np.linspace(1.0, 0.0, fade_frames, dtype=np.float64)[:, None]
    repaired = audio.copy()
    repaired[-fade_frames:] *= ramp
    repaired[-1] = 0.0

    info = sf.info(target)
    subtype = info.subtype if info.subtype else "PCM_24"
    temp = target.with_name(target.stem + ".tailfix.tmp.wav")
    sf.write(temp, repaired, sample_rate, subtype=subtype)
    temp.replace(target)
    return target


def repair_tail_automatically(
    path: str | Path,
    *,
    window_ms: float = 100.0,
    end_rms_threshold_dbfs: float = -50.0,
    last_sample_threshold_dbfs: float = -60.0,
    energetic_end_threshold_dbfs: float = -35.0,
    energetic_fade_ms: float = 400.0,
    hard_cut_fade_ms: float = 25.0,
    micro_fade_ms: float = 5.0,
    micro_fade_last_sample_threshold_dbfs: float = -80.0,
) -> TailRepairResult:
    """Repair the ending without asking the user to judge audio manually.

    A loud ending receives a longer 300-500 ms musical fade.  A quiet digital
    discontinuity receives a short click-safe fade.  Otherwise only a tiny
    micro-fade is applied when the last sample is still measurably non-zero.
    The pre-repair measurement is returned so reports cannot hide a hard cut
    merely because the repaired last sample became zero.
    """
    before = inspect_tail(
        path,
        window_ms=window_ms,
        end_rms_threshold_dbfs=end_rms_threshold_dbfs,
        last_sample_threshold_dbfs=last_sample_threshold_dbfs,
        energetic_end_threshold_dbfs=energetic_end_threshold_dbfs,
    )

    mode = "none"
    fade_ms = 0.0
    if before.energetic_end:
        mode = "musical_tail_fade"
        fade_ms = float(energetic_fade_ms)
        apply_click_safe_fade(path, fade_ms=fade_ms)
    elif before.hard_cut:
        mode = "click_safe_fade"
        fade_ms = float(hard_cut_fade_ms)
        apply_click_safe_fade(path, fade_ms=fade_ms)
    elif before.last_sample_dbfs > float(micro_fade_last_sample_threshold_dbfs):
        mode = "micro_fade"
        fade_ms = float(micro_fade_ms)
        apply_click_safe_fade(path, fade_ms=fade_ms)

    after = inspect_tail(
        path,
        window_ms=window_ms,
        end_rms_threshold_dbfs=end_rms_threshold_dbfs,
        last_sample_threshold_dbfs=last_sample_threshold_dbfs,
        energetic_end_threshold_dbfs=energetic_end_threshold_dbfs,
    )
    return TailRepairResult(mode=mode, fade_ms=fade_ms, before=before, after=after)


def ensure_release_tree(output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    paths = {
        "release": root / "01_RELEASE_READY",
        "review": root / "02_NEEDS_REVIEW",
        "report": root / "03_REPORT",
        "codec": root / "04_CODEC_PREVIEW",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def organize_release_files(
    output_dir: str | Path,
    rows: Iterable[tuple[Path, str]],
) -> dict[str, Path]:
    paths = ensure_release_tree(output_dir)
    for source, status in rows:
        if not source.exists():
            continue
        destination_dir = paths["release"] if status == "PASS" else paths["review"]
        shutil.copy2(source, destination_dir / source.name)
    return paths


def write_beginner_summary(
    output_dir: str | Path,
    *,
    pass_count: int,
    review_count: int,
    auto_fixed_count: int,
    codec_safe_count: int,
    total_count: int,
) -> Path:
    paths = ensure_release_tree(output_dir)
    ready = review_count == 0 and pass_count == total_count
    lines = [
        "HARU MASTERING 자동 최종 판정",
        "=" * 44,
        f"최종 상태: {'배포 가능' if ready else '배포 보류 곡 있음'}",
        f"전체 곡: {total_count}",
        f"PASS: {pass_count}",
        f"자동 수정 완료: {auto_fixed_count}",
        f"검토 필요: {review_count}",
        f"코덱 안전 확인: {codec_safe_count}/{total_count}",
        "",
        "사용 방법:",
        "- 01_RELEASE_READY 폴더의 WAV만 유튜브/음원유통에 사용하세요.",
        "- 02_NEEDS_REVIEW에 파일이 있으면 그 파일은 배포하지 마세요.",
        "- 사용자가 LUFS/LRA/dBTP를 직접 판단할 필요는 없습니다.",
    ]
    path = paths["report"] / "초보자_최종판정.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
