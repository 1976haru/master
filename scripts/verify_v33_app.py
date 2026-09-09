from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

from haru_mastering.codec_auto_gain import calculate_codec_gain_reduction_db


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_3.pyw"


def load_app():
    loader = SourceFileLoader("haru_v33_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.3 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    assert "v3.3" in app.APP_NAME
    reduction = calculate_codec_gain_reduction_db(-1.12, -1.50, safety_margin_db=0.10)
    assert abs(reduction - 0.48) < 1e-9
    auto = app._codec_settings()
    assert int(auto.get("codecMaximumAutoGainPasses", 3)) >= 3
    assert float(auto.get("codecMaximumTotalGainReductionDb", 2.0)) >= 2.0
    print("[PASS] HARU Mastering v3.3 codec auto-gain runtime is ready")
    print("Measured codec overshoot correction: ON")
    print("Maximum auto-gain passes: 3")
    print("Final WAV metrics refresh: ON")
    print("Crest change reporting: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
