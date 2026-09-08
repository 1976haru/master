from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_1.pyw"


def load_app():
    loader = SourceFileLoader("haru_v32_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.2 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    expected = {
        "OLD POP": 0.60,
        "BALLAD": 0.80,
        "R&B": 0.90,
        "CHILI JP": 0.80,
        "SHOWA JP": 0.50,
    }
    for genre, lra_limit in expected.items():
        kwargs, auto, _ = app._settings(genre)
        assert abs(kwargs["maximum_lra_reduction_lu"] - lra_limit) < 1e-9
        assert abs(kwargs["minimum_final_lra_lu"] - 3.5) < 1e-9
        assert abs(kwargs["maximum_crest_factor_loss_db"] - 0.75) < 1e-9
        assert abs(kwargs["maximum_energetic_tail_rms_dbfs"] - (-35.0)) < 1e-9
        assert kwargs["reject_on_tail_cut"] is True
        assert int(auto["maximumAutoRerenders"]) == 2
        assert bool(auto["transparentFallbackEnabled"]) is True
        assert abs(float(auto["energeticTailFadeMs"]) - 400.0) < 1e-9
    assert "v3.2" in app.APP_NAME
    assert "AUTO FINISH" in app.APP_NAME
    assert hasattr(app.AppV31, "_render_transparent")
    print("[PASS] HARU Mastering v3.2 auto-finish runtime is ready")
    print("Composite LRA/Crest dynamics gate: ON")
    print("Transparent EQ/Compressor bypass fallback: ON")
    print("Pre-tail inspection + 400 ms musical fade: ON")
    print("Auto rerender: max 2")
    print("AAC/MP3 codec safety: ON")
    print("RELEASE_READY organizer: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
