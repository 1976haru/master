from __future__ import annotations

import csv
import tempfile
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_7_2.pyw"


def load_app():
    loader = SourceFileLoader("haru_v372_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.7.2 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def _write_test_wav(path: Path, *, amplitude: float) -> None:
    sample_rate = 48000
    seconds = 8
    t = np.arange(sample_rate * seconds, dtype=np.float64) / sample_rate
    mono = amplitude * np.sin(2.0 * np.pi * 440.0 * t)
    stereo = np.column_stack((mono, mono))
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, stereo, sample_rate, subtype="PCM_24")


def main() -> int:
    app = load_app()
    assert "v3.7.2" in app.APP_NAME
    assert app.REPORT_VERSION == "v3.7.2"
    assert app.SYNC_VERSION == "v3.7.2"

    # The proven parent synchronizer and the v3.7.1 pass must both point at
    # the hardened v3.7.2 implementation.
    assert app.v371.v37.v361._refresh_final_metrics_csv is app._refresh_final_metrics_csv_v372
    assert app.v371._refresh_final_metrics_csv is app._refresh_final_metrics_csv_v372
    assert app.v371.v37.v361._refresh_completion_text_files is app._refresh_completion_text_files_v372
    assert app.v371._refresh_completion_text_files is app._refresh_completion_text_files_v372

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        release_track = "01. Release Test.wav"
        review_track = "02. Review Test.wav"
        _write_test_wav(out / "01_RELEASE_READY" / "01. Release Test_MASTER.wav", amplitude=0.15)
        _write_test_wav(out / "02_NEEDS_REVIEW" / "02. Review Test_MASTER.wav", amplitude=0.10)

        csv_path = out / "mastering_report.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "track",
                    "status",
                    "target_LUFS",
                    "final_LUFS",
                    "final_dBTP",
                    "final_metrics_source",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "track": release_track,
                    "status": "PASS",
                    "target_LUFS": "-14.0",
                    "final_LUFS": "stale",
                    "final_dBTP": "stale",
                    "final_metrics_source": "stale",
                }
            )
            writer.writerow(
                {
                    "track": review_track,
                    "status": "FAIL",
                    "target_LUFS": "-14.0",
                    "final_LUFS": "stale",
                    "final_dBTP": "stale",
                    "final_metrics_source": "stale",
                }
            )

        refreshed = app._refresh_final_metrics_csv_v372(out)
        assert refreshed == 2

        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fields = set(reader.fieldnames or [])

        required = {
            "final_LRA",
            "final_lufs_delta_lu",
            "final_lufs_within_tolerance",
            "codec_strategy",
            "final_metrics_sync_version",
        }
        assert required.issubset(fields)
        assert len(rows) == 2
        for row in rows:
            assert row["final_LUFS"] not in {"", "stale"}
            assert row["final_dBTP"] not in {"", "stale"}
            assert row["final_LRA"] not in {"", "stale"}
            assert row["final_lufs_within_tolerance"] in {"true", "false"}
            assert row["codec_strategy"] == "ceiling_rerender_preserve_loudness"
            assert row["final_metrics_sync_version"] == "v3.7.2"
            assert row["final_metrics_source"] == "final_master_after_all_postprocessing"

        copied = out / "03_REPORT" / "mastering_report.csv"
        assert copied.exists()
        with copied.open("r", newline="", encoding="utf-8-sig") as handle:
            copied_fields = set(csv.DictReader(handle).fieldnames or [])
        assert required.issubset(copied_fields)

        txt = out / "자동해결_결과.txt"
        txt.write_text(
            "모든 곡이 v3.7.1 자동검사와 자동수정을 통과했습니다. 수동 Studio 보완은 필요하지 않습니다.",
            encoding="utf-8",
        )
        changed = app._refresh_completion_text_files_v372(out)
        assert changed == 1
        assert "v3.7.2" in txt.read_text(encoding="utf-8")

    print("[PASS] HARU Mastering v3.7.2 guaranteed CSV sync is ready")
    print("Parent synchronizer patch: ON")
    print("RELEASE_READY path lookup: ON")
    print("NEEDS_REVIEW path lookup: ON")
    print("final_LRA and loudness columns: ON")
    print("03_REPORT CSV copy sync: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
