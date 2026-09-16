# -*- coding: utf-8 -*-
"""HARU Mastering v3.8 - Fullness Engine."""
from __future__ import annotations

import csv
import math
import re
import shutil
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V372_PATH = ROOT / "Suno15_Mastering_v3_7_2.pyw"


def _load_v372():
    loader = SourceFileLoader("suno15_v372", str(V372_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v3.7.2 program cannot be loaded: {V372_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v372 = _load_v372()
v371 = v372.v371
v37 = v371.v37
v32 = v37.v32
v2 = v37.v2
legacy = v37.legacy

from haru_mastering.codec_preview import check_codec_safety
from haru_mastering.fullness import (
    FULLNESS_STRENGTH_STEPS,
    FullnessDecision,
    default_fullness_mode,
    decide as decide_fullness,
    process as process_fullness,
)
from haru_mastering.quality_gate import evaluate_master
from haru_mastering.version import APP_TITLE, DISPLAY_VERSION, REPORT_VERSION, VERSION
import haru_mastering.report as report_module


APP_NAME = APP_TITLE
SYNC_VERSION = REPORT_VERSION
LOUDNESS_TOLERANCE_LU = float(v372.LOUDNESS_TOLERANCE_LU)


class FullnessCsvRow:
    def __init__(
        self,
        *,
        mode: str = "NATURAL",
        strength_percent: int = 0,
        warmth_gain_db: float = 0.0,
        body_gain_db: float = 0.0,
        saturation_wet_percent: float = 0.0,
        density_wet_percent: float = 0.0,
        auto_reduced: bool = False,
        retry_count: int = 0,
        bypassed_reason: str = "",
    ) -> None:
        self.mode = mode
        self.strength_percent = strength_percent
        self.warmth_gain_db = warmth_gain_db
        self.body_gain_db = body_gain_db
        self.saturation_wet_percent = saturation_wet_percent
        self.density_wet_percent = density_wet_percent
        self.auto_reduced = auto_reduced
        self.retry_count = retry_count
        self.bypassed_reason = bypassed_reason

    def as_csv(self) -> dict[str, str]:
        return {
            "app_version": REPORT_VERSION,
            "fullness_mode": self.mode,
            "fullness_strength_percent": str(int(self.strength_percent)),
            "warmth_gain_db": f"{self.warmth_gain_db:+.2f}",
            "body_gain_db": f"{self.body_gain_db:+.2f}",
            "saturation_wet_percent": f"{self.saturation_wet_percent:.1f}",
            "density_wet_percent": f"{self.density_wet_percent:.1f}",
            "fullness_auto_reduced": "true" if self.auto_reduced else "false",
            "fullness_retry_count": str(int(self.retry_count)),
            "fullness_bypassed_reason": self.bypassed_reason,
        }


def install_v38_runtime() -> None:
    v372.install_v372_sync()
    report_module.QUALITY_REPORT_VERSION = REPORT_VERSION


install_v38_runtime()


def _format_metric(value: float) -> str:
    number = float(value)
    return f"{number:.2f}" if math.isfinite(number) else "-inf"


def _safe_float(value, default=None):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _csv_additions() -> tuple[str, ...]:
    return (
        "app_version",
        "final_metrics_sync_version",
        "fullness_mode",
        "fullness_strength_percent",
        "warmth_gain_db",
        "body_gain_db",
        "saturation_wet_percent",
        "density_wet_percent",
        "fullness_auto_reduced",
        "fullness_retry_count",
        "fullness_bypassed_reason",
    )


def _copy_report_csv(output: Path, csv_path: Path) -> None:
    report_copy = output / "03_REPORT" / csv_path.name
    report_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(csv_path, report_copy)


_VERSION_PATTERN = re.compile(r"v3\.(?:8\.1|8|7\.2|7\.1|7|6\.1|6|5|4|3|2)(?![\d.])")


def _refresh_completion_text_files_v38(output_dir: str | Path) -> int:
    output = Path(output_dir)
    changed = 0
    for path in output.rglob("*.txt"):
        if not path.is_file():
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            original = path.read_text(encoding="utf-8-sig")
        updated = _VERSION_PATTERN.sub(REPORT_VERSION, original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def patch_csv_with_fullness(output_dir: str | Path, metadata: dict[str, FullnessCsvRow] | None = None) -> int:
    output = Path(output_dir)
    csv_path = output / "mastering_report.csv"
    if not csv_path.exists():
        return 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for name in _csv_additions():
        if name not in fieldnames:
            fieldnames.append(name)

    changed = 0
    metadata = metadata or {}
    for row in rows:
        track = (row.get("track") or "").strip()
        entry = metadata.get(track)
        if entry is not None:
            row.update(entry.as_csv())
        else:
            defaults = FullnessCsvRow().as_csv()
            for name, value in defaults.items():
                if not str(row.get(name) or "").strip():
                    row[name] = value
        if not str(row.get("final_metrics_sync_version") or "").strip():
            row["final_metrics_sync_version"] = REPORT_VERSION
        changed += 1

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    _copy_report_csv(output, csv_path)
    return changed


def _refresh_final_metrics_csv_v38(output_dir: str | Path) -> int:
    refreshed = v372._refresh_final_metrics_csv_v372(output_dir)
    patch_csv_with_fullness(output_dir)
    return refreshed


def _guard_reasons(result, *, codec_result=None) -> list[str]:
    reasons = list(result.issues)
    if codec_result is not None and not codec_result.safe:
        reasons.append(f"codec preview unsafe: {codec_result.maximum_true_peak_dbtp:.2f} dBTP")
    return reasons


class AppV38(v372.AppV372):
    def _build_ui(self):
        self.sound_var = legacy.tk.StringVar(value="RICH")
        self.fullness_status_var = legacy.tk.StringVar()
        self._fullness_metadata: dict[str, FullnessCsvRow] = {}
        super()._build_ui()

    def __init__(self):
        install_v38_runtime()
        super().__init__()
        self.title(APP_NAME)
        self.status_var.set(
            f"{DISPLAY_VERSION} 준비 - Fullness Engine / 실행 파일: {Path(__file__).resolve()}"
        )
        self.after(0, self._update_genre_description)

    def append_log(self, text):
        value = str(text)
        for old in ("v3.8", "v3.7.2", "v3.7.1", "v3.7", "v3.6.1", "v3.6", "v3.5", "v3.4", "v3.3", "v3.2"):
            value = re.sub(rf"{re.escape(old)}(?![\d.])", f"v{VERSION}", value)
        return super().append_log(value)

    def _select_genre(self, key: str) -> None:
        super()._select_genre(key)
        if hasattr(self, "sound_var"):
            self.sound_var.set(default_fullness_mode(key))
        self._update_genre_description()

    def _on_sound_mode_changed(self):
        self._update_genre_description()

    def _update_genre_description(self) -> None:
        if not hasattr(self, "genre_description_var"):
            return
        key = self.genre_var.get()
        if key not in legacy.GENRES:
            return
        g = legacy.GENRES[key]
        sound = "풍부함+ (추천)" if getattr(self, "sound_var", None) and self.sound_var.get() == "RICH" else "자연스러움"
        message = (
            f"선택: {g['label']}  [{key}]\n"
            f"목표: {g['target_i']:.1f} LUFS / {g['target_tp']:.1f} dBTP / LRA {g['target_lra']:g}\n"
            f"사운드: {sound}\n"
            "Warmth / Harmonic / Density를 자동 분석 후 필요한 만큼만 적용"
        )
        self.genre_description_var.set(message)
        if hasattr(self, "fullness_status_var"):
            self.fullness_status_var.set(f"{DISPLAY_VERSION} / 실행 파일: {Path(__file__).resolve()}")

    def _build_master_tab(self):
        ttk = legacy.ttk

        frame = ttk.LabelFrame(self.master_tab, text="1. Suno Studio에서 내보낸 15곡 폴더")
        frame.pack(fill="x", padx=14, pady=(14, 8))
        row = ttk.Frame(frame)
        row.pack(fill="x", padx=10, pady=10)
        ttk.Entry(row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="폴더 선택", command=self.choose_folder).pack(side="left", padx=(8, 0))

        gframe = ttk.LabelFrame(self.master_tab, text="2. 장르 선택 - 빠른 선택 또는 전체 장르")
        gframe.pack(fill="x", padx=14, pady=8)

        quick = ttk.Frame(gframe)
        quick.pack(fill="x", padx=10, pady=(8, 3))
        ttk.Label(quick, text="자주 쓰는 장르", font=("Malgun Gothic", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(4, 12), pady=4
        )
        for index, key in enumerate(v37.QUICK_GENRES):
            ttk.Radiobutton(
                quick,
                text=legacy.GENRES[key]["label"],
                variable=self.genre_var,
                value=key,
                command=lambda selected=key: self._select_genre(selected),
            ).grid(row=0, column=index + 1, sticky="w", padx=8, pady=4)

        all_row = ttk.Frame(gframe)
        all_row.pack(fill="x", padx=10, pady=4)
        ttk.Label(all_row, text=f"전체 장르 {len(v37.GENRE_DISPLAY_ORDER)}개").pack(side="left", padx=(4, 10))
        displays = [self._genre_display(key) for key in v37.GENRE_DISPLAY_ORDER]
        self._genre_display_to_key = dict(zip(displays, v37.GENRE_DISPLAY_ORDER))
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
            text="빠른 마스터 - 급할 때",
            variable=self.quality_var,
            value="FAST",
        ).pack(anchor="w", pady=3)
        ttk.Radiobutton(
            qinner,
            text="품질+ (추천) - 곡별 분석 + Adaptive Compression + 2-pass Loudness + 최종 검증",
            variable=self.quality_var,
            value="QUALITY+",
        ).pack(anchor="w", pady=3)

        sframe = ttk.LabelFrame(self.master_tab, text="4. 사운드 성향")
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
            text="진행 / 결과 - PASS / NEEDS_REVIEW만 확인하면 됩니다",
        )
        lframe.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.log = legacy.tk.Text(lframe, height=10, wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.log.insert("end", "추천: OLD POP, 한국 시니어, 일본 시니어, SHOWA, BALLAD는 풍부함+ 기본값입니다.\n")
        self.log.insert("end", f"{DISPLAY_VERSION} - 실행 파일: {Path(__file__).resolve()}\n")
        if not self.ffmpeg:
            self.log.insert("end", "[주의] FFmpeg가 없습니다. INSTALL.bat을 먼저 실행하세요.\n")

    def _fullness_mode(self, genre: str) -> str:
        if hasattr(self, "sound_var"):
            return self.sound_var.get()
        return default_fullness_mode(genre)

    def _metadata_from_decision(
        self,
        decision: FullnessDecision,
        *,
        retry_count: int,
        auto_reduced: bool,
        bypassed_reason: str,
    ) -> FullnessCsvRow:
        return FullnessCsvRow(
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

    def _fullness_guard_passes(self, src: Path, dst: Path, genre: str, auto_cfg: dict, profile: dict):
        gate_kwargs, _, _ = v32._settings(genre)
        result = evaluate_master(src, dst, **gate_kwargs)
        codec_result = None
        if result.status == "PASS" and bool(auto_cfg.get("codecPreviewEnabled", True)):
            codec_result = check_codec_safety(
                dst,
                true_peak_ceiling_dbtp=float(profile["truePeakCeilingDbtp"]),
                tolerance_db=float(auto_cfg.get("codecTruePeakSafetyMarginDb", 0.05)),
                ffmpeg=self.ffmpeg,
            )
        reasons = _guard_reasons(result, codec_result=codec_result)
        return not reasons, reasons

    def _apply_fullness_with_guard(self, src: Path, base: Path, dst: Path, genre: str) -> tuple[bool, str]:
        mode = self._fullness_mode(genre)
        _, auto_cfg, profile = v32._settings(genre)
        last_reasons: list[str] = []
        track = src.name

        if mode != "RICH":
            shutil.copy2(base, dst)
            decision = decide_fullness(v372.analyze_file(dst), genre_key=genre, mode="NATURAL")
            self._fullness_metadata[track] = self._metadata_from_decision(
                decision,
                retry_count=0,
                auto_reduced=False,
                bypassed_reason="natural_mode",
            )
            return True, ""

        for retry_count, strength in enumerate(FULLNESS_STRENGTH_STEPS):
            metrics = v372.analyze_file(base)
            decision = decide_fullness(
                metrics,
                genre_key=genre,
                mode="RICH" if strength else "NATURAL",
                strength_percent=strength,
                profile=profile,
            )
            render = process_fullness(base, dst, decision)
            if strength == 0:
                reason = " / ".join(last_reasons) if last_reasons else "guard_reduced_to_off"
                self._fullness_metadata[track] = self._metadata_from_decision(
                    decision,
                    retry_count=retry_count,
                    auto_reduced=retry_count > 0,
                    bypassed_reason=reason,
                )
                return True, ""

            passes, reasons = self._fullness_guard_passes(src, dst, genre, auto_cfg, profile)
            if passes:
                self._fullness_metadata[track] = self._metadata_from_decision(
                    render.decision,
                    retry_count=retry_count,
                    auto_reduced=retry_count > 0,
                    bypassed_reason="",
                )
                return True, ""
            last_reasons = reasons
            self.after(
                0,
                self.append_log,
                f"    Fullness guard: {strength}% -> reduce ({' / '.join(reasons)[:160]})",
            )
        return False, "Fullness guard did not produce a safe candidate"

    def _render_quality(self, src: Path, dst: Path, genre: str, factor: float):
        base = dst.with_name(f"{dst.stem}.v38_base.tmp.wav")
        try:
            ok, err = super()._render_quality(src, base, genre, factor)
            if not ok or not base.exists():
                return ok, err
            return self._apply_fullness_with_guard(src, base, dst, genre)
        finally:
            try:
                if base.exists():
                    base.unlink()
            except OSError:
                pass

    def _render_transparent(self, src: Path, dst: Path, genre: str, *, highpass_hz: float):
        ok, err = super()._render_transparent(src, dst, genre, highpass_hz=highpass_hz)
        if ok:
            decision = decide_fullness(v372.analyze_file(dst), genre_key=genre, mode="NATURAL")
            self._fullness_metadata[src.name] = self._metadata_from_decision(
                decision,
                retry_count=0,
                auto_reduced=False,
                bypassed_reason="transparent_fallback",
            )
        return ok, err

    def _worker(self, folder, files):
        install_v38_runtime()
        self._fullness_metadata = {}
        self.after(0, self.append_log, f"{DISPLAY_VERSION} Fullness Engine active")
        super()._worker(folder, files)
        output_dir = Path(self.last_output_dir)
        patched = patch_csv_with_fullness(output_dir, self._fullness_metadata)
        text_files = _refresh_completion_text_files_v38(output_dir)
        self.after(
            0,
            self.append_log,
            f"v{VERSION} Fullness CSV/TXT synchronized: {patched} tracks / {text_files} text files",
        )


if __name__ == "__main__":
    AppV38().mainloop()
