from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fullness_guard_does_not_run_codec_preview_per_candidate():
    text = (ROOT / "Suno15_Mastering_v3_9.pyw").read_text(encoding="utf-8")
    finish_candidate = text.split("    def _finish_candidate(", 1)[1].split(
        "    def _render_base(",
        1,
    )[0]

    assert "check_codec_safety" not in finish_candidate
    assert "v32.check_codec_safety" in text


def test_quality_modes_document_fullness_pass_limits_in_ui():
    text = (ROOT / "Suno15_Mastering_v3_9.pyw").read_text(encoding="utf-8")

    assert "Fullness 최대 1 pass" in text
    assert "Fullness 최대 2 passes" in text


def test_v39_is_latest_launcher_target():
    run = (ROOT / "RUN.bat").read_text(encoding="utf-8", errors="ignore")
    legacy = (ROOT / "Suno15_Mastering.pyw").read_text(encoding="utf-8", errors="ignore")

    assert run.find("Suno15_Mastering_v3_9.pyw") < run.find("Suno15_Mastering_v3_8_1.pyw")
    assert legacy.find("Suno15_Mastering_v3_9.pyw") < legacy.find("Suno15_Mastering_v3_8_1.pyw")

