# -*- coding: utf-8 -*-
"""HARU Mastering v3.9 - CHANNEL + GENRE / FAST FULLNESS ENGINE."""
from __future__ import annotations

import copy
import csv
import math
import re
import shutil
import time
import traceback
from dataclasses import dataclass, replace
from datetime import datetime
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parent
V38_PATH = ROOT / "Suno15_Mastering_v3_8.pyw"


def _load_v38():
    loader = SourceFileLoader("suno15_v38_for_v39", str(V38_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.8 program cannot be loaded: {V38_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v38 = _load_v38()
v372 = v38.v372
v371 = v38.v371
v37 = v38.v37
v32 = v38.v32
v2 = v38.v2
legacy = v38.legacy

from haru_mastering.analysis import AudioMetrics, analyze_array
from haru_mastering.auto_finish import organize_release_files, write_beginner_summary
from haru_mastering.filenames import final_output_name
from haru_mastering.fullness import (
    MAX_FULLNESS_RENDER_PASSES,
    FullnessDecision,
    default_fullness_mode,
    decide as decide_fullness,
    process as process_fullness,
    reduce_decision_for_guard_reasons,
)
from haru_mastering.profile_catalog import (
    CHANNEL_DISPLAY_ORDER,
    CHANNEL_PROFILES,
    DEFAULT_CHANNEL_KEY,
    DEFAULT_GENRE_KEY,
    DEFAULT_SOUND_MODE,
    GENRE_DISPLAY_ORDER,
    GENRE_PROFILES,
    compose_legacy_genre,
    compose_runtime_profile,
    composite_key,
    normalize_channel_key,
    normalize_genre_key,
)
from haru_mastering.report import write_quality_reports
from haru_mastering.retry_policy import (
    build_track_retry_policy,
    dynamics_stats,
    performance_level,
    slowest_stage,
)
from haru_mastering.version import APP_TITLE, DISPLAY_VERSION, REPORT_VERSION, VERSION
import haru_mastering.report as report_module


APP_NAME = APP_TITLE
SYNC_VERSION = REPORT_VERSION
LOUDNESS_TOLERANCE_LU = float(v372.LOUDNESS_TOLERANCE_LU)

_COMPOSITE_RUNTIME_PROFILES: dict[str, dict] = {}
_BASE_GET_PROFILE_V39 = v2.get_profile
_BASE_PROFILE_PAYLOAD_V39 = v371._ORIGINAL_PROFILE_PAYLOAD


def _runtime_profile_payload_v39():
    """Keep the configured Dynamics limit separate from the v3.7.1 Codec cap."""
    payload = v371._runtime_profile_payload()
    configured = _BASE_PROFILE_PAYLOAD_V39()
    configured_auto = configured.get("global", {}).get("autoFinish", {})
    auto = payload["global"].setdefault("autoFinish", {})
    auto["maximumAutoRerenders"] = int(configured_auto.get("maximumAutoRerenders", 2))
    return payload


@dataclass
class TrackTiming:
    analysis: float = 0.0
    base_mastering: float = 0.0
    fullness_analysis: float = 0.0
    fullness_render: float = 0.0
    quality_gate: float = 0.0
    codec_preview: float = 0.0
    total: float = 0.0


@dataclass
class SourceContext:
    audio: object
    sample_rate: int
    metrics: AudioMetrics
    raw: dict[str, str]


@dataclass
class AudioContext:
    audio: object
    sample_rate: int
    metrics: AudioMetrics


@dataclass
class TrackCounters:
    base_render_count: int = 0
    transparent_render_count: int = 0
    codec_ceiling_rerender_count: int = 0
    fullness_render_count: int = 0
    quality_gate_count: int = 0
    normal_quality_gate_count: int = 0
    codec_quality_gate_count: int = 0
    normal_quality_gate_limit: int = 3
    codec_quality_gate_limit: int = 2
    codec_sound_reapply_count: int = 0
    accepted_sound_mode: str = "NATURAL"
    accepted_fullness_strength: int = 0
    codec_check_count: int = 0
    fullness_render_limit: int = 2


class QualityGateBudgetExceeded(RuntimeError):
    """Raised only when a per-track Quality Gate budget is truly exhausted."""


TRACK_REPORT_FIELDS = (
    "track",
    "status",
    "channel_profile",
    "music_genre",
    "mastering_profile",
    "source_LUFS",
    "source_dBTP",
    "source_LRA",
    "target_LUFS",
    "final_LUFS",
    "final_dBTP",
    "processing_mode",
    "adaptive_factor",
    "auto_fixes",
    "tail_before_RMS",
    "tail_fix_mode",
    "tail_after_RMS",
    "codec_max_dBTP",
    "stage_analysis_sec",
    "stage_base_mastering_sec",
    "stage_fullness_analysis_sec",
    "stage_fullness_render_sec",
    "stage_quality_gate_sec",
    "stage_codec_preview_sec",
    "base_render_count",
    "transparent_render_count",
    "codec_ceiling_rerender_count",
    "fullness_render_count",
    "quality_gate_count",
    "normal_quality_gate_count",
    "codec_final_quality_gate_count",
    "codec_sound_reapply_count",
    "codec_check_count",
    "notes",
)


@dataclass
class CandidateFinish:
    ok: bool
    error: str
    result: object | None
    tail_repair: object | None
    timings: TrackTiming
    fullness_render_count: int
    last_reasons: list[str]
    recommended_fullness_strength: int | None = None


def _get_profile_v39(genre_key: str):
    key = str(genre_key)
    if key in _COMPOSITE_RUNTIME_PROFILES:
        return copy.deepcopy(_COMPOSITE_RUNTIME_PROFILES[key])
    return _BASE_GET_PROFILE_V39(genre_key)


def install_v39_runtime() -> None:
    v38.install_v38_runtime()
    v32.v3._profile_payload = _runtime_profile_payload_v39
    v2.get_profile = _get_profile_v39
    report_module.QUALITY_REPORT_VERSION = REPORT_VERSION
    v38.report_module.QUALITY_REPORT_VERSION = REPORT_VERSION

    for genre in GENRE_PROFILES.values():
        legacy.GENRES[genre.key] = {
            "label": genre.label,
            "target_i": -14.0,
            "target_tp": -1.5,
            "target_lra": float(genre.target_lra),
            "eq": list(genre.eq),
            "comp": list(genre.comp),
            "character": genre.character,
        }

    for channel_key in CHANNEL_DISPLAY_ORDER:
        channel = CHANNEL_PROFILES[channel_key]
        for genre_key in GENRE_DISPLAY_ORDER:
            key = composite_key(channel_key, genre_key)
            legacy.GENRES[key] = compose_legacy_genre(channel_key, genre_key)
            base = _profile_for_channel(channel.profile_name)
            _COMPOSITE_RUNTIME_PROFILES[key] = compose_runtime_profile(
                base,
                channel_key,
                genre_key,
            )
            v2.PROFILE_MAP[key] = channel.profile_name


def _profile_for_channel(profile_name: str) -> dict:
    payload = v2.load_profiles(v2.PROFILE_PATH)
    return v2.resolve_profile(payload, profile_name)


install_v39_runtime()


def _format_metric(value: float) -> str:
    number = float(value)
    return f"{number:.2f}" if math.isfinite(number) else "-inf"


def _metrics_as_raw(metrics: AudioMetrics) -> dict[str, str]:
    return {
        "input_i": _format_metric(metrics.lufs_i),
        "input_tp": _format_metric(metrics.true_peak_dbtp),
        "input_lra": _format_metric(metrics.lra_lu),
    }


def _has_issue(result, prefix: str) -> bool:
    return any(str(issue).startswith(prefix) for issue in getattr(result, "issues", ()))


def _append_unique(items: list[str], text: str) -> None:
    if text and text not in items:
        items.append(text)


def _automatic_limit_text(track: str, issues: list[str], profile_label: str) -> str:
    lines = [
        "=" * 72,
        f"자동 해결 한도 초과: {track}",
        f"프로필: {profile_label}",
        "",
        "프로그램이 압축 완화, 투명 마스터링, Tail 자동수정, 코덱 보호를 모두 시도했습니다.",
        "",
        "남은 문제:",
    ]
    lines.extend(f"- {issue}" for issue in issues)
    lines += [
        "",
        "권장 조치:",
        "- 이 파일은 02_NEEDS_REVIEW에 자동 분리됩니다.",
        "- 원본 WAV를 Suno Studio에서 다시 Export하거나 해당 곡만 재생성한 뒤 다시 실행하세요.",
    ]
    return "\n".join(lines)


class AppV39(v38.AppV38):
    def _build_ui(self):
        self.channel_var = legacy.tk.StringVar(value=DEFAULT_CHANNEL_KEY)
        if hasattr(self, "genre_var"):
            self.genre_var.set(DEFAULT_GENRE_KEY)
        self._fullness_render_count = 0
        self._codec_preview_count = 0
        self._source_analyze_count = 0
        self._stage_timings: dict[str, TrackTiming] = {}
        super()._build_ui()

    def __init__(self):
        install_v39_runtime()
        super().__init__()
        install_v39_runtime()
        self.title(APP_NAME)
        self.status_var.set(
            f"HARU Mastering v{VERSION} 준비 - 채널과 음악 장르를 분리하고 Fullness 재처리를 줄였습니다."
        )
        self.after(0, self._update_genre_description)

    def append_log(self, text):
        value = str(text)
        for old in ("v3.8.1", "v3.8", "v3.7.2", "v3.7.1", "v3.7", "v3.6.1", "v3.6", "v3.5", "v3.4", "v3.3", "v3.2"):
            value = re.sub(rf"{re.escape(old)}(?![\d.])", f"v{VERSION}", value)
        return super().append_log(value)

    def _channel_display(self, key: str) -> str:
        return CHANNEL_PROFILES[key].label

    def _genre_display(self, key: str) -> str:
        item = GENRE_PROFILES[key]
        return f"{item.label}  [{key}]"

    def _mastering_key(self) -> str:
        return composite_key(self.channel_var.get(), self.genre_var.get())

    def _select_channel(self, key: str) -> None:
        self.channel_var.set(normalize_channel_key(key))
        self._update_genre_description()

    def _select_genre(self, key: str) -> None:
        pure_key = normalize_genre_key(key)
        self.genre_var.set(pure_key)
        if hasattr(self, "genre_display_var"):
            self.genre_display_var.set(self._genre_display(pure_key))
        if hasattr(self, "sound_var") and not self.sound_var.get():
            self.sound_var.set(DEFAULT_SOUND_MODE)
        self._update_genre_description()

    def _on_genre_combo(self, _event=None) -> None:
        display = self.genre_display_var.get()
        key = self._genre_display_to_key.get(display)
        if key:
            self._select_genre(key)

    def _fullness_mode(self, _genre: str = "") -> str:
        if hasattr(self, "sound_var"):
            return self.sound_var.get()
        return DEFAULT_SOUND_MODE

    def _update_genre_description(self) -> None:
        if not hasattr(self, "genre_description_var"):
            return
        channel_key = normalize_channel_key(self.channel_var.get())
        genre_key = normalize_genre_key(self.genre_var.get())
        channel = CHANNEL_PROFILES[channel_key]
        genre = GENRE_PROFILES[genre_key]
        combined = legacy.GENRES.get(composite_key(channel_key, genre_key))
        if combined is None:
            combined = compose_legacy_genre(channel_key, genre_key)
        sound = "풍부함+ (추천)" if self._fullness_mode() == "RICH" else "자연스러움"
        self.genre_description_var.set(
            f"채널: {channel.label} - {channel.character}\n"
            f"장르: {genre.label} - {genre.character}\n"
            f"합성 목표: {combined['target_i']:.1f} LUFS / "
            f"{combined['target_tp']:.1f} dBTP / LRA {combined['target_lra']:g} / 사운드 {sound}"
        )
        if hasattr(self, "fullness_status_var"):
            self.fullness_status_var.set(
                f"{DISPLAY_VERSION} - Fullness 최대 {MAX_FULLNESS_RENDER_PASSES}회, Codec Preview는 최종 후보 기준"
            )

    def _build_master_tab(self):
        ttk = legacy.ttk

        frame = ttk.LabelFrame(self.master_tab, text="1. Suno Studio에서 내보낸 15곡 폴더")
        frame.pack(fill="x", padx=14, pady=(14, 8))
        row = ttk.Frame(frame)
        row.pack(fill="x", padx=10, pady=10)
        ttk.Entry(row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="폴더 선택", command=self.choose_folder).pack(side="left", padx=(8, 0))

        cframe = ttk.LabelFrame(self.master_tab, text="2. 채널 / 마스터링 프리셋")
        cframe.pack(fill="x", padx=14, pady=8)
        channel_grid = ttk.Frame(cframe)
        channel_grid.pack(fill="x", padx=10, pady=8)
        for index, key in enumerate(CHANNEL_DISPLAY_ORDER):
            ttk.Radiobutton(
                channel_grid,
                text=CHANNEL_PROFILES[key].label,
                variable=self.channel_var,
                value=key,
                command=lambda selected=key: self._select_channel(selected),
            ).grid(row=index // 3, column=index % 3, sticky="w", padx=8, pady=4)

        gframe = ttk.LabelFrame(self.master_tab, text="3. 음악 장르")
        gframe.pack(fill="x", padx=14, pady=8)
        all_row = ttk.Frame(gframe)
        all_row.pack(fill="x", padx=10, pady=8)
        ttk.Label(all_row, text=f"장르 {len(GENRE_DISPLAY_ORDER)}개").pack(side="left", padx=(4, 10))
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
        ).pack(fill="x", padx=14, pady=(0, 9))
        self._select_genre(DEFAULT_GENRE_KEY)

        qframe = ttk.LabelFrame(self.master_tab, text="4. 품질 모드")
        qframe.pack(fill="x", padx=14, pady=8)
        qinner = ttk.Frame(qframe)
        qinner.pack(fill="x", padx=10, pady=8)
        ttk.Radiobutton(
            qinner,
            text="FAST - 최소 분석 + Fullness 최대 1 pass + Codec final 1회",
            variable=self.quality_var,
            value="FAST",
        ).pack(anchor="w", pady=3)
        ttk.Radiobutton(
            qinner,
            text="QUALITY+ (추천) - 추가 검증 + Fullness 최대 2 passes + Codec final 1회",
            variable=self.quality_var,
            value="QUALITY+",
        ).pack(anchor="w", pady=3)

        sframe = ttk.LabelFrame(self.master_tab, text="5. 사운드 성향")
        sframe.pack(fill="x", padx=14, pady=8)
        sinner = ttk.Frame(sframe)
        sinner.pack(fill="x", padx=10, pady=8)
        ttk.Radiobutton(
            sinner,
            text="자연스러움",
            variable=self.sound_var,
            value="NATURAL",
            command=self._on_sound_mode_changed,
        ).pack(side="left", padx=(0, 24))
        ttk.Radiobutton(
            sinner,
            text="풍부함+ (추천)",
            variable=self.sound_var,
            value="RICH",
            command=self._on_sound_mode_changed,
        ).pack(side="left")
        self.sound_var.set(DEFAULT_SOUND_MODE)
        ttk.Label(
            sframe,
            textvariable=self.fullness_status_var,
            justify="left",
        ).pack(fill="x", padx=14, pady=(0, 8))

        bframe = ttk.Frame(self.master_tab)
        bframe.pack(fill="x", padx=14, pady=8)
        self.start_btn = ttk.Button(
            bframe,
            text="15곡 마스터링 시작",
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
            text="진행 / 결과 - 곡 내부 단계와 소요시간을 표시합니다.",
        )
        lframe.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.log = legacy.tk.Text(lframe, height=10, wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.log.insert("end", "기본값: 올드팝 라운지 + 팝 + 풍부함+.\n")
        self.log.insert("end", "채널은 사운드 방향, 장르는 음악 특성만 담당합니다.\n")
        if not self.ffmpeg:
            self.log.insert("end", "[주의] FFmpeg가 없습니다. INSTALL.bat을 먼저 실행하세요.\n")

    def _on_sound_mode_changed(self):
        self._update_genre_description()

    def _stage_status(self, index: int, total: int, stage: str, source: Path) -> None:
        self.after(0, self.status_var.set, f"{index:02d}/{total:02d} {stage}: {source.name}")

    def _stage_log(self, index: int, total: int, stage: str, seconds: float) -> None:
        self.after(0, self.append_log, f"[{index:02d}/{total:02d}] {stage}: {seconds:.1f} sec")

    def _source_context(self, source: Path) -> SourceContext:
        audio, sample_rate = sf.read(source, always_2d=True, dtype="float64")
        metrics = analyze_array(audio, sample_rate)
        self._source_analyze_count += 1
        return SourceContext(audio=audio, sample_rate=sample_rate, metrics=metrics, raw=_metrics_as_raw(metrics))

    def _audio_context(self, path: Path) -> AudioContext:
        audio, sample_rate = sf.read(path, always_2d=True, dtype="float64")
        metrics = analyze_array(audio, sample_rate)
        return AudioContext(audio=audio, sample_rate=sample_rate, metrics=metrics)

    def _evaluate_candidate(
        self,
        source: Path,
        candidate: Path,
        gate_kwargs: dict,
        source_ctx: SourceContext,
        counters: TrackCounters,
        *,
        gate_scope: str = "normal",
        processed_audio=None,
        processed_sample_rate: int | None = None,
        processed_metrics: AudioMetrics | None = None,
    ):
        if gate_scope == "codec":
            current_count = counters.codec_quality_gate_count
            limit = counters.codec_quality_gate_limit
        else:
            current_count = counters.normal_quality_gate_count
            limit = counters.normal_quality_gate_limit
        if current_count >= limit:
            raise QualityGateBudgetExceeded(
                f"{gate_scope} Quality Gate limit exceeded "
                f"({current_count}/{limit})"
            )
        counters.quality_gate_count += 1
        if gate_scope == "codec":
            counters.codec_quality_gate_count += 1
        else:
            counters.normal_quality_gate_count += 1
        return v32.evaluate_master(
            source,
            candidate,
            **gate_kwargs,
            source_audio=source_ctx.audio,
            source_sample_rate=source_ctx.sample_rate,
            source_metrics=source_ctx.metrics,
            processed_audio=processed_audio,
            processed_sample_rate=processed_sample_rate,
            processed_metrics=processed_metrics,
        )

    def _metadata_from_decision(
        self,
        decision: FullnessDecision,
        *,
        retry_count: int,
        auto_reduced: bool,
        bypassed_reason: str,
    ):
        return v38.FullnessCsvRow(
            mode=decision.mode,
            strength_percent=decision.strength_percent,
            warmth_gain_db=decision.warmth_gain_db,
            body_gain_db=decision.body_gain_db,
            saturation_wet_percent=decision.saturation_wet_percent,
            density_wet_percent=decision.density_wet_percent,
            auto_reduced=auto_reduced,
            retry_count=retry_count,
            bypassed_reason=bypassed_reason,
        )

    def _fullness_decision(
        self,
        metrics: AudioMetrics,
        mastering_key: str,
        profile: dict,
        *,
        mode: str,
        strength_percent: int,
    ) -> FullnessDecision:
        return decide_fullness(
            metrics,
            genre_key=mastering_key,
            mode=mode,
            strength_percent=strength_percent,
            profile=profile,
        )

    def _render_fullness_candidate(
        self,
        base: Path,
        dst: Path,
        decision: FullnessDecision,
        base_ctx: AudioContext,
        timing: TrackTiming,
        counters: TrackCounters,
        *,
        count_scope: str = "normal",
    ):
        if count_scope == "codec":
            if counters.codec_sound_reapply_count >= 1:
                raise QualityGateBudgetExceeded(
                    "codec sound reapply limit exceeded (1/1)"
                )
        elif counters.fullness_render_count >= counters.fullness_render_limit:
            raise RuntimeError(
                f"Fullness render count exceeded track limit "
                f"({counters.fullness_render_count}/{counters.fullness_render_limit})"
            )
        start = time.perf_counter()
        render = process_fullness(
            base,
            dst,
            decision,
            source_metrics=base_ctx.metrics,
            source_audio=base_ctx.audio,
            source_sample_rate=base_ctx.sample_rate,
            analyze_after=True,
            return_audio=True,
        )
        timing.fullness_render += time.perf_counter() - start
        if count_scope == "codec":
            counters.codec_sound_reapply_count += 1
        else:
            self._fullness_render_count += 1
            counters.fullness_render_count += 1
        return render

    def _finish_candidate(
        self,
        source: Path,
        base: Path,
        dst: Path,
        mastering_key: str,
        gate_kwargs: dict,
        auto_cfg: dict,
        profile: dict,
        source_ctx: SourceContext,
        base_ctx: AudioContext,
        fixes: list[str],
        counters: TrackCounters,
        *,
        max_fullness_passes: int,
        track_index: int,
        track_total: int,
        initial_strength: int | None = None,
        force_natural: bool = False,
    ) -> CandidateFinish:
        timing = TrackTiming()
        track = source.name
        sound_mode = "NATURAL" if force_natural else self._fullness_mode(mastering_key)
        base_metrics = base_ctx.metrics

        def evaluate_with_optional_cache(
            *,
            tail_repair,
            gate_scope: str = "normal",
            processed_audio=None,
            processed_sample_rate: int | None = None,
            processed_metrics: AudioMetrics | None = None,
        ):
            if getattr(tail_repair, "mode", "none") != "none":
                processed_audio = None
                processed_sample_rate = None
                processed_metrics = None
            start_qg = time.perf_counter()
            evaluated = self._evaluate_candidate(
                source,
                dst,
                gate_kwargs,
                source_ctx,
                counters,
                gate_scope=gate_scope,
                processed_audio=processed_audio,
                processed_sample_rate=processed_sample_rate,
                processed_metrics=processed_metrics,
            )
            elapsed = time.perf_counter() - start_qg
            timing.quality_gate += elapsed
            gate_count = (
                counters.codec_quality_gate_count
                if gate_scope == "codec"
                else counters.normal_quality_gate_count
            )
            gate_label = "Codec Final Gate" if gate_scope == "codec" else "Quality Gate"
            self._stage_log(track_index, track_total, f"{gate_label} #{gate_count}", elapsed)
            return evaluated

        if sound_mode != "RICH":
            decision = self._fullness_decision(
                base_metrics,
                mastering_key,
                profile,
                mode="NATURAL",
                strength_percent=0,
            )
            shutil.copy2(base, dst)
            tail_repair = self._repair_tail(dst, auto_cfg, fixes)
            result = evaluate_with_optional_cache(
                tail_repair=tail_repair,
                processed_audio=base_ctx.audio,
                processed_sample_rate=base_ctx.sample_rate,
                processed_metrics=base_metrics,
            )
            if not result.issues:
                counters.accepted_sound_mode = "NATURAL"
                counters.accepted_fullness_strength = 0
            self._fullness_metadata[track] = self._metadata_from_decision(
                decision,
                retry_count=0,
                auto_reduced=False,
                bypassed_reason="natural_mode" if not force_natural else "transparent_fallback",
            )
            return CandidateFinish(True, "", result, tail_repair, timing, 0, list(result.issues), None)

        default_strength = int(profile.get("fullness", {}).get("defaultStrengthPercent", 100))
        initial = self._fullness_decision(
            base_metrics,
            mastering_key,
            profile,
            mode="RICH",
            strength_percent=default_strength if initial_strength is None else int(initial_strength),
        )
        decision = initial
        last_reasons: list[str] = []
        render_count = 0
        recommended_strength = initial.strength_percent
        allowed_passes = max(
            0,
            min(
                int(max_fullness_passes),
                MAX_FULLNESS_RENDER_PASSES,
                counters.fullness_render_limit - counters.fullness_render_count,
            ),
        )

        for pass_index in range(allowed_passes):
            before_render = timing.fullness_render
            render = self._render_fullness_candidate(base, dst, decision, base_ctx, timing, counters)
            render_seconds = timing.fullness_render - before_render
            render_count += 1
            label = f"Fullness {render.decision.strength_percent}%"
            if pass_index > 0 or (
                initial_strength is not None and initial_strength != default_strength
            ):
                label += " rerender"
            self._stage_log(track_index, track_total, label, render_seconds)
            self.after(
                0,
                self.append_log,
                f"    Fullness render count: "
                f"{counters.fullness_render_count}/{counters.fullness_render_limit}",
            )
            tail_repair = self._repair_tail(dst, auto_cfg, fixes)
            result = evaluate_with_optional_cache(
                tail_repair=tail_repair,
                processed_audio=render.processed_audio,
                processed_sample_rate=render.processed_sample_rate,
                processed_metrics=render.after,
            )
            reasons = list(result.issues)
            if not reasons:
                counters.accepted_sound_mode = "RICH"
                counters.accepted_fullness_strength = render.decision.strength_percent
                self._fullness_metadata[track] = self._metadata_from_decision(
                    render.decision,
                    retry_count=pass_index,
                    auto_reduced=pass_index > 0,
                    bypassed_reason="",
                )
                return CandidateFinish(
                    True,
                    "",
                    result,
                    tail_repair,
                    timing,
                    render_count,
                    [],
                    recommended_strength,
                )

            last_reasons = reasons
            if _has_issue(result, "DYNAMICS RISK"):
                base_stats = dynamics_stats(source_ctx.metrics, base_metrics, gate_kwargs)
                final_stats = dynamics_stats(source_ctx.metrics, result.processed, gate_kwargs)
                self.after(
                    0,
                    self.append_log,
                    "    Dynamics origin: Fullness",
                )
                self.after(
                    0,
                    self.append_log,
                    f"    Base LRA loss: {base_stats.lra_reduction_lu:.2f} LU / "
                    f"crest loss: {base_stats.crest_factor_loss_db:.2f} dB",
                )
                self.after(
                    0,
                    self.append_log,
                    f"    Final LRA loss: {final_stats.lra_reduction_lu:.2f} LU / "
                    f"crest loss: {final_stats.crest_factor_loss_db:.2f} dB",
                )
            if pass_index + 1 >= allowed_passes:
                break
            decision = reduce_decision_for_guard_reasons(decision, reasons)
            recommended_strength = decision.strength_percent
            self.after(
                0,
                self.append_log,
                f"    Fullness guard: {render.decision.strength_percent}% -> "
                f"{decision.strength_percent}% ({' / '.join(reasons)[:160]})",
            )

        fallback = self._fullness_decision(
            base_metrics,
            mastering_key,
            profile,
            mode="NATURAL",
            strength_percent=0,
        )
        shutil.copy2(base, dst)
        tail_repair = self._repair_tail(dst, auto_cfg, fixes)
        result = evaluate_with_optional_cache(
            tail_repair=tail_repair,
            processed_audio=base_ctx.audio,
            processed_sample_rate=base_ctx.sample_rate,
            processed_metrics=base_metrics,
        )
        if not result.issues:
            counters.accepted_sound_mode = "NATURAL"
            counters.accepted_fullness_strength = 0
        self._fullness_metadata[track] = self._metadata_from_decision(
            fallback,
            retry_count=render_count,
            auto_reduced=render_count > 0,
            bypassed_reason=" / ".join(last_reasons) if last_reasons else "guard_reduced_to_off",
        )
        return CandidateFinish(
            True,
            "",
            result,
            tail_repair,
            timing,
            render_count,
            last_reasons,
            recommended_strength,
        )

    def _reapply_accepted_candidate(
        self,
        source: Path,
        base: Path,
        dst: Path,
        mastering_key: str,
        gate_kwargs: dict,
        auto_cfg: dict,
        profile: dict,
        source_ctx: SourceContext,
        base_ctx: AudioContext,
        fixes: list[str],
        counters: TrackCounters,
        *,
        track_index: int,
        track_total: int,
    ):
        """Rebuild only the already accepted sound state after a codec rerender."""
        timing = TrackTiming()
        accepted_mode = str(counters.accepted_sound_mode or "NATURAL").upper()
        accepted_strength = int(counters.accepted_fullness_strength or 0)
        processed_audio = base_ctx.audio
        processed_sample_rate = base_ctx.sample_rate
        processed_metrics = base_ctx.metrics

        if accepted_mode == "RICH" and accepted_strength > 0 and counters.codec_sound_reapply_count < 1:
            decision = self._fullness_decision(
                base_ctx.metrics,
                mastering_key,
                profile,
                mode="RICH",
                strength_percent=accepted_strength,
            )
            before_render = timing.fullness_render
            render = self._render_fullness_candidate(
                base,
                dst,
                decision,
                base_ctx,
                timing,
                counters,
                count_scope="codec",
            )
            self._stage_log(
                track_index,
                track_total,
                f"Codec sound reapply {accepted_strength}%",
                timing.fullness_render - before_render,
            )
            processed_audio = render.processed_audio
            processed_sample_rate = render.processed_sample_rate
            processed_metrics = render.after
        else:
            if accepted_mode == "RICH" and accepted_strength > 0:
                self.after(
                    0,
                    self.append_log,
                    "    Codec sound reapply limit reached; using NATURAL fallback",
                )
            shutil.copy2(base, dst)
            self._stage_log(track_index, track_total, "Codec sound state: NATURAL", 0.0)

        tail_repair = self._repair_tail(dst, auto_cfg, fixes)
        if getattr(tail_repair, "mode", "none") != "none":
            processed_audio = None
            processed_sample_rate = None
            processed_metrics = None
        self._stage_status(track_index, track_total, "codec final quality check", source)
        start = time.perf_counter()
        result = self._evaluate_candidate(
            source,
            dst,
            gate_kwargs,
            source_ctx,
            counters,
            gate_scope="codec",
            processed_audio=processed_audio,
            processed_sample_rate=processed_sample_rate,
            processed_metrics=processed_metrics,
        )
        elapsed = time.perf_counter() - start
        timing.quality_gate += elapsed
        self._stage_log(
            track_index,
            track_total,
            f"Codec Final Gate #{counters.codec_quality_gate_count}",
            elapsed,
        )
        return result, tail_repair, timing

    def _render_base(self, source: Path, base: Path, mastering_key: str, factor: float, mode: str):
        if mode == "QUALITY+":
            return v372.AppV372._render_quality(self, source, base, mastering_key, factor)
        return legacy.master_one_pass(self.ffmpeg, source, base, mastering_key)

    def _render_transparent_base(
        self,
        source: Path,
        base: Path,
        mastering_key: str,
        auto_cfg: dict,
    ):
        return v372.AppV372._render_transparent(
            self,
            source,
            base,
            mastering_key,
            highpass_hz=float(auto_cfg.get("transparentHighpassHz", 10.0)),
        )

    def _refresh_v39_reports(self, output_dir: Path) -> None:
        if hasattr(self, "_patch_csv_with_codec_gain"):
            self._patch_csv_with_codec_gain(output_dir)
        if hasattr(self, "_patch_csv_with_delay_diagnostics"):
            self._patch_csv_with_delay_diagnostics(output_dir)
        if hasattr(self, "_patch_csv_with_adaptive_tail"):
            self._patch_csv_with_adaptive_tail(output_dir)
        try:
            v37.v361.v36._refresh_final_tail_csv(output_dir)
        except Exception:
            pass
        v372._refresh_final_metrics_csv_v372(output_dir)
        v38.patch_csv_with_fullness(output_dir, self._fullness_metadata)
        v38._refresh_completion_text_files_v38(output_dir)
        if hasattr(self, "_refresh_beginner_summary"):
            self._refresh_beginner_summary(output_dir)

    def _record_track_error(
        self,
        track_index: int,
        track_total: int,
        source: Path,
        output_dir: Path,
        error: BaseException,
    ) -> str:
        message = f"{type(error).__name__}: {error}"
        trace = traceback.format_exc()
        error_path = output_dir / f"ERROR_{track_index:02d}_{source.stem}.txt"
        try:
            error_path.write_text(trace[-10000:], encoding="utf-8", errors="ignore")
        except OSError:
            pass
        self.after(0, self.append_log, f"[{track_index:02d}/{track_total:02d}] ERROR: {message}")
        self.after(
            0,
            self.append_log,
            f"[{track_index:02d}/{track_total:02d}] REVIEW - next track will continue",
        )
        return message

    def _worker(self, folder, files):
        install_v39_runtime()
        self._fullness_metadata = {}
        self._fullness_render_count = 0
        self._codec_preview_count = 0
        self._source_analyze_count = 0

        channel_key = normalize_channel_key(self.channel_var.get())
        genre_key = normalize_genre_key(self.genre_var.get())
        mastering_key = composite_key(channel_key, genre_key)
        channel = CHANNEL_PROFILES[channel_key]
        genre = GENRE_PROFILES[genre_key]
        mode = self.quality_var.get()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = folder / (
            f"MASTER_{channel_key}_{genre_key}_{'AUTO' if mode == 'QUALITY+' else 'FAST'}_{stamp}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        self.last_output_dir = out_dir

        gate_kwargs, auto_cfg, profile = v32._settings(mastering_key)
        resolved_maximum_auto_rerenders = (
            int(auto_cfg.get("maximumAutoRerenders", 2)) if mode == "QUALITY+" else 0
        )
        policy = build_track_retry_policy(
            mode=mode,
            resolved_maximum_auto_rerenders=resolved_maximum_auto_rerenders,
            max_fullness_render_passes=MAX_FULLNESS_RENDER_PASSES,
        )
        transparent_enabled = bool(auto_cfg.get("transparentFallbackEnabled", True)) and mode == "QUALITY+"
        codec_enabled = bool(auto_cfg.get("codecPreviewEnabled", True))
        codec_tolerance = float(auto_cfg.get("codecTruePeakSafetyMarginDb", 0.05))
        codec_step = float(auto_cfg.get("codecCeilingStepDb", 0.20))
        fullness_passes = policy.fullness_render_limit

        rows = []
        gate_results = []
        release_rows = []
        unresolved = []
        track_errors: list[tuple[str, str]] = []
        auto_fixed_count = 0
        codec_safe_count = 0
        total = len(files)
        original_tp = float(legacy.GENRES[mastering_key]["target_tp"])

        self.after(0, self.append_log, f"{DISPLAY_VERSION} CHANNEL + GENRE / FAST FULLNESS ENGINE")
        self.after(0, self.append_log, f"채널: {channel.label}")
        self.after(0, self.append_log, f"장르: {genre.label}")
        self.after(0, self.append_log, f"사운드: {'풍부함+' if self._fullness_mode() == 'RICH' else '자연스러움'} / 모드: {mode}")
        self.after(0, self.append_log, "[Settings]")
        self.after(0, self.append_log, f"maximumAutoRerenders = {resolved_maximum_auto_rerenders}")
        self.after(0, self.append_log, f"dynamicsBaseRerenders = {policy.dynamics_base_rerenders}")
        self.after(0, self.append_log, f"fullness_passes = {fullness_passes}")
        self.after(0, self.append_log, f"codecMaximumAutoRerenders = {policy.codec_maximum_auto_rerenders}")
        self.after(0, self.append_log, f"profile = {channel.label} + {genre.label}")
        self.after(0, self.append_log, "-" * 64)

        try:
            for idx, src in enumerate(files, 1):
                try:
                    track_start = time.perf_counter()
                    track_timing = TrackTiming()
                    self.after(0, self.append_log, f"[{idx:02d}/{total:02d}] {src.name}")

                    self._stage_status(idx, total, "analysis", src)
                    start = time.perf_counter()
                    source_ctx = self._source_context(src)
                    track_timing.analysis = time.perf_counter() - start
                    self._stage_log(idx, total, "analysis", track_timing.analysis)

                    raw_lra = legacy.safe_float(source_ctx.raw.get("input_lra"))
                    factor = legacy.adaptive_factor(raw_lra) if mode == "QUALITY+" else 1.0
                    current_tp = original_tp
                    dst = out_dir / final_output_name(src)
                    base = dst.with_name(f"{dst.stem}.v39_base.tmp.wav")
                    fixes: list[str] = []
                    codec_result = None
                    codec_error = ""
                    result = None
                    tail_repair = None
                    render_ok = False
                    render_err = ""
                    processing_mode = "normal"
                    candidate = None

                    counters = TrackCounters(
                        fullness_render_limit=policy.fullness_render_limit,
                        normal_quality_gate_limit=max(3, policy.quality_gate_transparent_limit),
                        codec_quality_gate_limit=max(1, policy.codec_maximum_auto_rerenders),
                    )
                    recommended_fullness_strength = None
                    base_ctx = None

                    legacy.GENRES[mastering_key]["target_tp"] = current_tp
                    self._stage_status(idx, total, "base mastering", src)
                    start = time.perf_counter()
                    render_ok, render_err = self._render_base(src, base, mastering_key, factor, mode)
                    counters.base_render_count += 1
                    base_seconds = time.perf_counter() - start
                    track_timing.base_mastering += base_seconds
                    self._stage_log(idx, total, "base mastering", base_seconds)

                    if render_ok and base.exists():
                        self._stage_status(idx, total, "Fullness analysis", src)
                        start = time.perf_counter()
                        base_ctx = self._audio_context(base)
                        analysis_seconds = time.perf_counter() - start
                        track_timing.fullness_analysis += analysis_seconds
                        self._stage_log(idx, total, "Fullness analysis", analysis_seconds)

                        base_dynamics = dynamics_stats(source_ctx.metrics, base_ctx.metrics, gate_kwargs)
                        if base_dynamics.risky:
                            self.after(0, self.append_log, "    Dynamics origin: Base")
                            self.after(
                                0,
                                self.append_log,
                                f"    Base LRA loss: {base_dynamics.lra_reduction_lu:.2f} LU / "
                                f"crest loss: {base_dynamics.crest_factor_loss_db:.2f} dB",
                            )

                        if base_dynamics.risky and transparent_enabled:
                            processing_mode = "transparent"
                            self.after(
                                0,
                                self.append_log,
                                "    Transparent fallback: base dynamics risk",
                            )
                            start = time.perf_counter()
                            render_ok, render_err = self._render_transparent_base(
                                src,
                                base,
                                mastering_key,
                                auto_cfg,
                            )
                            counters.transparent_render_count += 1
                            base_seconds = time.perf_counter() - start
                            track_timing.base_mastering += base_seconds
                            self._stage_log(idx, total, "transparent mastering", base_seconds)
                            if render_ok and base.exists():
                                _append_unique(fixes, "transparent mastering (dynamics fallback)")
                                start = time.perf_counter()
                                base_ctx = self._audio_context(base)
                                analysis_seconds = time.perf_counter() - start
                                track_timing.fullness_analysis += analysis_seconds
                                self._stage_log(idx, total, "transparent analysis", analysis_seconds)
                                candidate = self._finish_candidate(
                                    src,
                                    base,
                                    dst,
                                    mastering_key,
                                    gate_kwargs,
                                    auto_cfg,
                                    profile,
                                    source_ctx,
                                    base_ctx,
                                    fixes,
                                    counters,
                                    max_fullness_passes=1,
                                    track_index=idx,
                                    track_total=total,
                                    force_natural=True,
                                )
                                result = candidate.result
                                tail_repair = candidate.tail_repair
                                track_timing.fullness_render += candidate.timings.fullness_render
                                track_timing.quality_gate += candidate.timings.quality_gate
                        else:
                            if base_dynamics.risky:
                                processing_mode = "base_natural"
                                force_natural = True
                            else:
                                force_natural = False
                            candidate = self._finish_candidate(
                                src,
                                base,
                                dst,
                                mastering_key,
                                gate_kwargs,
                                auto_cfg,
                                profile,
                                source_ctx,
                                base_ctx,
                                fixes,
                                counters,
                                track_index=idx,
                                track_total=total,
                            max_fullness_passes=fullness_passes,
                            initial_strength=recommended_fullness_strength,
                            force_natural=force_natural,
                            )
                            result = candidate.result
                            tail_repair = candidate.tail_repair
                            track_timing.fullness_render += candidate.timings.fullness_render
                            track_timing.quality_gate += candidate.timings.quality_gate
                            recommended_fullness_strength = candidate.recommended_fullness_strength

                    if (
                        render_ok
                        and result is not None
                        and _has_issue(result, "DYNAMICS RISK")
                        and transparent_enabled
                        and processing_mode != "transparent"
                    ):
                        processing_mode = "transparent"
                        self.after(0, self.append_log, "    Transparent fallback: final dynamics risk")
                        start = time.perf_counter()
                        render_ok, render_err = self._render_transparent_base(src, base, mastering_key, auto_cfg)
                        counters.transparent_render_count += 1
                        base_seconds = time.perf_counter() - start
                        track_timing.base_mastering += base_seconds
                        self._stage_log(idx, total, "transparent mastering", base_seconds)
                        if render_ok and base.exists():
                            _append_unique(fixes, "transparent mastering (dynamics fallback)")
                            start = time.perf_counter()
                            base_ctx = self._audio_context(base)
                            analysis_seconds = time.perf_counter() - start
                            track_timing.fullness_analysis += analysis_seconds
                            self._stage_log(idx, total, "transparent analysis", analysis_seconds)
                            candidate = self._finish_candidate(
                                src,
                                base,
                                dst,
                                mastering_key,
                                gate_kwargs,
                                auto_cfg,
                                profile,
                                source_ctx,
                                base_ctx,
                                fixes,
                                counters,
                                max_fullness_passes=1,
                                track_index=idx,
                                track_total=total,
                                force_natural=True,
                            )
                            result = candidate.result
                            tail_repair = candidate.tail_repair
                            track_timing.fullness_render += candidate.timings.fullness_render
                            track_timing.quality_gate += candidate.timings.quality_gate
                    if render_ok and result is not None and result.status == "PASS" and codec_enabled:
                        self._stage_status(idx, total, "codec safety check", src)
                        codec_attempt_limit = policy.codec_maximum_auto_rerenders if mode == "QUALITY+" else 0
                        for codec_attempt in range(codec_attempt_limit + 1):
                            start = time.perf_counter()
                            try:
                                codec_result = v32.check_codec_safety(
                                    dst,
                                    true_peak_ceiling_dbtp=float(profile["truePeakCeilingDbtp"]),
                                    tolerance_db=codec_tolerance,
                                    ffmpeg=self.ffmpeg,
                                )
                                codec_error = ""
                            except Exception as exc:
                                codec_result = None
                                codec_error = f"codec verification failed: {exc}"
                                track_timing.codec_preview += time.perf_counter() - start
                                self._codec_preview_count += 1
                                counters.codec_check_count += 1
                                break
                            track_timing.codec_preview += time.perf_counter() - start
                            self._codec_preview_count += 1
                            counters.codec_check_count += 1
                            if codec_result.safe:
                                break
                            if codec_attempt >= codec_attempt_limit:
                                break
                            current_tp -= codec_step
                            legacy.GENRES[mastering_key]["target_tp"] = current_tp
                            _append_unique(fixes, f"코덱 피크 보호 ceiling {current_tp:.2f} dBTP")
                            self.after(0, self.append_log, f"    ↻ AAC/MP3 피크 보호 재마스터 {codec_attempt + 1}/{codec_attempt_limit}")
                            start = time.perf_counter()
                            counters.codec_ceiling_rerender_count += 1
                            if processing_mode == "transparent":
                                render_ok, render_err = self._render_transparent_base(src, base, mastering_key, auto_cfg)
                                counters.transparent_render_count += 1
                            else:
                                render_ok, render_err = self._render_base(src, base, mastering_key, factor, mode)
                            base_seconds = time.perf_counter() - start
                            track_timing.base_mastering += base_seconds
                            self._stage_log(idx, total, "codec ceiling rerender", base_seconds)
                            if not render_ok or not base.exists():
                                break
                            start = time.perf_counter()
                            base_ctx = self._audio_context(base)
                            analysis_seconds = time.perf_counter() - start
                            track_timing.fullness_analysis += analysis_seconds
                            self._stage_log(idx, total, "codec rerender analysis", analysis_seconds)
                            result, tail_repair, codec_timing = self._reapply_accepted_candidate(
                                src,
                                base,
                                dst,
                                mastering_key,
                                gate_kwargs,
                                auto_cfg,
                                profile,
                                source_ctx,
                                base_ctx,
                                fixes,
                                counters,
                                track_index=idx,
                                track_total=total,
                            )
                            track_timing.fullness_render += codec_timing.fullness_render
                            track_timing.quality_gate += codec_timing.quality_gate
                            if result is None or result.status != "PASS":
                                break
                        self._stage_log(idx, total, "Codec Preview", track_timing.codec_preview)

                    legacy.GENRES[mastering_key]["target_tp"] = original_tp

                    if not render_ok or result is None:
                        status = "FAIL"
                        notes = "마스터링 처리 실패"
                        unresolved.append((src.name, [notes]))
                        (out_dir / f"ERROR_{src.stem}.txt").write_text(
                            (render_err or "")[-5000:],
                            encoding="utf-8",
                            errors="ignore",
                        )
                    else:
                        codec_safe = codec_result.safe if codec_result is not None else (not codec_enabled)
                        if result.status == "PASS" and codec_error:
                            status = "FAIL"
                            notes = codec_error
                            result = replace(result, status="FAIL", issues=result.issues + (notes,))
                            unresolved.append((src.name, [notes]))
                        elif result.status == "PASS" and not codec_safe:
                            status = "FAIL"
                            notes = f"codec peak unsafe: {codec_result.maximum_true_peak_dbtp:.2f} dBTP"
                            result = replace(result, status="FAIL", issues=result.issues + (notes,))
                            unresolved.append((src.name, [notes]))
                        else:
                            status = result.status
                            notes = " / ".join(list(result.issues) + list(result.warnings))
                            if status != "PASS":
                                unresolved.append((src.name, list(result.issues) + list(result.warnings)))

                        if codec_result is not None and codec_result.safe:
                            codec_safe_count += 1
                        gate_results.append((src.name, result))

                    if fixes and status == "PASS":
                        auto_fixed_count += 1
                    release_rows.append((dst, status))
                    final = result.processed if result is not None else None
                    rows.append(
                        {
                            "track": src.name,
                            "status": status,
                            "channel_profile": channel.label,
                            "music_genre": genre.label,
                            "mastering_profile": legacy.GENRES[mastering_key]["label"],
                            "source_LUFS": source_ctx.raw.get("input_i", ""),
                            "source_dBTP": source_ctx.raw.get("input_tp", ""),
                            "source_LRA": source_ctx.raw.get("input_lra", ""),
                            "target_LUFS": legacy.GENRES[mastering_key]["target_i"],
                            "final_LUFS": _format_metric(final.lufs_i) if final else "",
                            "final_dBTP": _format_metric(final.true_peak_dbtp) if final else "",
                            "processing_mode": processing_mode,
                            "adaptive_factor": f"{factor:.2f}",
                            "auto_fixes": " / ".join(fixes),
                            "tail_before_RMS": (
                                f"{tail_repair.before.end_rms_dbfs:.2f}" if tail_repair is not None else ""
                            ),
                            "tail_fix_mode": tail_repair.mode if tail_repair is not None else "",
                            "tail_after_RMS": (
                                f"{tail_repair.after.end_rms_dbfs:.2f}" if tail_repair is not None else ""
                            ),
                            "codec_max_dBTP": (
                                f"{codec_result.maximum_true_peak_dbtp:.2f}" if codec_result is not None else ""
                            ),
                            "stage_analysis_sec": f"{track_timing.analysis:.1f}",
                            "stage_base_mastering_sec": f"{track_timing.base_mastering:.1f}",
                            "stage_fullness_analysis_sec": f"{track_timing.fullness_analysis:.1f}",
                            "stage_fullness_render_sec": f"{track_timing.fullness_render:.1f}",
                            "stage_quality_gate_sec": f"{track_timing.quality_gate:.1f}",
                            "stage_codec_preview_sec": f"{track_timing.codec_preview:.1f}",
                            "base_render_count": str(counters.base_render_count),
                            "transparent_render_count": str(counters.transparent_render_count),
                            "codec_ceiling_rerender_count": str(counters.codec_ceiling_rerender_count),
                            "fullness_render_count": str(counters.fullness_render_count),
                            "quality_gate_count": str(counters.quality_gate_count),
                            "normal_quality_gate_count": str(counters.normal_quality_gate_count),
                            "codec_final_quality_gate_count": str(counters.codec_quality_gate_count),
                            "codec_sound_reapply_count": str(counters.codec_sound_reapply_count),
                            "codec_check_count": str(counters.codec_check_count),
                            "notes": notes,
                        }
                    )
                    track_timing.total = time.perf_counter() - track_start
                    self.after(
                        0,
                        self.append_log,
                        f"    Fullness renders: {counters.fullness_render_count}",
                    )
                    self.after(
                        0,
                        self.append_log,
                        f"    Base renders: {counters.base_render_count}",
                    )
                    self.after(
                        0,
                        self.append_log,
                        f"    Transparent renders: {counters.transparent_render_count}",
                    )
                    self.after(
                        0,
                        self.append_log,
                        f"    Codec ceiling rerenders: {counters.codec_ceiling_rerender_count}",
                    )
                    self.after(
                        0,
                        self.append_log,
                        f"    Normal QG calls: {counters.normal_quality_gate_count}",
                    )
                    self.after(
                        0,
                        self.append_log,
                        f"    Codec final QG calls: {counters.codec_quality_gate_count}",
                    )
                    self.after(
                        0,
                        self.append_log,
                        f"    Quality Gate calls: {counters.quality_gate_count}",
                    )
                    self.after(
                        0,
                        self.append_log,
                        f"    Codec sound reapplies: {counters.codec_sound_reapply_count}",
                    )
                    self.after(
                        0,
                        self.append_log,
                        f"    Codec checks: {counters.codec_check_count}",
                    )
                    perf_level = performance_level(track_timing.total)
                    if perf_level:
                        slow_name, slow_seconds = slowest_stage(
                            {
                                "analysis": track_timing.analysis,
                                "base mastering": track_timing.base_mastering,
                                "Fullness analysis": track_timing.fullness_analysis,
                                "Fullness render": track_timing.fullness_render,
                                "Quality Gate": track_timing.quality_gate,
                                "Codec Preview": track_timing.codec_preview,
                            }
                        )
                        label = "성능 오류" if perf_level == "error" else "성능 경고"
                        limit_seconds = 240 if perf_level == "error" else 120
                        self.after(
                            0,
                            self.append_log,
                            f"[{label}] {idx:02d}번 곡 처리 시간이 {limit_seconds}초를 "
                            f"초과했습니다. 실제: {track_timing.total:.1f}초",
                        )
                        self.after(
                            0,
                            self.append_log,
                            f"    가장 느린 단계: {slow_name} {slow_seconds:.1f} sec",
                        )
                    self.after(0, self.append_log, f"[{idx:02d}/{total:02d}] 완료: {track_timing.total:.1f} sec")
                    icon = "PASS" if status == "PASS" else "REVIEW"
                    fix_text = f" | 자동수정: {', '.join(fixes)}" if fixes else ""
                    self.after(0, self.append_log, f"    -> {icon}{fix_text}")
                    self.after(0, self.progress_var.set, idx / total * 100)
                    self.after(0, self.status_var.set, f"{idx:02d}/{total:02d} 완료 - {track_timing.total:.0f}초")
                    try:
                        if base.exists():
                            base.unlink()
                    except OSError:
                        pass
                except (SystemExit, KeyboardInterrupt):
                    raise
                except Exception as exc:
                    message = self._record_track_error(idx, total, src, out_dir, exc)
                    unresolved.append((src.name, [message]))
                    track_errors.append((src.name, message))
        finally:
            legacy.GENRES[mastering_key]["target_tp"] = original_tp

        for track_name, message in track_errors:
            error_row = {field: "" for field in TRACK_REPORT_FIELDS}
            error_row.update(
                {
                    "track": track_name,
                    "status": "REVIEW",
                    "channel_profile": channel.label,
                    "music_genre": genre.label,
                    "mastering_profile": legacy.GENRES[mastering_key]["label"],
                    "notes": message,
                }
            )
            rows.append(error_row)

        if rows:
            with open(out_dir / "mastering_report.csv", "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(TRACK_REPORT_FIELDS))
                writer.writeheader()
                writer.writerows(rows)

        if gate_results:
            json_path, html_path = write_quality_reports(out_dir, gate_results)
        else:
            json_path = html_path = None

        result_sections = []
        if unresolved:
            for name, issues in unresolved:
                result_sections.append(
                    _automatic_limit_text(name, issues, legacy.GENRES[mastering_key]["label"])
                )
        else:
            result_sections.append(
                f"모든 곡이 v{VERSION} 자동검사와 자동수정을 통과했습니다. 수동 Studio 보완은 필요하지 않습니다."
            )
        auto_result_path = out_dir / "자동해결_결과.txt"
        auto_result_path.write_text("\n\n".join(result_sections), encoding="utf-8")
        compatibility_path = out_dir / "STUDIO_문제곡_보완_프롬프트.txt"
        compatibility_path.write_text("\n\n".join(result_sections), encoding="utf-8")

        paths = organize_release_files(out_dir, release_rows)
        for report_file in [
            out_dir / "mastering_report.csv",
            auto_result_path,
            compatibility_path,
            json_path,
            html_path,
        ]:
            if report_file and Path(report_file).exists():
                shutil.copy2(report_file, paths["report"] / Path(report_file).name)

        self._refresh_v39_reports(out_dir)

        pass_count = sum(row["status"] == "PASS" for row in rows)
        review_count = len(rows) - pass_count
        beginner = write_beginner_summary(
            out_dir,
            pass_count=pass_count,
            review_count=review_count,
            auto_fixed_count=auto_fixed_count,
            codec_safe_count=codec_safe_count,
            total_count=len(rows),
        )
        self.last_check_items = unresolved

        if review_count == 0:
            summary = (
                f"자동완성 완료: {len(rows)}곡 전부 배포 가능\n"
                f"자동 수정 완료 {auto_fixed_count}곡 / 코덱 안전 {codec_safe_count}곡\n"
                f"Fullness render {self._fullness_render_count}회 / Codec Preview {self._codec_preview_count}회\n"
                f"사용할 폴더: {paths['release']}"
            )
            title = "v3.9 자동완성 - 배포 가능"
        else:
            summary = (
                f"자동완성 완료: PASS {pass_count} / 배포 보류 {review_count}\n"
                f"Fullness render {self._fullness_render_count}회 / Codec Preview {self._codec_preview_count}회\n"
                f"안전한 파일: {paths['release']}\n"
                f"보류 파일: {paths['review']}\n"
                f"최종 판정: {beginner}"
            )
            title = "v3.9 자동완성 - 일부 배포 보류"

        self.after(0, self.append_log, "-" * 64)
        self.after(0, self.append_log, summary)
        self.after(0, self.status_var.set, f"완료 - PASS {pass_count} / 보류 {review_count}")
        self.after(0, self.start_btn.config, {"state": "normal"})
        self.after(0, lambda: legacy.messagebox.showinfo(title, summary))


if __name__ == "__main__":
    AppV39().mainloop()
