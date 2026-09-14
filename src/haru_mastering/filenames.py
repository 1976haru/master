from __future__ import annotations

from pathlib import Path
from typing import Iterator


FINAL_OUTPUT_DIRS = ("", "01_RELEASE_READY", "02_NEEDS_REVIEW")


def final_output_name(track: str | Path) -> str:
    """Return the user-facing mastered WAV name without mastering suffixes."""
    return Path(track).with_suffix(".wav").name


def final_output_path(output_dir: str | Path, track: str | Path) -> Path:
    return Path(output_dir) / final_output_name(track)


def final_output_candidates(output_dir: str | Path, track: str | Path) -> Iterator[Path]:
    output = Path(output_dir)
    name = final_output_name(track)
    for directory in FINAL_OUTPUT_DIRS:
        yield output / directory / name if directory else output / name


def find_final_output(output_dir: str | Path, track: str | Path) -> Path | None:
    for candidate in final_output_candidates(output_dir, track):
        if candidate.exists():
            return candidate
    return None
