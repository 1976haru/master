from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "Suno15_Mastering_v3.pyw"


def main() -> int:
    loader = SourceFileLoader("haru_v3_verify_app", str(APP_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Unable to create v3 runtime module spec")
    module = module_from_spec(spec)
    loader.exec_module(module)

    if not hasattr(module, "AppV3"):
        raise RuntimeError("AppV3 class is missing")
    genres = module.legacy.GENRES
    required = {"OLD POP", "CHANSON", "CHILI EN", "CHILI JP", "SHOWA JP"}
    missing = sorted(required - set(genres))
    if missing:
        raise RuntimeError(f"Missing v3 genres: {missing}")

    print("[PASS] HARU Mastering v3 runtime adapter imports successfully")
    print(module.APP_NAME)
    for key in sorted(required):
        item = genres[key]
        print(f"{key}: {item['target_i']} LUFS / {item['target_tp']} dBTP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
