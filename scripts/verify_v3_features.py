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
        rng = np.random.default_rng(20260908)
        audio = rng.normal(0.0, 0.025, size=(sr * 2, 2))
        reference_audio = audio.copy()
        reference_audio[:, 0] += 0.01 * np.sin(2 * np.pi * 3200 * np.arange(sr * 2) / sr)
        reference_audio[:, 1] += 0.01 * np.sin(2 * np.pi * 3200 * np.arange(sr * 2) / sr)

        source = root / "source.wav"
        master = root / "master.wav"
        reference = root / "reference.wav"
        sf.write(source, audio, sr, subtype="PCM_24")
        sf.write(master, audio, sr, subtype="PCM_24")
        sf.write(reference, reference_audio, sr, subtype="PCM_24")

        metrics = analyze_file(master)
        gate = evaluate_master(
            source,
            master,
            target_lufs_i=metrics.lufs_i,
            true_peak_ceiling_dbtp=metrics.true_peak_dbtp + 0.1,
            lufs_tolerance_lu=0.2,
        )
        plan = build_reference_plan(source, reference, max_correction_db=1.0)

    if gate.status != "PASS" or gate.residual_delay_samples != 0:
        raise RuntimeError(
            f"Quality Gate verification failed: {gate.status}, delay={gate.residual_delay_samples}"
        )

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
