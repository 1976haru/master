from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_7.pyw"


def load_app():
    loader = SourceFileLoader("haru_v37_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.7 adapter")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    required = {
        "OLD POP",
        "SENIOR KR",
        "SENIOR JP",
        "SHOWA JP",
        "ENKA JP",
        "TROT KR",
        "J-BALLAD",
        "K-POP",
        "KIDS POP",
        "CITY POP JP",
        "ACOUSTIC",
        "ROCK",
        "LOFI",
        "INSTRUMENTAL",
        "GENERAL",
    }
    assert "v3.7" in app.APP_NAME
    assert required.issubset(app.legacy.GENRES)
    assert len(app.GENRE_DISPLAY_ORDER) >= 23
    assert app.GENRE_DISPLAY_ORDER[0] == "OLD POP"
    assert app.QUICK_GENRES == (
        "OLD POP",
        "SENIOR JP",
        "SHOWA JP",
        "K-POP",
        "KIDS POP",
        "BALLAD",
    )

    expected = {
        "SENIOR JP": (-14.3, -1.5, 11.0),
        "K-POP": (-14.0, -1.2, 9.0),
        "KIDS POP": (-14.0, -1.3, 8.0),
        "GENERAL": (-14.0, -1.5, 10.0),
    }
    for key, (target_i, target_tp, target_lra) in expected.items():
        genre = app.legacy.GENRES[key]
        profile = app.v2.get_profile(key)
        assert genre["target_i"] == target_i
        assert genre["target_tp"] == target_tp
        assert genre["target_lra"] == target_lra
        assert profile["targetLufsI"] == target_i
        assert profile["truePeakCeilingDbtp"] == target_tp
        assert app.v2.V2_LRA_TARGETS[key] == target_lra
        assert app.v2.V2_EQ[key]
        assert app.v2.V2_COMP[key]

    # Ensure the full validated mastering/report chain remains inherited.
    assert issubclass(app.AppV37, app.v361.AppV361)
    assert hasattr(app.AppV37, "_build_master_tab")
    assert hasattr(app.AppV37, "_update_genre_description")

    print("[PASS] HARU Mastering v3.7 multi-genre edition is ready")
    print(f"Available genres: {len(app.GENRE_DISPLAY_ORDER)}")
    print("Old Pop quick preset: ON")
    print("Japanese senior presets: ON")
    print("K-POP and Kids Pop presets: ON")
    print("General fallback preset: ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
