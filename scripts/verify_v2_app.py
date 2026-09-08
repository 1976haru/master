from __future__ import annotations

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Suno15_Mastering_v2.pyw"

loader = SourceFileLoader("verify_suno15_v2", str(APP))
spec = spec_from_loader(loader.name, loader)
if spec is None:
    raise SystemExit("[FAIL] v2 app loader spec creation failed")
module = module_from_spec(spec)
loader.exec_module(module)
module.patch_runtime()

required = ["OLD POP", "CHANSON", "CHILI EN", "CHILI JP", "SHOWA JP"]
missing = [name for name in required if name not in module.legacy.GENRES]
if missing:
    raise SystemExit(f"[FAIL] missing v2 genres: {missing}")

checks = {
    "OLD POP": (-14.0, -1.5),
    "CHANSON": (-14.0, -1.5),
    "CHILI EN": (-14.0, -1.2),
    "CHILI JP": (-14.0, -1.2),
    "SHOWA JP": (-14.3, -1.5),
}

for name, (target_i, target_tp) in checks.items():
    genre = module.legacy.GENRES[name]
    if abs(float(genre["target_i"]) - target_i) > 1e-9:
        raise SystemExit(f"[FAIL] {name} LUFS target mismatch: {genre['target_i']}")
    if abs(float(genre["target_tp"]) - target_tp) > 1e-9:
        raise SystemExit(f"[FAIL] {name} TP target mismatch: {genre['target_tp']}")
    limiter = module.limiter_filter(name)
    if "latency=true" not in limiter:
        raise SystemExit(f"[FAIL] {name} limiter latency compensation missing")

print("[PASS] HARU Mastering v2 app adapter is ready")
for name in required:
    genre = module.legacy.GENRES[name]
    print(
        f"{name}: {genre['target_i']:.1f} LUFS / "
        f"{genre['target_tp']:.1f} dBTP / LRA target {genre['target_lra']}"
    )
print("Limiter: FFmpeg alimiter latency compensation = ON")
