from __future__ import annotations

import csv
import tempfile
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_8_1.pyw"


def load_app():
    loader = SourceFileLoader("haru_v381_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.8.1 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def _write_test_wav(path: Path, *, amplitude: float = 0.12) -> None:
    sample_rate = 48000
    t = np.arange(sample_rate * 4, dtype=np.float64) / sample_rate
    mono = amplitude * np.sin(2.0 * np.pi * 440.0 * t)
    audio = np.column_stack((mono, mono))
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sample_rate, subtype="PCM_24")


def main() -> int:
    app = load_app()
    assert app.APP_NAME == "HARU / SUNO 15-SET MASTERING v3.9"
    assert app.SYNC_VERSION == "v3.9"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        release_track = "01. Test Song.wav"
        review_track = "02. Problem Song.wav"
        _write_test_wav(out / "01_RELEASE_READY" / release_track, amplitude=0.12)
        _write_test_wav(out / "02_NEEDS_REVIEW" / review_track, amplitude=0.08)

        for bad in (
            "01. Test Song_MASTER.wav",
            "01. Test Song_master.wav",
            "01. Test Song_MATER.wav",
            "01. Test Song_MASTERED.wav",
        ):
            assert not (out / "01_RELEASE_READY" / bad).exists()

        csv_path = out / "mastering_report.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["track", "status", "target_LUFS", "final_LUFS", "final_dBTP"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "track": release_track,
                    "status": "PASS",
                    "target_LUFS": "-14.0",
                    "final_LUFS": "stale",
                    "final_dBTP": "stale",
                }
            )
            writer.writerow(
                {
                    "track": review_track,
                    "status": "FAIL",
                    "target_LUFS": "-14.0",
                    "final_LUFS": "stale",
                    "final_dBTP": "stale",
                }
            )

        refreshed = app.v38._refresh_final_metrics_csv_v38(out)
        assert refreshed == 2
        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))

        assert {row["track"] for row in rows} == {release_track, review_track}
        for row in rows:
            assert row["final_LUFS"] not in {"", "stale"}
            assert row["final_dBTP"] not in {"", "stale"}
            assert row["final_LRA"] not in {"", "stale"}
            assert row["app_version"] == "v3.9"
            assert row["final_metrics_sync_version"] == "v3.9"

    print("[PASS] HARU Mastering v3.8.1 filename cleanup adapter follows v3.9 versioning")
    print("Final WAV names: original stem + .wav")
    print("RELEASE_READY lookup: suffixless")
    print("NEEDS_REVIEW lookup: suffixless")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
