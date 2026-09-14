from __future__ import annotations

import csv
import tempfile
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_8.pyw"


def load_app():
    loader = SourceFileLoader("haru_v38_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.8 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    assert app.APP_NAME == "HARU / SUNO 15-SET MASTERING v3.8.1"
    assert app.REPORT_VERSION == "v3.8.1"
    assert app.SYNC_VERSION == "v3.8.1"
    assert issubclass(app.AppV38, app.v372.AppV372)
    assert app.report_module.QUALITY_REPORT_VERSION == "v3.8.1"

    with tempfile.TemporaryDirectory() as temp_dir:
        out = Path(temp_dir)
        csv_path = out / "mastering_report.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "track",
                    "status",
                    "target_LUFS",
                    "final_metrics_sync_version",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "track": "01.wav",
                    "status": "PASS",
                    "target_LUFS": "-14.0",
                    "final_metrics_sync_version": "v3.7.2",
                }
            )

        rows = {
            "01.wav": app.FullnessCsvRow(
                mode="RICH",
                strength_percent=75,
                warmth_gain_db=0.45,
                body_gain_db=0.25,
                saturation_wet_percent=4.0,
                density_wet_percent=4.0,
                auto_reduced=True,
                retry_count=1,
            )
        }
        assert app.patch_csv_with_fullness(out, rows) == 1
        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            row = next(csv.DictReader(handle))
        assert row["app_version"] == "v3.8.1"
        assert row["final_metrics_sync_version"] == "v3.8.1"
        assert row["fullness_mode"] == "RICH"
        assert row["fullness_strength_percent"] == "75"
        assert row["warmth_gain_db"] == "+0.45"
        assert row["body_gain_db"] == "+0.25"
        assert row["saturation_wet_percent"] == "4.0"
        assert row["density_wet_percent"] == "4.0"
        assert row["fullness_auto_reduced"] == "true"
        assert row["fullness_retry_count"] == "1"
        assert (out / "03_REPORT" / "mastering_report.csv").exists()

        txt = out / "auto_result.txt"
        txt.write_text("All tracks passed v3.7.2 final checks.", encoding="utf-8")
        assert app._refresh_completion_text_files_v38(out) == 1
        assert "v3.8.1" in txt.read_text(encoding="utf-8")

    print("[PASS] HARU Mastering v3.8 Fullness Engine is ready")
    print("v3.7.2 inheritance: ON")
    print("Fullness CSV columns: ON")
    print("Central version strings: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
