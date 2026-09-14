# -*- coding: utf-8 -*-
"""HARU Mastering v3.8.1 - final filename cleanup patch."""
from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V38_PATH = ROOT / "Suno15_Mastering_v3_8.pyw"


def _load_v38():
    loader = SourceFileLoader("suno15_v38", str(V38_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.8 program cannot be loaded: {V38_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v38 = _load_v38()

from haru_mastering.version import APP_TITLE, REPORT_VERSION, VERSION


APP_NAME = APP_TITLE
SYNC_VERSION = REPORT_VERSION


class AppV381(v38.AppV38):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set(
            f"HARU Mastering v{VERSION} 준비 - 최종 WAV 파일명에서 _MASTER suffix를 제거합니다."
        )


if __name__ == "__main__":
    AppV381().mainloop()
