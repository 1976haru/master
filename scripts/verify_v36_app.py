from __future__ import annotations

import csv
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_6.pyw"


def load_app():
    loader = SourceFileLoader("haru_v36_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.6 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    assert "v3.6" in app.APP_NAME
    assert "v3.6 자동검사" in app._upgrade_completion_text(
        "모든 곡이 v3.2 자동검사와 자동수정을 통과했습니다."
    )

    with TemporaryDirectory() as temp_dir:
        output = Path(temp_dir)
        sr = 48000
        rng = np.random.default_rng(36)
        audio = rng.normal(0.0, 0.01, size=(sr, 2))
        fade_frames = int(0.20 * sr)
        audio[-fade_frames:] *= np.linspace(1.0, 0.0, fade_frames)[:, None]
        audio[-1] = 0.0

        master = output / "01. Sync Test_MASTER.wav"
        sf.write(master, audio, sr, subtype="PCM_24")

        csv_path = output / "mastering_report.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["track", "status", "tail_after_RMS", "tail_after_rms_dbfs"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "track": "01. Sync Test.wav",
                    "status": "PASS",
                    "tail_after_RMS": "-10.00",
                    "tail_after_rms_dbfs": "-10.00",
                }
            )

        text_path = output / "자동해결_결과.txt"
        text_path.write_text(
            "모든 곡이 v3.2 자동검사와 자동수정을 통과했습니다.",
            encoding="utf-8",
        )

        assert app._refresh_final_tail_csv(output) == 1
        assert app._refresh_completion_text_files(output) == 1

        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            row = next(csv.DictReader(handle))
        expected = app.inspect_tail(
            master,
            window_ms=100.0,
            end_rms_threshold_dbfs=-50.0,
            last_sample_threshold_dbfs=-60.0,
            energetic_end_threshold_dbfs=-35.0,
        )
        assert abs(float(row["tail_final_rms_dbfs"]) - expected.end_rms_dbfs) < 0.02
        assert row["tail_after_RMS"] == row["tail_final_rms_dbfs"]
        assert row["tail_metrics_source"] == "final_master_after_codec"
        assert "v3.6 자동검사" in text_path.read_text(encoding="utf-8")

    print("[PASS] HARU Mastering v3.6 final report synchronization is ready")
    print("Completion text version sync: ON")
    print("Final WAV Tail CSV sync: ON")
    print("Codec post-gain Tail remeasurement: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
