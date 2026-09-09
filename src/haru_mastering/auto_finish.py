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
    attempted_fades_ms: tuple[float, ...] = ()
    target_end_rms_dbfs: float | None = None


def _dbfs(value: float) -> float:
    value = abs(float(value))
    if value <= 1e-15:
        return float("-inf")
    return 20.0 * math.log10(value)


def _tail_metrics_from_audio(
    audio: np.ndarray,
    sample_rate: int,
    *,
    window_ms: float,
    end_rms_threshold_dbfs: float,
    last_sample_threshold_dbfs: float,
    energetic_end_threshold_dbfs: float | None,
) -> TailMetrics:
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


def inspect_tail(
    path: str | Path,
    *,
    window_ms: float = 100.0,
    end_rms_threshold_dbfs: float = -50.0,
    last_sample_threshold_dbfs: float = -60.0,
    energetic_end_threshold_dbfs: float | None = None,
) -> TailMetrics:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float64")
    return _tail_metrics_from_audio(
        audio,
        sample_rate,
        window_ms=window_ms,
        end_rms_threshold_dbfs=end_rms_threshold_dbfs,
        last_sample_threshold_dbfs=last_sample_threshold_dbfs,
        energetic_end_threshold_dbfs=energetic_end_threshold_dbfs,
    )


def _faded_copy(audio: np.ndarray, sample_rate: int, fade_ms: float) -> np.ndarray:
    if audio.shape[0] == 0:
        return audio.copy()
    fade_frames = min(
        audio.shape[0],
        max(2, int(round(sample_rate * float(fade_ms) / 1000.0))),
    )
    repaired = audio.copy()
    ramp = np.linspace(1.0, 0.0, fade_frames, dtype=np.float64)[:, None]
    repaired[-fade_frames:] *= ramp
    repaired[-1] = 0.0
    return repaired


def _write_audio_atomic(path: Path, audio: np.ndarray, sample_rate: int, subtype: str) -> None:
    temp = path.with_name(path.stem + ".tailfix.tmp.wav")
    sf.write(temp, audio, sample_rate, subtype=subtype)
    temp.replace(path)


def apply_click_safe_fade(
    path: str | Path,
    *,
    fade_ms: float = 25.0,
) -> Path:
    target = Path(path)
    audio, sample_rate = sf.read(target, always_2d=True, dtype="float64")
    if audio.shape[0] == 0:
        return target
    repaired = _faded_copy(audio, sample_rate, fade_ms)
    info = sf.info(target)
    subtype = info.subtype if info.subtype else "PCM_24"
    _write_audio_atomic(target, repaired, sample_rate, subtype)
    return target


def _adaptive_fade_candidates(
    base_fade_ms: float,
    candidates_ms: Iterable[float] | None,
    maximum_fade_ms: float,
) -> tuple[float, ...]:
    base = max(5.0, float(base_fade_ms))
    maximum = max(base, float(maximum_fade_ms))
    values = (
        list(candidates_ms)
        if candidates_ms is not None
        else [base, base * 1.5, base * 2.0, base * 3.0]
    )
    values.append(base)
    normalized = sorted(
        {
            round(min(maximum, max(5.0, float(value))), 3)
            for value in values
            if np.isfinite(float(value)) and float(value) > 0.0
        }
    )
    if not normalized:
        normalized = [base]
    return tuple(normalized)


def repair_tail_automatically(
    path: str | Path,
    *,
    window_ms: float = 100.0,
    end_rms_threshold_dbfs: float = -50.0,
    last_sample_threshold_dbfs: float = -60.0,
    energetic_end_threshold_dbfs: float = -35.0,
    energetic_fade_ms: float = 400.0,
    energetic_fade_candidates_ms: Iterable[float] | None = None,
    energetic_target_margin_db: float = 0.5,
    maximum_energetic_fade_ms: float = 1200.0,
    hard_cut_fade_ms: float = 25.0,
    micro_fade_ms: float = 5.0,
    micro_fade_last_sample_threshold_dbfs: float = -80.0,
) -> TailRepairResult:
    """Repair the ending automatically while preserving the shortest safe fade.

    Energetic endings are evaluated from the same unmodified master with a fade
    ladder.  The first candidate that clears the gate plus a small safety margin
    is written once.  This avoids repeated fade multiplication while allowing a
    400 ms attempt to expand to 600, 800 or 1200 ms when the ending is stronger.
    Quiet hard cuts still use a short click-safe fade and normal endings receive
    only a tiny micro-fade when the final sample is non-zero.
    """
    target = Path(path)
    audio, sample_rate = sf.read(target, always_2d=True, dtype="float64")
    info = sf.info(target)
    subtype = info.subtype if info.subtype else "PCM_24"

    before = _tail_metrics_from_audio(
        audio,
        sample_rate,
        window_ms=window_ms,
        end_rms_threshold_dbfs=end_rms_threshold_dbfs,
        last_sample_threshold_dbfs=last_sample_threshold_dbfs,
        energetic_end_threshold_dbfs=energetic_end_threshold_dbfs,
    )

    mode = "none"
    fade_ms = 0.0
    attempted: tuple[float, ...] = ()
    target_end_rms: float | None = None
    repaired_audio = audio.copy()

    if before.energetic_end:
        mode = "musical_tail_fade"
        candidates = _adaptive_fade_candidates(
            energetic_fade_ms,
            energetic_fade_candidates_ms,
            maximum_energetic_fade_ms,
        )
        target_end_rms = float(energetic_end_threshold_dbfs) - max(
            0.0, float(energetic_target_margin_db)
        )
        tried: list[float] = []
        selected_audio = None
        selected_ms = candidates[-1]
        for candidate_ms in candidates:
            tried.append(candidate_ms)
            candidate_audio = _faded_copy(audio, sample_rate, candidate_ms)
            candidate_metrics = _tail_metrics_from_audio(
                candidate_audio,
                sample_rate,
                window_ms=window_ms,
                end_rms_threshold_dbfs=end_rms_threshold_dbfs,
                last_sample_threshold_dbfs=last_sample_threshold_dbfs,
                energetic_end_threshold_dbfs=energetic_end_threshold_dbfs,
            )
            selected_audio = candidate_audio
            selected_ms = candidate_ms
            if (
                candidate_metrics.end_rms_dbfs <= target_end_rms
                and not candidate_metrics.hard_cut
            ):
                break
        attempted = tuple(tried)
        fade_ms = float(selected_ms)
        repaired_audio = selected_audio if selected_audio is not None else audio.copy()
    elif before.hard_cut:
        mode = "click_safe_fade"
        fade_ms = float(hard_cut_fade_ms)
        attempted = (fade_ms,)
        repaired_audio = _faded_copy(audio, sample_rate, fade_ms)
    elif before.last_sample_dbfs > float(micro_fade_last_sample_threshold_dbfs):
        mode = "micro_fade"
        fade_ms = float(micro_fade_ms)
        attempted = (fade_ms,)
        repaired_audio = _faded_copy(audio, sample_rate, fade_ms)

    if mode != "none":
        _write_audio_atomic(target, repaired_audio, sample_rate, subtype)

    after = inspect_tail(
        target,
        window_ms=window_ms,
        end_rms_threshold_dbfs=end_rms_threshold_dbfs,
        last_sample_threshold_dbfs=last_sample_threshold_dbfs,
        energetic_end_threshold_dbfs=energetic_end_threshold_dbfs,
    )
    return TailRepairResult(
        mode=mode,
        fade_ms=fade_ms,
        before=before,
        after=after,
        attempted_fades_ms=attempted,
        target_end_rms_dbfs=target_end_rms,
    )


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
