from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_run_bat_prefers_v39_before_v381():
    text = (ROOT / "RUN.bat").read_text(encoding="utf-8", errors="ignore")
    assert text.find("Suno15_Mastering_v3_9.pyw") < text.find("Suno15_Mastering_v3_8_1.pyw")


def test_run_bat_keeps_v381_before_v38():
    text = (ROOT / "RUN.bat").read_text(encoding="utf-8", errors="ignore")
    assert text.find("Suno15_Mastering_v3_8_1.pyw") < text.find("Suno15_Mastering_v3_8.pyw")


def test_legacy_direct_execution_is_guarded():
    text = (ROOT / "Suno15_Mastering.pyw").read_text(encoding="utf-8", errors="ignore")
    assert "_launch_latest_from_legacy" in text
    assert "Suno15_Mastering_v3_9.pyw" in text
    assert "Suno15_Mastering_v3_8_1.pyw" in text
    assert "App().mainloop()" not in text.split('if __name__ == "__main__":')[-1]


def test_archived_legacy_launchers_forward_to_root_run():
    for name in ("RUN.bat", "START_HERE.bat"):
        text = (ROOT / "archive" / "legacy_v1_2" / name).read_text(
            encoding="utf-8",
            errors="ignore",
        )
        assert "..\\..\\RUN.bat" in text
