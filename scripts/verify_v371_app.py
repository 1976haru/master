from __future__ import annotations

import csv
import math
import tempfile
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_7_1.pyw"


def load_app():
    loader = SourceFileLoader("haru_v371_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.7.1 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def _write_test_wav(path: Path) -> None:
    sr = 48000
    seconds = 4.0
    t = np.arange(int(sr * seconds), dtype=np.float64) / sr
    # Slight amplitude movement gives pyloudnorm a stable, finite LRA measurement.
    envelope = 0.18 + 0.03 * np.sin(2.0 * np.pi * 0.4 * t)
    mono = envelope * np.sin(2.0 * np.pi * 220.0 * t)
    stereo = np.column_stack((mono, mono * 0.98))
    sf.write(path, stereo, sr, subtype="PCM_24")


def main() -> int:
    app = load_app()
    assert "v3.7.1" in app.APP_NAME
    assert app.report_module.QUALITY_REPORT_VERSION == "v3.7.1"

    payload = app._runtime_profile_payload()
    auto = payload["global"]["autoFinish"]
    assert int(auto["maximumAutoRerenders"]) >= 4
    assert math.isclose(float(auto["codecCeilingStepDb"]), 0.50, abs_tol=1e-12)

    # Critical regression guard: Stage 3 must use the read-only codec checker,
    # not the v3.3 checker that attenuates the mastered WAV before rerendering.
    assert app.v37.v32.check_codec_safety is app._RAW_CODEC_CHECK
    assert app._RAW_CODEC_CHECK is app.v37.v361.v36.v35.v34.v33._BASE_CODEC_CHECK

    assert (
        app._upgrade_completion_text(
            "모든 곡이 v3.6.1 자동검사와 자동수정을 통과했습니다. 수동 Studio 보완은 필요하지 않습니다."
        )
        == "모든 곡이 v3.7.1 자동검사와 자동수정을 통과했습니다. 수동 Studio 보완은 필요하지 않습니다."
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir)
        track = "01. verify.wav"
        master = output / "01. verify_MASTER.wav"
        _write_test_wav(master)
        metrics = app.analyze_file(master)

        csv_path = output / "mastering_report.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["track", "status", "target_LUFS", "final_LUFS", "final_dBTP"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "track": track,
                    "status": "PASS",
                    "target_LUFS": f"{metrics.lufs_i:.6f}",
                    "final_LUFS": "-99",
                    "final_dBTP": "-99",
                }
            )

        assert app._refresh_final_metrics_csv(output) == 1
        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            row = next(csv.DictReader(handle))

        assert "final_LRA" in row
        assert "final_lufs_delta_lu" in row
        assert "final_lufs_within_tolerance" in row
        assert "codec_strategy" in row
        assert math.isclose(float(row["final_LUFS"]), metrics.lufs_i, abs_tol=0.011)
        assert math.isclose(float(row["final_dBTP"]), metrics.true_peak_dbtp, abs_tol=0.011)
        assert math.isclose(float(row["final_LRA"]), metrics.lra_lu, abs_tol=0.011)
        assert row["final_lufs_within_tolerance"] == "true"
        assert row["codec_strategy"] == "ceiling_rerender_preserve_loudness"
        assert (output / "03_REPORT" / "mastering_report.csv").exists()

    print("[PASS] HARU Mastering v3.7.1 loudness-safe codec strategy is ready")
    print("Codec broadband attenuation before rerender: OFF")
    print("Codec ceiling rerender: 0.50 dB x up to 4")
    print("Final LUFS / dBTP / LRA CSV sync: ON")
    print("Completion/report version: v3.7.1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
