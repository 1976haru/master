# -*- coding: utf-8 -*-
"""
SUNO 15-SET MASTERING FINAL v1
15곡 1SET 배치 마스터링 + Suno Studio 문제곡 선택 보완 프롬프트
"""
import os, re, csv, json, math, shutil, subprocess, threading, webbrowser
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "SUNO 15-SET MASTERING FINAL v1.1 - Studio Easy Guide"
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}

GENRES = {
    "BALLAD": {
        "label": "발라드", "target_i": -13.5, "target_tp": -1.0, "target_lra": 10,
        "eq": ["highpass=f=30", "equalizer=f=250:t=q:w=1.0:g=-0.8", "equalizer=f=3000:t=q:w=1.0:g=1.0", "equalizer=f=8500:t=q:w=1.0:g=-0.5"],
        "comp": [0.125, 1.8, 25, 250, 1.08],
        "character": "따뜻한 보컬, 감정 보존, 부드러운 고역, 피아노/스트링 자연스러움",
    },
    "JAZZ": {
        "label": "재즈", "target_i": -15.0, "target_tp": -1.0, "target_lra": 14,
        "eq": ["highpass=f=25", "equalizer=f=220:t=q:w=1.0:g=-0.4", "equalizer=f=4500:t=q:w=1.0:g=0.4"],
        "comp": [0.18, 1.35, 35, 300, 1.00],
        "character": "다이내믹 보존, 공간감, 콘트라베이스/피아노/브러시 질감 유지",
    },
    "CHANSON": {
        "label": "샹송", "target_i": -14.0, "target_tp": -1.0, "target_lra": 11,
        "eq": ["highpass=f=30", "equalizer=f=240:t=q:w=1.0:g=-0.7", "equalizer=f=2600:t=q:w=1.0:g=1.2", "equalizer=f=8000:t=q:w=1.0:g=-0.7"],
        "comp": [0.14, 1.6, 28, 260, 1.06],
        "character": "보컬 중심, 서정성, 빈티지한 온기, 과한 저역/고역 억제",
    },
    "R&B": {
        "label": "리듬앤블루스", "target_i": -12.0, "target_tp": -1.0, "target_lra": 9,
        "eq": ["highpass=f=28", "equalizer=f=90:t=q:w=0.8:g=1.2", "equalizer=f=260:t=q:w=1.0:g=-1.2", "equalizer=f=3200:t=q:w=1.0:g=1.0"],
        "comp": [0.10, 2.2, 15, 180, 1.12],
        "character": "킥/베이스 단단함, 보컬 선명도, 현대적 음압, 저중역 탁함 억제",
    },
    "SOUL": {
        "label": "소울", "target_i": -12.5, "target_tp": -1.0, "target_lra": 10,
        "eq": ["highpass=f=28", "equalizer=f=110:t=q:w=0.9:g=0.8", "equalizer=f=350:t=q:w=1.0:g=0.4", "equalizer=f=3000:t=q:w=1.0:g=1.0", "equalizer=f=8500:t=q:w=1.0:g=-0.4"],
        "comp": [0.11, 2.0, 20, 220, 1.10],
        "character": "두꺼운 보컬, 따뜻한 중역/저역, 드럼 펀치, 감정과 질감 유지",
    },
    "CHILI JP": {
        "label": "칠리랩 일본어", "target_i": -12.5, "target_tp": -1.0, "target_lra": 9,
        "eq": ["highpass=f=28", "equalizer=f=90:t=q:w=0.8:g=1.0", "equalizer=f=250:t=q:w=1.0:g=-1.0", "equalizer=f=2800:t=q:w=1.0:g=0.8", "equalizer=f=6200:t=q:w=1.0:g=-0.5"],
        "comp": [0.105, 2.0, 18, 200, 1.10],
        "character": "일본어 보컬 명료도, 부드러운 고역, 따뜻한 베이스, 장시간 청취 편안함",
    },
    "CHILI EN": {
        "label": "칠리랩 영어", "target_i": -12.0, "target_tp": -1.0, "target_lra": 9,
        "eq": ["highpass=f=28", "equalizer=f=85:t=q:w=0.8:g=1.2", "equalizer=f=250:t=q:w=1.0:g=-1.2", "equalizer=f=3000:t=q:w=1.0:g=1.0", "equalizer=f=9500:t=q:w=1.0:g=0.4"],
        "comp": [0.10, 2.2, 16, 190, 1.12],
        "character": "보컬 존재감, 킥/베이스 펀치, 넓고 깨끗한 공간, 현대적 칠 무드",
    },
}


def get_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def safe_float(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def extract_loudnorm_json(text):
    blocks = re.findall(r'\{\s*"input_i".*?\}', text, flags=re.S)
    if not blocks:
        return None
    try:
        return json.loads(blocks[-1])
    except Exception:
        return None


def run_ffmpeg(ffmpeg, args):
    p = subprocess.run(
        [ffmpeg] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="ignore",
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )
    return p.returncode, p.stdout, p.stderr


def analyze_raw(ffmpeg, path):
    af = "loudnorm=I=-14:TP=-1:LRA=11:print_format=json"
    rc, _, err = run_ffmpeg(ffmpeg, ["-hide_banner", "-nostats", "-i", str(path), "-af", af, "-f", "null", "-"])
    return (extract_loudnorm_json(err), err) if rc == 0 else (None, err)


def adaptive_factor(raw_lra):
    if raw_lra is None: return 1.0
    if raw_lra >= 16: return 1.15
    if raw_lra >= 12: return 1.08
    if raw_lra <= 3: return 0.65
    if raw_lra <= 5: return 0.78
    return 1.0


def build_pre_chain(genre_key, factor=1.0):
    g = GENRES[genre_key]
    th, ratio, attack, release, makeup = g["comp"]
    ratio = 1.0 + (ratio - 1.0) * factor
    filters = list(g["eq"])
    filters.append(f"acompressor=threshold={th}:ratio={ratio:.3f}:attack={attack}:release={release}:makeup={makeup}")
    return ",".join(filters)


def first_pass(ffmpeg, path, genre_key, factor):
    g = GENRES[genre_key]
    af = build_pre_chain(genre_key, factor) + f",loudnorm=I={g['target_i']}:TP={g['target_tp']}:LRA={g['target_lra']}:print_format=json"
    rc, _, err = run_ffmpeg(ffmpeg, ["-hide_banner", "-nostats", "-i", str(path), "-af", af, "-f", "null", "-"])
    return (extract_loudnorm_json(err), err) if rc == 0 else (None, err)


def master_two_pass(ffmpeg, src, dst, genre_key, factor, stats):
    g = GENRES[genre_key]
    needed = ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"]
    if not stats or any(k not in stats for k in needed):
        return False, "2-pass 측정값 누락"
    loud = (
        f"loudnorm=I={g['target_i']}:TP={g['target_tp']}:LRA={g['target_lra']}"
        f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
        f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}:linear=true:print_format=summary"
    )
    limiter = "alimiter=limit=0.891:attack=5:release=50:level=false"
    af = build_pre_chain(genre_key, factor) + "," + loud + "," + limiter
    rc, _, err = run_ffmpeg(ffmpeg, ["-y", "-hide_banner", "-i", str(src), "-af", af, "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])
    return rc == 0, err


def master_one_pass(ffmpeg, src, dst, genre_key):
    g = GENRES[genre_key]
    loud = f"loudnorm=I={g['target_i']}:TP={g['target_tp']}:LRA={g['target_lra']}:print_format=summary"
    limiter = "alimiter=limit=0.891:attack=5:release=50:level=false"
    af = build_pre_chain(genre_key, 1.0) + "," + loud + "," + limiter
    rc, _, err = run_ffmpeg(ffmpeg, ["-y", "-hide_banner", "-i", str(src), "-af", af, "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])
    return rc == 0, err


def warnings_for(raw, final, genre_key):
    warns = []
    src_tp = safe_float(raw.get("input_tp")) if raw else None
    src_lra = safe_float(raw.get("input_lra")) if raw else None
    final_i = safe_float(final.get("input_i")) if final else None
    final_tp = safe_float(final.get("input_tp")) if final else None
    target = GENRES[genre_key]["target_i"]
    if src_tp is not None and src_tp > 0.0: warns.append("원본 True Peak가 0 dBTP 초과")
    if src_lra is not None and src_lra >= 18: warns.append("원본 다이내믹이 매우 큼")
    if src_lra is not None and src_lra <= 2.0: warns.append("원본이 이미 강하게 압축된 편")
    if final_i is not None and abs(final_i - target) > 0.8: warns.append("최종 음량 목표 편차가 큼")
    if final_tp is not None and final_tp > -0.5: warns.append("최종 True Peak 여유 확인 필요")
    return warns


def make_studio_prompt(genre_key, issues=None):
    g = GENRES[genre_key]
    issue_text = " / ".join(issues or []) if issues else "특별한 오류 없음. 필요한 항목만 선택적으로 적용."
    return f"""[Suno Studio 문제곡 선택 보완 프롬프트]
장르: {g['label']} ({genre_key})
장르 목표: {g['character']}
현재 확인사항: {issue_text}

원곡의 멜로디, 조성, 템포, 구조와 가사를 기본적으로 보존하면서 필요한 경우에만 적용해 주세요.
과한 재생성이나 과한 이펙트는 피하고, 원곡보다 자연스럽고 듣기 편한 방향으로 개선해 주세요.

1) 트랙/스템 이름을 사람이 바로 이해할 수 있게 정리해 주세요.
   예: Lead Vocal, Backing Vocal, Drums, Bass, Piano, Guitar, FX.
2) 리드보컬에 실제 문제가 있을 때만 Advanced Stem Split을 사용해 Lead Vocal을 분리해 주세요.
3) 리드보컬 FX가 과하거나 뿌옇게 들릴 때만 FX를 제거한 뒤 EQ와 Compressor를 부드럽게 적용해 주세요.
   Reverb/Delay는 장르의 공간감에 필요한 만큼만 사용해 주세요.
4) 편곡이 비어 보일 때만 멜로디와 어울리는 화성 코러스를 추가해 주세요.
   코러스는 처음에는 Reverb 없이 만들고, 필요할 때만 소량의 공간계를 추가해 주세요.
5) 편곡이 얇을 때만 코드톤에 맞는 Electric Piano 멜로디/보이싱을 은은하게 추가해 주세요.
6) MIDI를 수정해 기타/피아노/리듬 파트를 바꿀 수 있습니다. 만족한 뒤에만 오디오/WAV로 렌더링해 주세요.
7) 보컬 재편곡/재녹음이 필요할 경우 원래 음정과 멜로디 흐름을 최대한 보존해 주세요.
   가사는 사용자가 별도로 요청하지 않는 한 바꾸지 마세요.
8) 플러그인은 Reverb, Delay, EQ Automation, Compressor 중심으로 최소한만 사용해 주세요.
   Tremolo 같은 새 플러그인은 곡에 실제로 필요한 경우에만 만들어 사용해 주세요.
9) 최종 목표는 '효과를 많이 넣은 소리'가 아니라 {g['character']} 입니다.
10) 완료 후 원본 대비 보컬 선명도, 저역 정돈, 고역 피로감, 다이내믹, 공간감이 좋아졌는지 점검해 주세요.
"""



class App(tk.Tk):
    STUDIO_URL = "https://suno.com/studio"
    STUDIO_HELP_URL = "https://help.suno.com/en/categories/2701953-studio-2-0"

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x790")
        self.minsize(900, 720)
        self.folder_var = tk.StringVar()
        self.genre_var = tk.StringVar(value="BALLAD")
        self.quality_var = tk.StringVar(value="QUALITY+")
        self.status_var = tk.StringVar(value="준비: Suno Studio에서 15곡을 WAV로 내보낸 뒤 시작하세요.")
        self.progress_var = tk.DoubleVar(value=0)
        self.ffmpeg = get_ffmpeg()
        self.last_output_dir = None
        self.last_check_items = []
        self._build_ui()

    def _build_ui(self):
        # 상단 공통 바
        top = ttk.Frame(self)
        top.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(top, text="SUNO 15곡 SET 마스터링", font=("Malgun Gothic", 18, "bold")).pack(side="left")
        ttk.Button(top, text="① Suno Studio 열기", command=lambda: webbrowser.open(self.STUDIO_URL)).pack(side="right", padx=4)
        ttk.Button(top, text="공식 Studio 도움말", command=lambda: webbrowser.open(self.STUDIO_HELP_URL)).pack(side="right", padx=4)

        ttk.Label(
            self,
            text="초보자 기준: Studio에서는 '내보내기 + 문제곡만 보완' / 15곡 전체 마스터링은 이 프로그램에서 자동 처리",
            font=("Malgun Gothic", 10, "bold")
        ).pack(anchor="w", padx=16, pady=(0, 8))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.guide_tab = ttk.Frame(self.notebook)
        self.master_tab = ttk.Frame(self.notebook)
        self.check_tab = ttk.Frame(self.notebook)
        self.menu_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.guide_tab, text="① 처음부터 따라하기")
        self.notebook.add(self.master_tab, text="② 15곡 마스터링")
        self.notebook.add(self.check_tab, text="③ CHECK곡 Studio 보완")
        self.notebook.add(self.menu_tab, text="④ Studio 메뉴 사전")

        self._build_guide_tab()
        self._build_master_tab()
        self._build_check_tab()
        self._build_menu_tab()

    def _build_guide_tab(self):
        wrap = 850
        intro = ttk.LabelFrame(self.guide_tab, text="이 프로그램을 쓸 때 딱 이것만 기억하세요")
        intro.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Label(
            intro,
            text="정상곡: Suno Studio에서 바로 WAV Export → 15곡 모이면 '품질+' 자동 마스터링\n문제곡: 자동 마스터링 후 CHECK로 잡힌 곡만 Studio에서 Stem / Remove FX / Chat / Effect를 사용",
            justify="left", wraplength=wrap, font=("Malgun Gothic", 10, "bold")
        ).pack(anchor="w", padx=12, pady=10)

        steps = [
            ("STEP 1 · Suno 곡을 Studio로 열기",
             "Suno Library에서 곡의 ⋯ → Edit → Open in Studio.\n또는 Studio 안에서 오른쪽 Library를 열어 곡을 찾아 Timeline으로 가져옵니다. (Library 단축키: 4)"),
            ("STEP 2 · 정상곡은 수정하지 말고 바로 Export",
             "Studio 화면 오른쪽 위, Timeline 위쪽의 Export → Full Song → WAV.\nStudio 2.0은 Full Song을 32-bit WAV 또는 MP3로 내보낼 수 있습니다. 이 프로그램은 32-bit WAV 입력도 그대로 받습니다."),
            ("STEP 3 · 15곡을 한 폴더에 모으기",
             "예: D:\\00suno-current\\MASTER_INPUT\\EP001\\ 안에 01.wav ~ 15.wav.\n파일명 순서는 01, 02, 03...처럼 시작하면 관리가 가장 쉽습니다."),
            ("STEP 4 · 이 프로그램에서 '품질+' 실행",
             "위 탭의 [② 15곡 마스터링] → 폴더 선택 → 장르 선택 → 품질+ → 시작.\n15곡의 음량/피크/장르 톤을 자동으로 정리하고 문제곡만 CHECK로 표시합니다."),
            ("STEP 5 · CHECK가 있을 때만 Studio로 돌아가기",
             "[③ CHECK곡 Studio 보완] 탭에서 증상 버튼을 누르면 정확한 메뉴 경로와 복붙 프롬프트가 나옵니다.\nPASS곡은 다시 만지지 않아도 됩니다."),
        ]
        for title, body in steps:
            f = ttk.LabelFrame(self.guide_tab, text=title)
            f.pack(fill="x", padx=12, pady=5)
            ttk.Label(f, text=body, justify="left", wraplength=wrap).pack(side="left", fill="x", expand=True, padx=12, pady=8)

        btns = ttk.Frame(self.guide_tab)
        btns.pack(fill="x", padx=12, pady=10)
        ttk.Button(btns, text="Suno Studio 열기", command=lambda: webbrowser.open(self.STUDIO_URL)).pack(side="left", expand=True, fill="x", padx=4, ipady=5)
        ttk.Button(btns, text="15곡 마스터링으로 이동 →", command=lambda: self.notebook.select(self.master_tab)).pack(side="left", expand=True, fill="x", padx=4, ipady=5)

    def _build_master_tab(self):
        frame = ttk.LabelFrame(self.master_tab, text="1. Suno Studio에서 내보낸 15곡 폴더")
        frame.pack(fill="x", padx=14, pady=(14, 8))
        row = ttk.Frame(frame); row.pack(fill="x", padx=10, pady=10)
        ttk.Entry(row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="폴더 선택", command=self.choose_folder).pack(side="left", padx=(8,0))

        gframe = ttk.LabelFrame(self.master_tab, text="2. 장르 선택")
        gframe.pack(fill="x", padx=14, pady=8)
        inner = ttk.Frame(gframe); inner.pack(fill="x", padx=8, pady=8)
        for i, key in enumerate(GENRES):
            ttk.Radiobutton(
                inner, text=f"{GENRES[key]['label']} ({key})",
                variable=self.genre_var, value=key
            ).grid(row=i//2, column=i%2, sticky="w", padx=14, pady=5)

        qframe = ttk.LabelFrame(self.master_tab, text="3. 품질 모드")
        qframe.pack(fill="x", padx=14, pady=8)
        qinner = ttk.Frame(qframe); qinner.pack(fill="x", padx=10, pady=8)
        ttk.Radiobutton(qinner, text="빠른 마스터 — 급할 때", variable=self.quality_var, value="FAST").pack(anchor="w", pady=3)
        ttk.Radiobutton(qinner, text="품질+ (추천) — 곡별 분석 + Adaptive Compression + 2-pass Loudness + 최종 검증", variable=self.quality_var, value="QUALITY+").pack(anchor="w", pady=3)

        bframe = ttk.Frame(self.master_tab); bframe.pack(fill="x", padx=14, pady=8)
        self.start_btn = ttk.Button(bframe, text="▶ 15곡 마스터링 시작", command=self.start_mastering)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0,5), ipady=8)
        ttk.Button(bframe, text="Suno Studio 열기", command=lambda: webbrowser.open(self.STUDIO_URL)).pack(side="left", padx=5, ipady=8)
        ttk.Button(bframe, text="최근 결과 폴더", command=self.open_last_output).pack(side="left", padx=(5,0), ipady=8)

        ttk.Progressbar(self.master_tab, variable=self.progress_var, maximum=100).pack(fill="x", padx=14, pady=(8,2))
        ttk.Label(self.master_tab, textvariable=self.status_var, font=("Malgun Gothic", 10, "bold")).pack(anchor="w", padx=16, pady=(2,8))

        lframe = ttk.LabelFrame(self.master_tab, text="진행 / 결과 — 숫자는 몰라도 됩니다. PASS / CHECK만 보면 됩니다.")
        lframe.pack(fill="both", expand=True, padx=14, pady=(0,14))
        self.log = tk.Text(lframe, height=14, wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.log.insert("end", "추천: 처음에는 무조건 '품질+'로 시작하세요.\n")
        self.log.insert("end", "완료 후 PASS는 그대로 사용하고 CHECK만 Studio에서 보완합니다.\n")
        if not self.ffmpeg:
            self.log.insert("end", "[주의] FFmpeg가 없습니다. '설치_한번만.bat'를 먼저 실행하세요.\n")

    def _build_check_tab(self):
        info = ttk.LabelFrame(self.check_tab, text="CHECK곡만 여기서 처리")
        info.pack(fill="x", padx=14, pady=(14,8))
        ttk.Label(
            info,
            text="곡을 Studio로 연 뒤, 아래에서 가장 비슷한 증상을 하나만 선택하세요. 메뉴 경로와 복붙 문장을 자동으로 만들어 줍니다.",
            wraplength=850, justify="left", font=("Malgun Gothic", 10, "bold")
        ).pack(anchor="w", padx=12, pady=10)

        symptom_frame = ttk.LabelFrame(self.check_tab, text="증상 선택")
        symptom_frame.pack(fill="x", padx=14, pady=8)
        symptoms = [
            ("보컬이 뿌옇다 / 리버브 과다", "vocal_fx"),
            ("보컬만 따로 손보고 싶다", "vocal_stem"),
            ("보컬이 작고 뒤에 있다", "vocal_low"),
            ("저음이 붕붕 / 베이스 과다", "bass"),
            ("고음이 거칠고 피곤하다", "harsh"),
            ("편곡이 비어 있다", "thin"),
            ("피아노/기타/리듬을 바꾸고 싶다", "midi"),
            ("전체적인 장르 톤을 다듬고 싶다", "general"),
        ]
        rowf = ttk.Frame(symptom_frame); rowf.pack(fill="x", padx=8, pady=8)
        for i,(label,key) in enumerate(symptoms):
            ttk.Button(rowf, text=label, command=lambda k=key: self.show_studio_fix(k)).grid(row=i//2, column=i%2, sticky="ew", padx=5, pady=5)
        rowf.columnconfigure(0, weight=1); rowf.columnconfigure(1, weight=1)

        result_frame = ttk.LabelFrame(self.check_tab, text="Suno Studio에서 이렇게 하세요")
        result_frame.pack(fill="both", expand=True, padx=14, pady=8)
        self.studio_help_text = tk.Text(result_frame, wrap="word", font=("Malgun Gothic", 10), height=18)
        self.studio_help_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.studio_help_text.insert("end", "위의 증상 버튼을 하나 누르면 정확한 메뉴 경로가 표시됩니다.\n")

        bf = ttk.Frame(self.check_tab); bf.pack(fill="x", padx=14, pady=(0,14))
        ttk.Button(bf, text="현재 안내 전체 복사", command=self.copy_current_studio_help).pack(side="left", expand=True, fill="x", padx=4, ipady=5)
        ttk.Button(bf, text="장르별 전체 보완 프롬프트 복사", command=self.copy_prompt).pack(side="left", expand=True, fill="x", padx=4, ipady=5)
        ttk.Button(bf, text="Suno Studio 열기", command=lambda: webbrowser.open(self.STUDIO_URL)).pack(side="left", expand=True, fill="x", padx=4, ipady=5)

    def _build_menu_tab(self):
        guide = ttk.LabelFrame(self.menu_tab, text="처음에는 메뉴를 전부 배울 필요가 없습니다")
        guide.pack(fill="x", padx=14, pady=(14,8))
        ttk.Label(
            guide,
            text="초록 = 매번 사용 / 주황 = CHECK곡에서만 / 회색 = 나중에 필요할 때",
            font=("Malgun Gothic", 10, "bold")
        ).pack(anchor="w", padx=12, pady=8)

        items = [
            ("매번", "Open in Studio", "Suno Library → 곡 ⋯ → Edit → Open in Studio", "기존 Suno 곡을 Studio로 엽니다."),
            ("매번", "Library", "Studio 오른쪽 Library 버튼 / 키보드 4", "All Songs, Liked, Stems, Uploads, Studio Projects를 찾습니다."),
            ("매번", "Export", "오른쪽 위, Timeline 위 → Export → Full Song", "정상곡은 여기서 WAV로 내보내면 됩니다."),
            ("매번", "Chat Bar", "화면 중앙 반짝임 아이콘 / 트랙·클립 선택 후 Enter", "말로 편집을 지시합니다. 선택한 트랙/클립을 기준으로 작동합니다."),
            ("CHECK", "Remove FX", "오디오 클립 헤더 우클릭 → Remove FX", "리버브/딜레이 등이 과한 보컬을 dry 버전으로 만들 때만 사용합니다."),
            ("CHECK", "Split Stems", "오디오 클립 우클릭 → Split Stems → Split from Mix 또는 Advanced Split", "보컬/베이스 등 한 요소만 따로 손볼 때 사용합니다. 불필요한 Stem 분리는 하지 않습니다."),
            ("CHECK", "Add effect", "트랙 선택 → Add effect → EQ / Compressor / Reverb / Delay", "한 트랙의 소리만 다듬을 때 사용합니다. 효과 체인은 순서를 바꾸고 preset 저장이 가능합니다."),
            ("나중", "MIDI", "MIDI track / Piano Roll", "악기 음표 자체를 바꾸고 싶을 때 사용합니다. 평소 마스터링에는 필요 없습니다."),
            ("나중", "Automation", "파라미터 우클릭 → Automate", "곡 진행에 따라 볼륨/EQ/효과를 움직이고 싶을 때 사용합니다."),
            ("나중", "Custom Plugin", "Chat Bar에 원하는 효과를 설명 → Build It!", "특수효과를 만들 때만 사용합니다. VST/AU 외부 플러그인은 Studio에서 불러오지 않습니다."),
        ]
        tree = ttk.Treeview(self.menu_tab, columns=("use","menu","where","why"), show="headings", height=13)
        tree.heading("use", text="언제")
        tree.heading("menu", text="메뉴")
        tree.heading("where", text="어디서 누르나")
        tree.heading("why", text="용도")
        tree.column("use", width=70, anchor="center")
        tree.column("menu", width=130)
        tree.column("where", width=330)
        tree.column("why", width=360)
        for item in items: tree.insert("", "end", values=item)
        tree.pack(fill="both", expand=True, padx=14, pady=8)

        notes = ttk.LabelFrame(self.menu_tab, text="초보자 단축키 3개만")
        notes.pack(fill="x", padx=14, pady=(0,14))
        ttk.Label(notes, text="Space = 재생/정지    |    Enter = Chat Bar 열기    |    4 = Library 열기", font=("Malgun Gothic", 11, "bold")).pack(anchor="w", padx=12, pady=10)

    def studio_fix_text(self, key):
        genre = self.genre_var.get()
        g = GENRES[genre]
        base = f"장르: {g['label']} / 목표: {g['character']}\n\n"
        data = {
            "vocal_fx": (
                "메뉴 경로\n1) Lead Vocal이 들어있는 오디오 클립의 헤더를 우클릭\n2) Remove FX 선택\n3) 새 dry take가 생기면 들어보고 괜찮을 때 Commit\n4) 필요하면 트랙 선택 → Add effect → EQ / Compressor\n5) Reverb/Delay는 마지막에 아주 조금만\n\n"
                "Chat Bar 복붙\n이 리드보컬의 과한 리버브/딜레이와 뿌연 느낌을 줄이고 자연스럽고 선명하게 만들어줘. 원래 멜로디, 음정, 가사는 유지하고 EQ와 Compressor는 부드럽게, Reverb/Delay는 꼭 필요한 만큼만 사용해줘."
            ),
            "vocal_stem": (
                "메뉴 경로\n1) 오디오 클립 우클릭 → Split Stems\n2) 보컬 하나만 필요하면 Split from Mix에서 Vocal 선택\n3) 더 세밀하게 나누고 싶을 때만 Advanced Split\n4) 분리된 Lead Vocal 트랙만 EQ/Compressor 등으로 손보기\n\n"
                "Chat Bar 복붙\n이 곡에서 리드보컬만 분리해서 따로 다듬고 싶어. 다른 악기는 최대한 그대로 두고 보컬의 자연스러운 질감과 감정을 유지해줘."
            ),
            "vocal_low": (
                "가장 쉬운 방법\n1) Lead Vocal 트랙 선택\n2) 먼저 Volume을 조금 올려 A/B 확인\n3) 그래도 묻히면 Add effect → EQ / Compressor\n4) Chat Bar에 아래 문장 붙여넣기\n\n"
                "Chat Bar 복붙\n리드보컬이 반주 뒤에 묻혀 있어. 보컬을 자연스럽게 앞으로 가져오되 너무 크거나 날카롭게 만들지 말고, 반주의 공간과 감정은 유지해줘."
            ),
            "bass": (
                "가장 쉬운 방법\n1) 베이스가 별도 트랙이면 Bass 트랙 선택\n2) Add effect → EQ로 저역을 과하지 않게 정리\n3) 필요하면 Compressor를 부드럽게\n4) 한 덩어리 믹스라면 무리해서 Stem 분리하지 말고 먼저 자동 마스터링 결과를 비교\n\n"
                "Chat Bar 복붙\n저역이 붕붕거리고 다른 악기를 가려. 킥과 베이스의 힘은 유지하면서 과한 sub/low-mid를 정리하고 보컬이 더 잘 들리게 해줘."
            ),
            "harsh": (
                "가장 쉬운 방법\n1) 거친 소리가 보컬이면 Lead Vocal 트랙 선택\n2) Add effect → EQ\n3) 고역을 과도하게 깎지 말고 피로감만 줄이기\n4) 보컬 FX가 문제면 Remove FX 후 다시 최소 효과 적용\n\n"
                "Chat Bar 복붙\n고역이 조금 거칠고 오래 들으면 피곤해. 밝기와 디테일은 유지하면서 치찰음과 날카로운 고역만 부드럽게 줄여줘."
            ),
            "thin": (
                "메뉴 경로\n1) 편곡이 비어 있는 구간을 선택\n2) Enter로 Chat Bar 열기\n3) 코러스 또는 Electric Piano를 '조연' 수준으로 추가\n4) 생성된 Take를 들어보고 Commit할 때만 유지\n\n"
                "Chat Bar 복붙\n이 구간이 조금 비어 보여. 기존 멜로디와 보컬을 가리지 않는 은은한 화성 코러스와 코드톤 중심의 Electric Piano를 필요한 만큼만 추가해줘. 코러스는 처음에는 reverb 없이 만들어줘."
            ),
            "midi": (
                "메뉴 흐름\n1) 바꾸고 싶은 악기 파트를 선택\n2) MIDI 트랙으로 작업하거나 오디오를 MIDI로 변환/추출\n3) Piano Roll에서 음표/리듬 수정\n4) 만족했을 때만 오디오로 렌더링\n\n"
                "Chat Bar 복붙\n이 파트의 화성과 전체 분위기는 유지하면서 기타/피아노/리듬 MIDI를 더 자연스럽고 세련되게 정리해줘. 보컬과 충돌하지 않게 해줘."
            ),
            "general": (
                "가장 쉬운 방법\n1) 트랙 또는 곡 전체에서 실제로 문제가 있는 부분만 선택\n2) Enter → Chat Bar\n3) 아래 문장으로 먼저 요청\n4) 결과가 좋아졌을 때만 Commit\n\n"
                f"Chat Bar 복붙\n이 곡을 {g['label']} 장르에 맞게 다듬어줘. 목표는 {g['character']}이야. 원래 멜로디, 음정, 템포, 구조, 가사는 유지하고 과한 효과는 피하면서 보컬 선명도, 저역 정돈, 고역 피로감, 다이내믹, 공간감을 자연스럽게 개선해줘."
            ),
        }
        return base + data[key]

    def show_studio_fix(self, key):
        txt = self.studio_fix_text(key)
        self.studio_help_text.delete("1.0", "end")
        self.studio_help_text.insert("end", txt)

    def copy_current_studio_help(self):
        txt = self.studio_help_text.get("1.0", "end").strip()
        if not txt:
            messagebox.showwarning("안내 없음", "먼저 증상 버튼을 선택하세요.")
            return
        self.clipboard_clear(); self.clipboard_append(txt); self.update()
        messagebox.showinfo("복사 완료", "현재 Studio 메뉴 안내와 프롬프트를 복사했습니다.")

    def choose_folder(self):
        p = filedialog.askdirectory(title="Suno Studio에서 내보낸 15곡 폴더 선택")
        if p:
            self.folder_var.set(p)
            count = len([x for x in Path(p).iterdir() if x.is_file() and x.suffix.lower() in AUDIO_EXTS])
            self.status_var.set(f"오디오 {count}곡 감지 — 장르 선택 후 '품질+'로 시작하세요.")

    def copy_prompt(self):
        text = make_studio_prompt(self.genre_var.get())
        self.clipboard_clear(); self.clipboard_append(text); self.update()
        messagebox.showinfo("복사 완료", "장르별 Suno Studio 전체 보완 프롬프트를 복사했습니다.\nCHECK 곡에만 붙여넣어 사용하세요.")

    def append_log(self, text):
        self.log.insert("end", text + "\n"); self.log.see("end")

    def open_last_output(self):
        if not self.last_output_dir or not Path(self.last_output_dir).exists():
            messagebox.showinfo("결과 없음", "아직 이번 실행에서 생성된 결과 폴더가 없습니다.")
            return
        p = str(self.last_output_dir)
        try:
            if os.name == "nt": os.startfile(p)
            else: webbrowser.open(Path(p).as_uri())
        except Exception as e:
            messagebox.showerror("열기 실패", str(e))

    def start_mastering(self):
        if not self.ffmpeg:
            messagebox.showerror("FFmpeg 없음", "'설치_한번만.bat'를 먼저 실행해 주세요."); return
        folder = Path(self.folder_var.get().strip())
        if not folder.exists():
            messagebox.showwarning("폴더 필요", "Suno Studio에서 내보낸 15곡 폴더를 먼저 선택해 주세요."); return
        files = sorted([x for x in folder.iterdir() if x.is_file() and x.suffix.lower() in AUDIO_EXTS], key=lambda p: p.name.lower())
        if not files:
            messagebox.showwarning("오디오 없음", "오디오 파일을 찾지 못했습니다."); return
        if len(files) != 15 and not messagebox.askyesno("15곡이 아닙니다", f"현재 {len(files)}곡입니다. 그래도 처리할까요?"):
            return
        self.start_btn.config(state="disabled"); self.progress_var.set(0); self.log.delete("1.0", "end")
        threading.Thread(target=self._worker, args=(folder, files), daemon=True).start()

    def _worker(self, folder, files):
        genre, mode = self.genre_var.get(), self.quality_var.get()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = folder / f"MASTER_{genre.replace(' ', '_')}_{'QUALITY' if mode == 'QUALITY+' else 'FAST'}_{stamp}"
        out_dir.mkdir(parents=True, exist_ok=True)
        self.last_output_dir = out_dir
        rows, check_items, total = [], [], len(files)
        self.after(0, self.append_log, f"장르: {GENRES[genre]['label']} / 모드: {mode}")
        self.after(0, self.append_log, f"목표: {GENRES[genre]['character']}")
        self.after(0, self.append_log, "-"*56)

        for idx, src in enumerate(files, 1):
            self.after(0, self.status_var.set, f"{idx}/{total} 처리 중: {src.name}")
            self.after(0, self.append_log, f"[{idx:02d}/{total:02d}] {src.name}")
            raw, _ = analyze_raw(self.ffmpeg, src)
            raw_lra = safe_float(raw.get("input_lra")) if raw else None
            factor = adaptive_factor(raw_lra) if mode == "QUALITY+" else 1.0
            dst = out_dir / f"{src.stem}_MASTER.wav"

            if mode == "QUALITY+":
                first, first_err = first_pass(self.ffmpeg, src, genre, factor)
                ok, err = master_two_pass(self.ffmpeg, src, dst, genre, factor, first) if first else (False, first_err)
            else:
                ok, err = master_one_pass(self.ffmpeg, src, dst, genre)

            final = analyze_raw(self.ffmpeg, dst)[0] if ok and dst.exists() else None
            warns = warnings_for(raw, final, genre) if ok else ["마스터링 처리 실패"]
            status = "CHECK" if warns else "PASS"
            if status == "CHECK": check_items.append((src.name, warns))
            rows.append({
                "track": src.name, "status": status,
                "source_LUFS": raw.get("input_i", "") if raw else "",
                "source_dBTP": raw.get("input_tp", "") if raw else "",
                "source_LRA": raw.get("input_lra", "") if raw else "",
                "target_LUFS": GENRES[genre]["target_i"],
                "final_LUFS": final.get("input_i", "") if final else "",
                "final_dBTP": final.get("input_tp", "") if final else "",
                "adaptive_factor": f"{factor:.2f}", "notes": " / ".join(warns),
            })
            if ok:
                self.after(0, self.append_log, f"    → {status} | Final {final.get('input_i','?') if final else '?'} LUFS / {final.get('input_tp','?') if final else '?'} dBTP")
            else:
                self.after(0, self.append_log, "    → ERROR")
                (out_dir / f"ERROR_{src.stem}.txt").write_text((err or "")[-5000:], encoding="utf-8", errors="ignore")
            self.after(0, self.progress_var.set, idx/total*100)

        with open(out_dir / "mastering_report.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        sections = []
        if check_items:
            for name, issues in check_items:
                sections += ["="*72, f"문제곡: {name}", make_studio_prompt(genre, issues)]
        else:
            sections += ["모든 곡이 자동 검사 기준 PASS입니다. Suno Studio 추가 보완은 필수가 아닙니다.", make_studio_prompt(genre)]
        (out_dir / "STUDIO_문제곡_보완_프롬프트.txt").write_text("\n".join(sections), encoding="utf-8")

        self.last_check_items = check_items
        pass_count = sum(r["status"] == "PASS" for r in rows); check_count = len(rows)-pass_count
        summary = f"완료: {len(rows)}곡 | PASS {pass_count} | CHECK {check_count}\n결과 폴더: {out_dir}"
        if check_count:
            summary += "\n다음: [③ CHECK곡 Studio 보완] 탭에서 문제 유형을 눌러 메뉴 안내를 따라가세요."
        else:
            summary += "\n모든 곡 PASS — Studio에 다시 들어갈 필요 없습니다."
        self.after(0, self.append_log, "-"*56); self.after(0, self.append_log, summary)
        self.after(0, self.status_var.set, f"완료 — PASS {pass_count} / CHECK {check_count}")
        self.after(0, self.start_btn.config, {"state":"normal"})
        if check_count:
            self.after(0, lambda: self.notebook.select(self.check_tab))
        self.after(0, lambda: messagebox.showinfo("마스터링 완료", summary))

if __name__ == "__main__":
    App().mainloop()
