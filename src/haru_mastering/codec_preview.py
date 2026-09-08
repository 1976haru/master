from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .analysis import AudioMetrics, analyze_file


@dataclass(frozen=True)
class CodecPreviewResult:
    codec: str
    encoded_path: str
    metrics: AudioMetrics

    def to_dict(self) -> dict:
        return {
            "codec": self.codec,
            "encoded_path": self.encoded_path,
            "metrics": self.metrics.to_dict(),
        }


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


def _ffmpeg_executable(ffmpeg: str | None = None) -> str:
    if ffmpeg:
        return ffmpeg
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("FFmpeg is required for codec preview") from exc


def create_codec_previews(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str | None = None,
) -> tuple[CodecPreviewResult, ...]:
    source = Path(source_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    exe = _ffmpeg_executable(ffmpeg)

    targets = (
        ("AAC-256", output / f"{source.stem}_AAC256.m4a", ["-c:a", "aac", "-b:a", "256k"]),
        ("MP3-320", output / f"{source.stem}_MP3_320.mp3", ["-c:a", "libmp3lame", "-b:a", "320k"]),
    )
    results: list[CodecPreviewResult] = []

    for label, encoded, codec_args in targets:
        encode = _run([exe, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), *codec_args, str(encoded)])
        if encode.returncode != 0:
            raise RuntimeError(f"{label} encode failed: {(encode.stderr or encode.stdout)[-2000:]}")

        with tempfile.TemporaryDirectory(prefix="haru_codec_") as tmp:
            decoded = Path(tmp) / "decoded.wav"
            decode = _run(
                [
                    exe,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(encoded),
                    "-ar",
                    "48000",
                    "-c:a",
                    "pcm_s24le",
                    str(decoded),
                ]
            )
            if decode.returncode != 0:
                raise RuntimeError(f"{label} decode failed: {(decode.stderr or decode.stdout)[-2000:]}")
            metrics = analyze_file(decoded)

        results.append(CodecPreviewResult(codec=label, encoded_path=str(encoded), metrics=metrics))

    report_path = output / f"{source.stem}_codec_preview.json"
    report_path.write_text(
        json.dumps([item.to_dict() for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return tuple(results)
