from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    config = root / "config" / "channel_profiles.v2.json"

    try:
        from haru_mastering.profiles import load_profiles, resolve_profile
        from haru_mastering.analysis import analyze_array
        import numpy as np
    except Exception as exc:
        print("[FAIL] HARU Mastering v2 import failed:")
        print(exc)
        print("\nRun INSTALL.bat again from the repository root.")
        return 1

    try:
        payload = load_profiles(config)
        names = sorted(payload["profiles"].keys())
        for name in names:
            profile = resolve_profile(payload, name)
            assert profile["workingSampleRateHz"] == 48000

        sr = 48000
        t = np.arange(sr, dtype=np.float64) / sr
        x = 0.05 * np.sin(2 * np.pi * 440.0 * t)
        stereo = np.column_stack([x, x])
        metrics = analyze_array(stereo, sr)
    except Exception as exc:
        print("[FAIL] v2 self-check failed:")
        print(exc)
        return 2

    print("[PASS] HARU Mastering v2 core is ready")
    print("Profiles:", ", ".join(names))
    print(f"Analyzer: {metrics.sample_rate_hz} Hz / {metrics.channels} ch")
    print(f"Sample Peak: {metrics.sample_peak_dbfs:.2f} dBFS")
    print(f"True Peak: {metrics.true_peak_dbtp:.2f} dBTP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
