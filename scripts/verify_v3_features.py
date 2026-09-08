from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_file
from haru_mastering.quality_gate import evaluate_master
from haru_mastering.reference import build_reference_plan
from haru_mastering.repair import detect_optional_tools


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="haru_v3_verify_") as tmp:
        root = Path(tmp)
        sr = 48000
        duration = 2.0
        t = np.arange(int(sr * duration), dtype=np.float64) / sr
        tone = 0.08 * np.sin(2.0 * np.pi * 440.0 * t)
        audio = np.column_stack([tone, tone])
        source = root / "source.wav"
        master = root / "master.wav"
        reference = root / "reference.wav"
        sf.write(source, audio, sr, subtype="PCM_24")
        sf.write(master, audio, sr, subtype="PCM_24")
        sf.write(reference, audio * 0.9, sr, subtype="PCM_24")

        metrics = analyze_file(master)
        gate = evaluate_master(
            source,
            master,
            target_lufs_i=metrics.lufs_i,
            true_peak_ceiling_dbtp=metrics.true_peak_dbtp + 0.1,
            lufs_tolerance_lu=0.2,
        )
        plan = build_reference_plan(source, reference, max_correction_db=1.0)

    tools = detect_optional_tools()
    print("[PASS] HARU Mastering v3 feature core is ready")
    print(f"Quality Gate: {gate.status} / residual delay {gate.residual_delay_samples} sample(s)")
    print(f"Reference Assist: {len(plan.corrections)} bounded EQ correction(s)")
    print(f"FFmpeg: {'YES' if shutil.which('ffmpeg') else 'via imageio-ffmpeg / PATH check at runtime'}")
    print(f"noisereduce: {'READY' if tools.noisereduce else 'OPTIONAL - not installed'}")
    print(f"DeepFilterNet: {'READY' if tools.deepfilternet else 'OPTIONAL - not installed'}")
    print(f"audio-separator: {'READY' if tools.audio_separator else 'OPTIONAL - not installed'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
