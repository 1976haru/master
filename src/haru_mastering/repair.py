from __future__ import annotations

import importlib.util
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class ToolStatus:
    noisereduce: bool
    deepfilternet: bool
    audio_separator: bool


def detect_optional_tools() -> ToolStatus:
    return ToolStatus(
        noisereduce=importlib.util.find_spec("noisereduce") is not None,
        deepfilternet=(shutil.which("deepFilter") is not None or shutil.which("deep-filter") is not None),
        audio_separator=shutil.which("audio-separator") is not None,
    )


def reduce_noise_file(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    strength: float = 0.45,
) -> Path:
    """Conservative spectral-gate repair using the optional noisereduce package."""
    if not 0.0 <= strength <= 1.0:
        raise ValueError("strength must be between 0 and 1")
    try:
        import noisereduce as nr
    except ImportError as exc:
        raise RuntimeError("noisereduce is not installed; run INSTALL_AI_TOOLS.bat") from exc

    source = Path(source_path)
    destination = Path(destination_path)
    audio, sample_rate = sf.read(source, always_2d=True, dtype="float64")
    repaired = np.empty_like(audio)

    # Music is much less tolerant of aggressive spectral gating than speech.
    # Keep the default intentionally conservative and process each channel independently.
    for channel in range(audio.shape[1]):
        repaired[:, channel] = nr.reduce_noise(
            y=audio[:, channel],
            sr=sample_rate,
            stationary=False,
            prop_decrease=float(strength),
        )

    peak = float(np.max(np.abs(repaired)))
    if peak > 0.999:
        repaired *= 0.999 / peak
    destination.parent.mkdir(parents=True, exist_ok=True)
    sf.write(destination, repaired, sample_rate, subtype="PCM_24")
    return destination


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
        creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0),
    )


def run_deepfilternet(
    source_path: str | Path,
    output_dir: str | Path,
) -> list[Path]:
    """Run DeepFilterNet with its built-in latency compensation enabled."""
    source = Path(source_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    executable = shutil.which("deepFilter")
    if executable:
        command = [
            executable,
            str(source),
            "--output-dir",
            str(output),
            "--compensate-delay",
        ]
    else:
        executable = shutil.which("deep-filter")
        if not executable:
            raise RuntimeError("DeepFilterNet is not installed; run INSTALL_AI_TOOLS.bat")
        command = [
            executable,
            "--compensate-delay",
            "--out-dir",
            str(output),
            str(source),
        ]

    before = {path.resolve() for path in output.glob("*.wav")}
    result = _run(command)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-4000:]
        raise RuntimeError(f"DeepFilterNet failed:\n{detail}")
    after = {path.resolve() for path in output.glob("*.wav")}
    created = sorted(Path(path) for path in after - before)
    return created


def run_audio_separator(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    model_filename: str = "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
) -> list[Path]:
    """Separate vocals/instrumental with python-audio-separator when installed."""
    executable = shutil.which("audio-separator")
    if not executable:
        raise RuntimeError("audio-separator is not installed; run INSTALL_AI_TOOLS.bat")

    source = Path(source_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    before = {path.resolve() for path in output.iterdir() if path.is_file()}
    command = [
        executable,
        str(source),
        "--output_dir",
        str(output),
        "--output_format",
        "WAV",
        "--model_filename",
        model_filename,
    ]
    result = _run(command)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-4000:]
        raise RuntimeError(f"audio-separator failed:\n{detail}")
    after = {path.resolve() for path in output.iterdir() if path.is_file()}
    return sorted(Path(path) for path in after - before)
