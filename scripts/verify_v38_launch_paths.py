from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    run = _read(ROOT / "RUN.bat")
    start = _read(ROOT / "START_HERE.bat")
    legacy = _read(ROOT / "Suno15_Mastering.pyw")
    archived_run = _read(ROOT / "archive" / "legacy_v1_2" / "RUN.bat")
    archived_start = _read(ROOT / "archive" / "legacy_v1_2" / "START_HERE.bat")

    assert run.find("Suno15_Mastering_v3_10.pyw") < run.find("Suno15_Mastering_v3_9.pyw")
    assert run.find("Suno15_Mastering_v3_9.pyw") < run.find("Suno15_Mastering_v3_8_1.pyw")
    assert run.find("Suno15_Mastering_v3_8_1.pyw") < run.find("Suno15_Mastering_v3_8.pyw")
    assert "call \"%~dp0RUN.bat\"" in start
    assert "_launch_latest_from_legacy" in legacy
    assert "Suno15_Mastering_v3_9.pyw" in legacy
    assert "Suno15_Mastering_v3_8_1.pyw" in legacy
    assert "App().mainloop()" not in legacy.split('if __name__ == "__main__":')[-1]
    assert "..\\..\\RUN.bat" in archived_run
    assert "..\\..\\RUN.bat" in archived_start

    print("[PASS] v3.10 launch paths point away from legacy UI")
    print("Root RUN: v3.10 first, v3.9 fallback")
    print("START_HERE: root RUN")
    print("Archived legacy RUN/START_HERE: root RUN")
    print("Suno15_Mastering.pyw direct execution guard: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
