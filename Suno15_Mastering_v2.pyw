# -*- coding: utf-8 -*-
"""
HARU Mastering v2 runtime adapter.

기존 Suno15_Mastering.pyw UI와 Studio 안내 기능은 그대로 사용하고,
마스터링 목표값/프리체인/리미터만 v2 채널 프로필 기준으로 안전하게 교체한다.

되돌리려면 RUN_LEGACY.bat을 실행하면 된다.
"""
from __future__ import annotations

import json
import math
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEGACY_PATH = ROOT / "Suno15_Mastering.pyw"
PROFILE_PATH = ROOT / "config" / "channel_profiles.v2.json"


def load_legacy():
    loader = SourceFileLoader("suno15_legacy", str(LEGACY_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"기존 프로그램을 불러올 수 없습니다: {LEGACY_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


legacy = load_legacy()

try:
    from haru_mastering.profiles import load_profiles, resolve_profile
except Exception as exc:
    raise RuntimeError(
        "HARU Mastering v2 core를 불러오지 못했습니다. INSTALL.bat을 다시 실행하세요."
    ) from exc


PROFILE_MAP = {
    "OLD POP": "old_pop_lounge",
    "BALLAD": "old_pop_lounge",
    "JAZZ": "old_pop_lounge",
    "R&B": "old_pop_lounge",
    "SOUL": "old_pop_lounge",
    "CHANSON": "old_pop_lounge_french_chanson",
    "CHILI EN": "chili_lab",
    "CHILI JP": "chili_lab_ja",
    "SHOWA JP": "showa_seventies",
}

# legacy loudnorm의 LRA는 목표값이지 강제 LRA 감소량이 아니다.
# 기존 장르 정체성을 유지하면서 과도한 압축이 생기지 않도록 보수적으로 둔다.
V2_LRA_TARGETS = {
    "OLD POP": 11,
    "BALLAD": 10,
    "JAZZ": 13,
    "R&B": 10,
    "SOUL": 10,
    "CHANSON": 11,
    "CHILI EN": 9,
    "CHILI JP": 9,
    "SHOWA JP": 11,
}

# 고정 EQ를 완전히 제거하지는 않되 v1보다 변화량을 절반 수준으로 줄인다.
# 이후 단계에서 분석 기반 dynamic EQ로 대체할 예정.
V2_EQ = {
    "OLD POP": [
        "highpass=f=24",
        "equalizer=f=260:t=q:w=1.0:g=-0.3",
        "equalizer=f=3000:t=q:w=1.0:g=0.5",
        "equalizer=f=8500:t=q:w=1.0:g=-0.2",
    ],
    "BALLAD": [
        "highpass=f=25",
        "equalizer=f=250:t=q:w=1.0:g=-0.4",
        "equalizer=f=3000:t=q:w=1.0:g=0.5",
        "equalizer=f=8500:t=q:w=1.0:g=-0.3",
    ],
    "JAZZ": [
        "highpass=f=22",
        "equalizer=f=220:t=q:w=1.0:g=-0.2",
        "equalizer=f=4500:t=q:w=1.0:g=0.2",
    ],
    "CHANSON": [
        "highpass=f=24",
        "equalizer=f=240:t=q:w=1.0:g=-0.3",
        "equalizer=f=2600:t=q:w=1.0:g=0.6",
        "equalizer=f=8000:t=q:w=1.0:g=-0.4",
    ],
    "R&B": [
        "highpass=f=25",
        "equalizer=f=90:t=q:w=0.8:g=0.5",
        "equalizer=f=260:t=q:w=1.0:g=-0.5",
        "equalizer=f=3200:t=q:w=1.0:g=0.5",
    ],
    "SOUL": [
        "highpass=f=24",
        "equalizer=f=110:t=q:w=0.9:g=0.4",
        "equalizer=f=350:t=q:w=1.0:g=0.2",
        "equalizer=f=3000:t=q:w=1.0:g=0.5",
        "equalizer=f=8500:t=q:w=1.0:g=-0.2",
    ],
    "CHILI EN": [
        "highpass=f=25",
        "equalizer=f=85:t=q:w=0.8:g=0.6",
        "equalizer=f=250:t=q:w=1.0:g=-0.6",
        "equalizer=f=3000:t=q:w=1.0:g=0.6",
        "equalizer=f=9000:t=q:w=1.0:g=0.2",
    ],
    "CHILI JP": [
        "highpass=f=25",
        "equalizer=f=90:t=q:w=0.8:g=0.5",
        "equalizer=f=250:t=q:w=1.0:g=-0.5",
        "equalizer=f=2800:t=q:w=1.0:g=0.5",
        "equalizer=f=6200:t=q:w=1.0:g=-0.3",
    ],
    "SHOWA JP": [
        "highpass=f=22",
        "equalizer=f=260:t=q:w=1.0:g=-0.2",
        "equalizer=f=2600:t=q:w=1.0:g=0.3",
        "equalizer=f=7600:t=q:w=1.0:g=-0.3",
    ],
}

# threshold, ratio, attack(ms), release(ms), makeup
V2_COMP = {
    "OLD POP": [0.18, 1.30, 30, 280, 1.02],
    "BALLAD": [0.18, 1.35, 30, 280, 1.03],
    "JAZZ": [0.22, 1.18, 40, 320, 1.00],
    "CHANSON": [0.19, 1.30, 32, 300, 1.02],
    "R&B": [0.17, 1.45, 24, 230, 1.04],
    "SOUL": [0.17, 1.40, 26, 250, 1.04],
    "CHILI EN": [0.16, 1.50, 22, 220, 1.04],
    "CHILI JP": [0.17, 1.42, 24, 230, 1.03],
    "SHOWA JP": [0.21, 1.22, 35, 320, 1.01],
}

V2_CHARACTER = {
    "OLD POP": "따뜻하고 성숙하며 오래 들어도 피곤하지 않은 OLD POP LOUNGE 사운드",
    "SHOWA JP": "1970s 일본 New Music/포크의 성숙한 중저역, 부드러운 고역, 자연스러운 스테레오",
}


def get_profile(genre_key):
    payload = load_profiles(PROFILE_PATH)
    profile_name = PROFILE_MAP.get(genre_key, "old_pop_lounge")
    return resolve_profile(payload, profile_name)


def apply_v2_genres():
    # 새 채널 선택지 추가
    if "OLD POP" not in legacy.GENRES:
        legacy.GENRES["OLD POP"] = {
            "label": "OLD POP LOUNGE",
            "target_i": -14.0,
            "target_tp": -1.5,
            "target_lra": 11,
            "eq": V2_EQ["OLD POP"],
            "comp": V2_COMP["OLD POP"],
            "character": V2_CHARACTER["OLD POP"],
        }
    if "SHOWA JP" not in legacy.GENRES:
        legacy.GENRES["SHOWA JP"] = {
            "label": "昭和セブンティーズ",
            "target_i": -14.3,
            "target_tp": -1.5,
            "target_lra": 11,
            "eq": V2_EQ["SHOWA JP"],
            "comp": V2_COMP["SHOWA JP"],
            "character": V2_CHARACTER["SHOWA JP"],
        }

    for genre_key in list(legacy.GENRES):
        profile = get_profile(genre_key)
        g = legacy.GENRES[genre_key]
        g["target_i"] = float(profile["targetLufsI"])
        g["target_tp"] = float(profile["truePeakCeilingDbtp"])
        g["target_lra"] = V2_LRA_TARGETS.get(genre_key, g.get("target_lra", 11))
        g["eq"] = list(V2_EQ.get(genre_key, g.get("eq", [])))
        g["comp"] = list(V2_COMP.get(genre_key, g.get("comp", [0.2, 1.2, 30, 300, 1.0])))

    # 기존 장르 설명은 유지하되 v2 채널 정체성을 명확히 표시
    legacy.GENRES["CHANSON"]["character"] = (
        "프랑스어의 둥근 모음과 대화형 보컬, 어쿠스틱 악기 질감, 절제된 고역과 자연스러운 공간"
    )
    legacy.GENRES["CHILI EN"]["character"] = (
        "가까운 보컬, 타이트한 저역, 도시적 Chill Rap/Urban Soul, 선명한 훅과 과하지 않은 고역"
    )
    legacy.GENRES["CHILI JP"]["character"] = (
        "자연스러운 일본어 모라 리듬, 가까운 저중역 보컬, 타이트한 저역, 아이돌식 과광택 없는 고역"
    )


def build_pre_chain_v2(genre_key, factor=1.0):
    g = legacy.GENRES[genre_key]
    threshold, ratio, attack, release, makeup = g["comp"]

    # 이미 강하게 압축된 곡은 ratio를 1에 더 가깝게 줄인다.
    # 다이내믹이 큰 곡도 v1처럼 공격적으로 누르지 않는다.
    factor = min(max(float(factor), 0.65), 1.08)
    ratio = 1.0 + (ratio - 1.0) * factor

    filters = list(g["eq"])
    filters.append(
        f"acompressor=threshold={threshold}:ratio={ratio:.3f}:"
        f"attack={attack}:release={release}:makeup={makeup}"
    )
    return ",".join(filters)


def limiter_filter(genre_key):
    g = legacy.GENRES[genre_key]
    ceiling_linear = 10.0 ** (float(g["target_tp"]) / 20.0)
    # latency=true가 attack lookahead 지연을 보상한다.
    return (
        f"alimiter=limit={ceiling_linear:.6f}:attack=5:release=50:"
        "level=false:latency=true"
    )


def first_pass_v2(ffmpeg, path, genre_key, factor):
    g = legacy.GENRES[genre_key]
    af = (
        build_pre_chain_v2(genre_key, factor)
        + f",loudnorm=I={g['target_i']}:TP={g['target_tp']}:"
        f"LRA={g['target_lra']}:print_format=json"
    )
    rc, _, err = legacy.run_ffmpeg(
        ffmpeg,
        ["-hide_banner", "-nostats", "-i", str(path), "-af", af, "-f", "null", "-"],
    )
    return (legacy.extract_loudnorm_json(err), err) if rc == 0 else (None, err)


def master_two_pass_v2(ffmpeg, src, dst, genre_key, factor, stats):
    g = legacy.GENRES[genre_key]
    needed = ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"]
    if not stats or any(key not in stats for key in needed):
        return False, "2-pass 측정값 누락"

    loud = (
        f"loudnorm=I={g['target_i']}:TP={g['target_tp']}:LRA={g['target_lra']}"
        f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
        f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}:linear=true:print_format=summary"
    )
    af = build_pre_chain_v2(genre_key, factor) + "," + loud + "," + limiter_filter(genre_key)
    rc, _, err = legacy.run_ffmpeg(
        ffmpeg,
        [
            "-y", "-hide_banner", "-i", str(src),
            "-af", af,
            "-ar", "48000",
            "-c:a", "pcm_s24le",
            str(dst),
        ],
    )
    return rc == 0, err


def master_one_pass_v2(ffmpeg, src, dst, genre_key):
    g = legacy.GENRES[genre_key]
    loud = (
        f"loudnorm=I={g['target_i']}:TP={g['target_tp']}:"
        f"LRA={g['target_lra']}:print_format=summary"
    )
    af = build_pre_chain_v2(genre_key, 1.0) + "," + loud + "," + limiter_filter(genre_key)
    rc, _, err = legacy.run_ffmpeg(
        ffmpeg,
        [
            "-y", "-hide_banner", "-i", str(src),
            "-af", af,
            "-ar", "48000",
            "-c:a", "pcm_s24le",
            str(dst),
        ],
    )
    return rc == 0, err


def warnings_for_v2(raw, final, genre_key):
    warns = []
    src_tp = legacy.safe_float(raw.get("input_tp")) if raw else None
    src_lra = legacy.safe_float(raw.get("input_lra")) if raw else None
    final_i = legacy.safe_float(final.get("input_i")) if final else None
    final_tp = legacy.safe_float(final.get("input_tp")) if final else None
    g = legacy.GENRES[genre_key]
    target = float(g["target_i"])
    ceiling = float(g["target_tp"])

    if src_tp is not None and src_tp > 0.0:
        warns.append("원본 True Peak가 0 dBTP 초과")
    if src_lra is not None and src_lra >= 18:
        warns.append("원본 다이내믹이 매우 큼 — 과압축 방지 모드 적용")
    if src_lra is not None and src_lra <= 2.0:
        warns.append("원본이 이미 강하게 압축됨 — 추가 압축 최소화 필요")
    if final_i is not None and abs(final_i - target) > 0.35:
        warns.append("최종 음량이 v2 목표에서 ±0.35 LU 이상 벗어남")
    if final_tp is not None and final_tp > ceiling + 0.10:
        warns.append("최종 True Peak가 채널 ceiling을 초과")
    return warns


def patch_runtime():
    apply_v2_genres()
    legacy.APP_NAME = "HARU / SUNO 15-SET MASTERING v2.0 - Channel Aware"
    legacy.build_pre_chain = build_pre_chain_v2
    legacy.first_pass = first_pass_v2
    legacy.master_two_pass = master_two_pass_v2
    legacy.master_one_pass = master_one_pass_v2
    legacy.warnings_for = warnings_for_v2


if __name__ == "__main__":
    patch_runtime()
    legacy.App().mainloop()
