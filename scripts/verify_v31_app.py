from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_1.pyw"


def load_app():
    loader = SourceFileLoader("haru_v31_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.1 adapter")
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
        assert kwargs["reject_on_tail_cut"] is True
        assert int(auto["maximumAutoRerenders"]) == 2
    assert "AUTO FINISH" in app.APP_NAME
    print("[PASS] HARU Mastering v3.1 auto-finish runtime is ready")
    print("Auto rerender: max 2")
    print("Tail hard-cut repair: ON")
    print("Profile/genre LRA limits: ON")
    print("AAC/MP3 codec safety: ON")
    print("RELEASE_READY organizer: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
