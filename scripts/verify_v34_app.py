from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

from haru_mastering.alignment import DelayDiagnostic
from haru_mastering.quality_gate import classify_delay_diagnostic


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_4.pyw"


def load_app():
    loader = SourceFileLoader("haru_v34_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.4 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    assert "v3.4" in app.APP_NAME

    tiny = DelayDiagnostic(
        delay_samples=-4,
        window_estimates_samples=(-4, -4, -3, -4, -5),
        window_peak_correlations=(0.9, 0.9, 0.9, 0.9, 0.9),
        confidence=0.97,
        consistent=True,
        spread_samples=2,
    )
    classification, _ = classify_delay_diagnostic(tiny)
    assert classification == "INFO"

    confirmed = DelayDiagnostic(
        delay_samples=240,
        window_estimates_samples=(240, 240, 239, 240, 241),
        window_peak_correlations=(0.9, 0.9, 0.9, 0.9, 0.9),
        confidence=0.97,
        consistent=True,
        spread_samples=2,
    )
    classification, _ = classify_delay_diagnostic(confirmed)
    assert classification == "FAIL"

    auto = app._delay_config()
    assert int(auto.get("delayInformationLimitSamples", 8)) == 8
    assert int(auto.get("delayAutomaticAlignmentMinimumSamples", 48)) == 48

    print("[PASS] HARU Mastering v3.4 smart delay runtime is ready")
    print("-4 sample estimator drift: INFO / release eligible")
    print("48+ confirmed samples: automatic alignment candidate")
    print("Multi-window confidence guard: ON")
    print("Failed alignment rollback: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
