from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v3_9.pyw"


def load_app():
    loader = SourceFileLoader("haru_v39_verify", str(APP))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load v3.9 adapter")
    module = module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def main() -> int:
    app = load_app()
    assert app.APP_NAME == "HARU / SUNO 15-SET MASTERING v3.9"
    assert app.SYNC_VERSION == "v3.9"
    assert issubclass(app.AppV39, app.v38.AppV38)
    assert app.MAX_FULLNESS_RENDER_PASSES == 2

    channel_labels = {profile.label for profile in app.CHANNEL_PROFILES.values()}
    genre_labels = {profile.label for profile in app.GENRE_PROFILES.values()}
    assert {"올드팝 라운지", "한국 시니어", "일본 시니어"}.issubset(channel_labels)
    assert "올드팝 라운지" not in genre_labels
    assert {"K-POP", "재즈", "발라드"}.issubset(genre_labels)

    key = app.composite_key("OLD_POP_LOUNGE", "BALLAD")
    assert key in app.legacy.GENRES
    assert key in app._COMPOSITE_RUNTIME_PROFILES
    assert app.legacy.GENRES[key]["label"] == "올드팝 라운지 + 발라드"

    source = APP.read_text(encoding="utf-8")
    finish_candidate = source.split("    def _finish_candidate(", 1)[1].split(
        "    def _render_base(",
        1,
    )[0]
    assert "check_codec_safety" not in finish_candidate
    assert "v32.check_codec_safety" in source
    worker = source.split("    def _worker(", 1)[1].split("        if rows:", 1)[0]
    assert "for attempt in range" not in worker
    assert "factor * 0.65" not in worker
    assert "max_retries" not in worker
    assert "dynamicsBaseRerenders =" in worker
    assert "Fullness renders:" in worker
    assert "Quality Gate calls:" in worker
    assert "Codec checks:" in worker
    assert "1/4" not in source

    print("[PASS] HARU Mastering v3.9 channel/genre fast fullness runtime is ready")
    print("CHANNEL_PROFILES and GENRE_PROFILES: separated")
    print("Fullness render cap: 2")
    print("Dynamics outer retry ladder: removed")
    print("Codec Preview placement: final candidate path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
