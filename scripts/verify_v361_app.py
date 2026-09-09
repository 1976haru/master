from __future__ import annotations

import csv
import json
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_file
from haru_mastering.quality_gate import classify_tail_silence_difference


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_6_1.pyw"


def load_app():
    loader = SourceFileLoader("haru_v361_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.6.1 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    assert "v3.6.1" in app.APP_NAME
    assert "v3.6.1 자동검사" in app._upgrade_completion_text(
        "모든 곡이 v3.6 자동검사와 자동수정을 통과했습니다."
    )

    classification, note = classify_tail_silence_difference(
        source_trailing_silence_ms=904.35,
        processed_trailing_silence_ms=875.85,
        duration_delta_ms=0.0,
        tail_hard_cut=False,
        tail_energetic_end=False,
        tail_last_sample_dbfs=float("-inf"),
    )
    assert classification == "INFO"
    assert "28.5 ms" in note

    with TemporaryDirectory() as temp_dir:
        output = Path(temp_dir)
        sr = 48000
        rng = np.random.default_rng(361)
        audio = rng.normal(0.0, 0.01, size=(sr * 2, 2))
        fade_frames = int(0.20 * sr)
        audio[-fade_frames:] *= np.linspace(1.0, 0.0, fade_frames)[:, None]
        audio[-1] = 0.0

        master = output / "01. Sync Test_MASTER.wav"
        sf.write(master, audio, sr, subtype="PCM_24")
        expected = analyze_file(master)

        csv_path = output / "mastering_report.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "track",
                    "status",
                    "final_LUFS",
                    "final_dBTP",
                    "final_LRA",
                    "tail_after_RMS",
                    "tail_after_rms_dbfs",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "track": "01. Sync Test.wav",
                    "status": "PASS",
                    "final_LUFS": "-10.00",
                    "final_dBTP": "-0.10",
                    "final_LRA": "0.10",
                    "tail_after_RMS": "-10.00",
                    "tail_after_rms_dbfs": "-10.00",
                }
            )

        (output / "HARU_QUALITY_GATE.json").write_text(
            json.dumps(
                [
                    {
                        "track": "01. Sync Test.wav",
                        "tail_note": "minor trailing-silence difference 28.5 ms; final tail is silent and safe",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        text_path = output / "자동해결_결과.txt"
        text_path.write_text(
            "모든 곡이 v3.6 자동검사와 자동수정을 통과했습니다.",
            encoding="utf-8",
        )

        assert app.v36._refresh_final_tail_csv(output) == 1
        assert app._refresh_final_metrics_csv(output) == 1
        assert app._refresh_completion_text_files(output) == 1

        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            row = next(csv.DictReader(handle))
        assert abs(float(row["final_LUFS"]) - expected.lufs_i) < 0.02
        assert abs(float(row["final_dBTP"]) - expected.true_peak_dbtp) < 0.02
        assert abs(float(row["final_LRA"]) - expected.lra_lu) < 0.02
        assert row["final_metrics_source"] == "final_master_after_all_postprocessing"
        assert row["tail_metrics_source"] == "final_master_after_codec"
        assert "28.5 ms" in row["tail_info_note"]
        assert "v3.6.1 자동검사" in text_path.read_text(encoding="utf-8")

    print("[PASS] HARU Mastering v3.6.1 final metrics synchronization is ready")
    print("Final WAV LUFS / dBTP / LRA CSV sync: ON")
    print("20-50 ms safe Tail difference: INFO")
    print("Hard cut / energetic / >50 ms Tail difference: WARN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
