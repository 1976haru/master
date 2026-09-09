# -*- coding: utf-8 -*-
"""HARU Mastering v3.7 - expanded multi-genre presets.

Adds senior, Japanese, K-pop, kids and general-purpose mastering profiles
without changing the validated v3.6.1 mastering/report pipeline.
"""
from __future__ import annotations

import copy
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V361_PATH = ROOT / "Suno15_Mastering_v3_6_1.pyw"


def _load_v361():
    loader = SourceFileLoader("suno15_v361", str(V361_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.6.1 프로그램을 불러올 수 없습니다: {V361_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v361 = _load_v361()
v32 = v361.v36.v35.v34.v33.v32
v2 = v32.v2
legacy = v32.legacy

APP_NAME = "HARU / SUNO 15-SET MASTERING v3.7 - MULTI GENRE EDITION"


def _genre(
    label: str,
    target_i: float,
    target_tp: float,
    target_lra: float,
    eq: list[str],
    comp: list[float],
    character: str,
) -> dict:
    return {
        "label": label,
        "target_i": float(target_i),
        "target_tp": float(target_tp),
        "target_lra": float(target_lra),
        "eq": list(eq),
        "comp": list(comp),
        "character": character,
    }


EXPANDED_GENRES = {
    "SENIOR KR": _genre(
        "한국 시니어 감성", -14.2, -1.5, 10,
        ["highpass=f=24", "equalizer=f=260:t=q:w=1.0:g=-0.2", "equalizer=f=2800:t=q:w=1.0:g=0.4", "equalizer=f=7800:t=q:w=1.0:g=-0.3"],
        [0.19, 1.25, 32, 300, 1.01],
        "성숙한 한국어 보컬, 따뜻한 중저역, 부드러운 고역, 장시간 청취 편안함",
    ),
    "SENIOR JP": _genre(
        "日本シニア 감성", -14.3, -1.5, 11,
        ["highpass=f=22", "equalizer=f=260:t=q:w=1.0:g=-0.2", "equalizer=f=2600:t=q:w=1.0:g=0.3", "equalizer=f=7600:t=q:w=1.0:g=-0.3"],
        [0.21, 1.22, 35, 320, 1.01],
        "일본 시니어용 성숙한 보컬, 자연스러운 일본어 발음, 잔잔한 고역과 편안한 공간감",
    ),
    "ENKA JP": _genre(
        "엔카·歌謡曲", -14.3, -1.5, 10,
        ["highpass=f=24", "equalizer=f=180:t=q:w=0.9:g=0.3", "equalizer=f=360:t=q:w=1.0:g=-0.2", "equalizer=f=2500:t=q:w=1.0:g=0.4", "equalizer=f=7000:t=q:w=1.0:g=-0.5"],
        [0.20, 1.25, 34, 320, 1.01],
        "엔카 특유의 깊은 보컬과 비브라토, 선명한 가사, 과하지 않은 저역과 고역",
    ),
    "TROT KR": _genre(
        "트로트", -13.8, -1.3, 9,
        ["highpass=f=27", "equalizer=f=110:t=q:w=0.9:g=0.3", "equalizer=f=300:t=q:w=1.0:g=-0.3", "equalizer=f=2800:t=q:w=1.0:g=0.6", "equalizer=f=7200:t=q:w=1.0:g=-0.2"],
        [0.17, 1.42, 24, 240, 1.03],
        "또렷한 한국어 보컬, 리듬의 추진력, 단단하지만 과하지 않은 저역, 편안한 고역",
    ),
    "J-BALLAD": _genre(
        "일본어 발라드", -14.0, -1.3, 10,
        ["highpass=f=25", "equalizer=f=250:t=q:w=1.0:g=-0.3", "equalizer=f=2700:t=q:w=1.0:g=0.5", "equalizer=f=7200:t=q:w=1.0:g=-0.3"],
        [0.18, 1.32, 30, 280, 1.02],
        "일본어 가사 전달력, 감정과 호흡 보존, 피아노·스트링의 자연스러운 깊이",
    ),
    "POP": _genre(
        "팝", -14.0, -1.2, 9,
        ["highpass=f=27", "equalizer=f=100:t=q:w=0.9:g=0.3", "equalizer=f=280:t=q:w=1.0:g=-0.4", "equalizer=f=3200:t=q:w=1.0:g=0.5"],
        [0.17, 1.42, 23, 230, 1.03],
        "보컬과 훅의 균형, 정돈된 저역, 선명하지만 피곤하지 않은 현대 팝 사운드",
    ),
    "K-POP": _genre(
        "K-POP", -14.0, -1.2, 9,
        ["highpass=f=28", "equalizer=f=90:t=q:w=0.8:g=0.5", "equalizer=f=260:t=q:w=1.0:g=-0.6", "equalizer=f=3300:t=q:w=1.0:g=0.7", "equalizer=f=9000:t=q:w=1.0:g=0.2"],
        [0.16, 1.50, 20, 210, 1.04],
        "선명한 보컬과 훅, 타이트한 킥·베이스, 넓은 공간감, 과도한 음압과 고역은 억제",
    ),
    "CITY POP JP": _genre(
        "일본 시티팝", -14.0, -1.3, 10,
        ["highpass=f=25", "equalizer=f=90:t=q:w=0.9:g=0.4", "equalizer=f=300:t=q:w=1.0:g=-0.3", "equalizer=f=3000:t=q:w=1.0:g=0.4", "equalizer=f=9000:t=q:w=1.0:g=0.2"],
        [0.18, 1.34, 28, 260, 1.02],
        "도시적인 베이스와 키보드, 자연스러운 일본어 보컬, 부드러운 빈티지 광택",
    ),
    "ACOUSTIC": _genre(
        "어쿠스틱·포크", -14.5, -1.5, 12,
        ["highpass=f=22", "equalizer=f=240:t=q:w=1.0:g=-0.2", "equalizer=f=3500:t=q:w=1.0:g=0.2"],
        [0.22, 1.18, 40, 340, 1.00],
        "기타와 생악기의 질감, 보컬 호흡, 넓은 다이내믹과 자연스러운 룸감을 보존",
    ),
    "ROCK": _genre(
        "록·밴드", -13.8, -1.2, 9,
        ["highpass=f=27", "equalizer=f=100:t=q:w=0.9:g=0.4", "equalizer=f=300:t=q:w=1.0:g=-0.4", "equalizer=f=2800:t=q:w=1.0:g=0.4", "equalizer=f=8500:t=q:w=1.0:g=-0.1"],
        [0.16, 1.48, 18, 220, 1.04],
        "드럼과 기타의 에너지, 보컬 중심, 트랜지언트 보존, 거친 고역과 저중역 혼탁 억제",
    ),
    "KIDS POP": _genre(
        "동요·키즈팝", -14.0, -1.3, 8,
        ["highpass=f=30", "equalizer=f=180:t=q:w=1.0:g=-0.2", "equalizer=f=3000:t=q:w=1.0:g=0.5", "equalizer=f=7500:t=q:w=1.0:g=-0.3"],
        [0.18, 1.35, 22, 220, 1.02],
        "어린이 보컬과 가사의 명료도, 밝고 친근한 악기, 자극적이지 않은 고역과 안전한 피크",
    ),
    "LOFI": _genre(
        "로파이·카페", -14.5, -1.5, 10,
        ["highpass=f=25", "equalizer=f=120:t=q:w=0.9:g=0.2", "equalizer=f=320:t=q:w=1.0:g=-0.2", "equalizer=f=6500:t=q:w=1.0:g=-0.4"],
        [0.21, 1.20, 34, 320, 1.01],
        "잔잔한 질감과 따뜻한 저중역, 부드러운 트랜지언트, 오래 들어도 피곤하지 않은 카페 사운드",
    ),
    "INSTRUMENTAL": _genre(
        "연주·뉴에이지", -14.5, -1.5, 12,
        ["highpass=f=22", "equalizer=f=250:t=q:w=1.0:g=-0.2", "equalizer=f=4200:t=q:w=1.0:g=0.2"],
        [0.23, 1.15, 42, 350, 1.00],
        "피아노와 연주 악기의 다이내믹, 잔향과 공간, 자연스러운 음색을 최대한 보존",
    ),
    "GENERAL": _genre(
        "기타·일반형", -14.0, -1.5, 10,
        ["highpass=f=25", "equalizer=f=280:t=q:w=1.0:g=-0.2", "equalizer=f=3200:t=q:w=1.0:g=0.2"],
        [0.20, 1.22, 32, 300, 1.01],
        "특정 장르에 치우치지 않는 중립적 음색, 안전한 피크, 자연스러운 다이내믹과 스테레오",
    ),
}

GENRE_DISPLAY_ORDER = (
    "OLD POP", "SENIOR KR", "SENIOR JP", "SHOWA JP", "ENKA JP", "TROT KR",
    "BALLAD", "J-BALLAD", "POP", "K-POP", "CITY POP JP",
    "CHILI JP", "CHILI EN", "R&B", "SOUL",
    "JAZZ", "CHANSON", "ACOUSTIC", "ROCK", "KIDS POP", "LOFI",
    "INSTRUMENTAL", "GENERAL",
)

QUICK_GENRES = ("OLD POP", "SENIOR JP", "SHOWA JP", "K-POP", "KIDS POP", "BALLAD")

PROFILE_BASE = {
    "SENIOR KR": "OLD POP",
    "SENIOR JP": "SHOWA JP",
    "ENKA JP": "SHOWA JP",
    "TROT KR": "CHILI EN",
    "J-BALLAD": "CHILI JP",
    "POP": "CHILI EN",
    "K-POP": "CHILI EN",
    "CITY POP JP": "CHILI JP",
    "ACOUSTIC": "OLD POP",
    "ROCK": "CHILI EN",
    "KIDS POP": "CHILI EN",
    "LOFI": "OLD POP",
    "INSTRUMENTAL": "OLD POP",
    "GENERAL": "OLD POP",
}

_BASE_GET_PROFILE = v2.get_profile


def get_profile_v37(genre_key: str):
    if genre_key not in EXPANDED_GENRES:
        return _BASE_GET_PROFILE(genre_key)
    spec = EXPANDED_GENRES[genre_key]
    base_key = PROFILE_BASE[genre_key]
    profile = copy.deepcopy(_BASE_GET_PROFILE(base_key))
    profile["label"] = spec["label"]
    profile["targetLufsI"] = float(spec["target_i"])
    profile["truePeakCeilingDbtp"] = float(spec["target_tp"])
    profile["maxLraReductionLu"] = {
        "ACOUSTIC": 0.50,
        "INSTRUMENTAL": 0.50,
        "SENIOR JP": 0.60,
        "ENKA JP": 0.60,
        "KIDS POP": 0.80,
        "K-POP": 0.90,
    }.get(genre_key, 0.80)
    profile["intent"] = [spec["character"]]
    return profile


def install_expanded_genres() -> None:
    for key, spec in EXPANDED_GENRES.items():
        legacy.GENRES[key] = copy.deepcopy(spec)
        v2.V2_EQ[key] = list(spec["eq"])
        v2.V2_COMP[key] = list(spec["comp"])
        v2.V2_LRA_TARGETS[key] = float(spec["target_lra"])
        v2.V2_CHARACTER[key] = spec["character"]
        v2.PROFILE_MAP[key] = v2.PROFILE_MAP.get(PROFILE_BASE[key], "old_pop_lounge")

    # Reorder the dictionary so all menus and generated guides are predictable.
    ordered = {}
    for key in GENRE_DISPLAY_ORDER:
        if key in legacy.GENRES:
            ordered[key] = legacy.GENRES[key]
    for key, value in legacy.GENRES.items():
        if key not in ordered:
            ordered[key] = value
    legacy.GENRES.clear()
    legacy.GENRES.update(ordered)
    v2.get_profile = get_profile_v37


install_expanded_genres()


class AppV37(v361.AppV361):
    def __init__(self):
        install_expanded_genres()
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1120x860")
        self.minsize(980, 760)
        self.status_var.set("v3.7 준비 — 올드팝·시니어·일본어·K-POP·동요 등 장르를 선택하세요.")
        self.after(0, self._update_genre_description)

    def _genre_display(self, key: str) -> str:
        item = legacy.GENRES[key]
        return f"{item['label']}  [{key}]"

    def _select_genre(self, key: str) -> None:
        self.genre_var.set(key)
        if hasattr(self, "genre_display_var"):
            self.genre_display_var.set(self._genre_display(key))
        self._update_genre_description()

    def _on_genre_combo(self, _event=None) -> None:
        display = self.genre_display_var.get()
        key = self._genre_display_to_key.get(display)
        if key:
            self.genre_var.set(key)
            self._update_genre_description()

    def _update_genre_description(self) -> None:
        if not hasattr(self, "genre_description_var"):
            return
        key = self.genre_var.get()
        if key not in legacy.GENRES:
            return
        g = legacy.GENRES[key]
        self.genre_description_var.set(
            f"선택: {g['label']}  |  목표 {g['target_i']:.1f} LUFS / "
            f"{g['target_tp']:.1f} dBTP / LRA {g['target_lra']:g}\n"
            f"방향: {g['character']}"
        )

    def _build_master_tab(self):
        ttk = legacy.ttk

        frame = ttk.LabelFrame(self.master_tab, text="1. Suno Studio에서 내보낸 15곡 폴더")
        frame.pack(fill="x", padx=14, pady=(14, 8))
        row = ttk.Frame(frame)
        row.pack(fill="x", padx=10, pady=10)
        ttk.Entry(row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="폴더 선택", command=self.choose_folder).pack(side="left", padx=(8, 0))

        gframe = ttk.LabelFrame(self.master_tab, text="2. 장르 선택 — 빠른 선택 또는 전체 장르")
        gframe.pack(fill="x", padx=14, pady=8)

        quick = ttk.Frame(gframe)
        quick.pack(fill="x", padx=10, pady=(8, 3))
        ttk.Label(quick, text="자주 쓰는 장르", font=("Malgun Gothic", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(4, 12), pady=4
        )
        for index, key in enumerate(QUICK_GENRES):
            ttk.Radiobutton(
                quick,
                text=legacy.GENRES[key]["label"],
                variable=self.genre_var,
                value=key,
                command=lambda selected=key: self._select_genre(selected),
            ).grid(row=0, column=index + 1, sticky="w", padx=8, pady=4)

        all_row = ttk.Frame(gframe)
        all_row.pack(fill="x", padx=10, pady=4)
        ttk.Label(all_row, text=f"전체 장르 {len(GENRE_DISPLAY_ORDER)}개").pack(side="left", padx=(4, 10))
        displays = [self._genre_display(key) for key in GENRE_DISPLAY_ORDER]
        self._genre_display_to_key = dict(zip(displays, GENRE_DISPLAY_ORDER))
        self.genre_display_var = legacy.tk.StringVar()
        self.genre_combo = ttk.Combobox(
            all_row,
            textvariable=self.genre_display_var,
            values=displays,
            state="readonly",
            width=58,
        )
        self.genre_combo.pack(side="left", fill="x", expand=True)
        self.genre_combo.bind("<<ComboboxSelected>>", self._on_genre_combo)

        self.genre_description_var = legacy.tk.StringVar()
        ttk.Label(
            gframe,
            textvariable=self.genre_description_var,
            justify="left",
            wraplength=1020,
        ).pack(fill="x", padx=14, pady=(3, 9))
        self._select_genre("OLD POP")

        qframe = ttk.LabelFrame(self.master_tab, text="3. 품질 모드")
        qframe.pack(fill="x", padx=14, pady=8)
        qinner = ttk.Frame(qframe)
        qinner.pack(fill="x", padx=10, pady=8)
        ttk.Radiobutton(
            qinner,
            text="빠른 마스터 — 급할 때",
            variable=self.quality_var,
            value="FAST",
        ).pack(anchor="w", pady=3)
        ttk.Radiobutton(
            qinner,
            text="품질+ (추천) — 곡별 분석 + Adaptive Compression + 2-pass Loudness + 최종 검증",
            variable=self.quality_var,
            value="QUALITY+",
        ).pack(anchor="w", pady=3)

        bframe = ttk.Frame(self.master_tab)
        bframe.pack(fill="x", padx=14, pady=8)
        self.start_btn = ttk.Button(
            bframe,
            text="▶ 15곡 마스터링 시작",
            command=self.start_mastering,
        )
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 5), ipady=8)
        ttk.Button(
            bframe,
            text="Suno Studio 열기",
            command=lambda: legacy.webbrowser.open(self.STUDIO_URL),
        ).pack(side="left", padx=5, ipady=8)
        ttk.Button(
            bframe,
            text="최근 결과 폴더",
            command=self.open_last_output,
        ).pack(side="left", padx=(5, 0), ipady=8)

        ttk.Progressbar(self.master_tab, variable=self.progress_var, maximum=100).pack(
            fill="x", padx=14, pady=(8, 2)
        )
        ttk.Label(
            self.master_tab,
            textvariable=self.status_var,
            font=("Malgun Gothic", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(2, 8))

        lframe = ttk.LabelFrame(
            self.master_tab,
            text="진행 / 결과 — 숫자는 몰라도 됩니다. PASS / CHECK만 보면 됩니다.",
        )
        lframe.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.log = legacy.tk.Text(lframe, height=10, wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.log.insert("end", "추천: 올드팝은 OLD POP, 일본 시니어는 日本シニア를 선택하세요.\n")
        self.log.insert("end", "분류가 애매한 곡은 '기타·일반형'을 선택하면 안전하게 처리합니다.\n")
        if not self.ffmpeg:
            self.log.insert("end", "[주의] FFmpeg가 없습니다. INSTALL.bat을 먼저 실행하세요.\n")


if __name__ == "__main__":
    AppV37().mainloop()
