"""HARU Mastering v3.11 - Suno v6 Noise Repair."""
from __future__ import annotations

import sys
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_v310():
    source = ROOT / "Suno15_Mastering_v3_10.pyw"
    loader = SourceFileLoader("haru_v311_v310", str(source))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {source}")
    module = module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


v310 = _load_v310()


class AppV311(v310.AppV310):
    def __init__(self):
        super().__init__()
        self.title("HARU Mastering v3.11 - Suno v6 Noise Repair")


if __name__ == "__main__":
    AppV311().mainloop()
