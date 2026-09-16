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


def test_dynamics_outer_retry_ladder_is_removed_from_v39_worker():
    text = (ROOT / "Suno15_Mastering_v3_9.pyw").read_text(encoding="utf-8")
    worker = text.split("    def _worker(", 1)[1].split("        if rows:", 1)[0]

    assert "for attempt in range" not in worker
    assert "factor * 0.65" not in worker
    assert "max_retries" not in worker
    assert "Transparent fallback: base dynamics risk" in worker
    assert "Transparent fallback: final dynamics risk" in worker


def test_v39_logs_resolved_settings_and_track_counters():
    text = (ROOT / "Suno15_Mastering_v3_9.pyw").read_text(encoding="utf-8")

    assert "[Settings]" in text
    assert "maximumAutoRerenders =" in text
    assert "dynamicsBaseRerenders =" in text
    assert "codecMaximumAutoRerenders =" in text
    assert "Fullness renders:" in text
    assert "Quality Gate calls:" in text
    assert "Codec checks:" in text
    assert "초과했습니다" in text
    assert "1/4" not in text


def test_worker_has_per_track_error_boundary_and_codec_gate_labels():
    text = (ROOT / "Suno15_Mastering_v3_9.pyw").read_text(encoding="utf-8")
    worker = text.split("    def _worker(", 1)[1].split("        if rows:", 1)[0]

    assert "except (SystemExit, KeyboardInterrupt):" in worker
    assert "except Exception as exc:" in worker
    assert "_record_track_error(idx, total, src, out_dir, exc)" in worker
    assert "Codec Final Gate" in text
    assert "Codec sound reapply" in text
