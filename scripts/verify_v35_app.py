from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_5.pyw"


def load_app():
    loader = SourceFileLoader("haru_v35_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.5 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    assert "v3.5" in app.APP_NAME
    assert app._tail_candidate_values({}) == (400.0, 600.0, 800.0, 1200.0)

    with TemporaryDirectory() as temp_dir:
        sr = 48000
        t = np.arange(sr * 3, dtype=np.float64) / sr
        tone = 0.20 * np.sin(2.0 * np.pi * 220.0 * t)
        path = Path(temp_dir) / "adaptive_tail.wav"
        sf.write(path, np.column_stack([tone, tone]), sr, subtype="PCM_24")

        result = app.repair_tail_automatically(
            path,
            energetic_end_threshold_dbfs=-35.0,
            energetic_fade_candidates_ms=(400.0, 600.0, 800.0, 1200.0),
            energetic_target_margin_db=0.5,
            maximum_energetic_fade_ms=1200.0,
        )
        assert result.mode == "musical_tail_fade"
        assert result.fade_ms == 600.0
        assert result.attempted_fades_ms == (400.0, 600.0)
        assert result.after.end_rms_dbfs <= -35.5
        assert result.after.energetic_end is False

    print("[PASS] HARU Mastering v3.5 adaptive tail runtime is ready")
    print("Energetic fade ladder: 400 -> 600 -> 800 -> 1200 ms")
    print("Shortest passing fade selection: ON")
    print("Single-write non-stacking fade: ON")
    print("Tail safety margin: 0.5 dB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
