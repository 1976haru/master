# -*- coding: utf-8 -*-
"""HARU / SUNO 15-SET MASTERING v3 runtime.

v2 채널 마스터링을 그대로 보존하면서 다음을 추가한다.
- 15곡 완료 후 자동 file-level Quality Gate + HTML/JSON report
- 선택적 noisereduce / DeepFilterNet / audio-separator 실행
- GPL 코드 없이 자체 bounded Reference Assist
- AAC 256 / MP3 320 codec roundtrip preview

기본 마스터링은 AI 도구가 설치되지 않아도 정상 동작한다.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V2_PATH = ROOT / "Suno15_Mastering_v2.pyw"


def _load_v2():
    loader = SourceFileLoader("suno15_v2", str(V2_PATH))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"v2 프로그램을 불러올 수 없습니다: {V2_PATH}")
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


v2 = _load_v2()
v2.patch_runtime()
legacy = v2.legacy

from haru_mastering.analysis import analyze_file
from haru_mastering.codec_preview import create_codec_previews
from haru_mastering.profiles import load_profiles
from haru_mastering.quality_gate import evaluate_master
from haru_mastering.reference import build_reference_plan, ffmpeg_equalizer_chain
from haru_mastering.repair import (
    detect_optional_tools,
    reduce_noise_file,
    run_audio_separator,
    run_deepfilternet,
)
from haru_mastering.report import write_quality_reports


APP_NAME = "HARU / SUNO 15-SET MASTERING v3.0 - Repair + Quality Gate"


def _profile_payload():
    return load_profiles(v2.PROFILE_PATH)


def _gate_kwargs(genre_key: str) -> dict:
    payload = _profile_payload()
    profile = v2.get_profile(genre_key)
    global_cfg = payload["global"]
    gate = global_cfg["qualityGate"]
    return {
        "target_lufs_i": float(profile["targetLufsI"]),
        "true_peak_ceiling_dbtp": float(profile["truePeakCeilingDbtp"]),
        "lufs_tolerance_lu": float(gate["lufsToleranceLu"]),
        "true_peak_tolerance_db": float(gate["truePeakToleranceDb"]),
        "maximum_clipped_samples": int(gate["maximumClippedSamples"]),
        "maximum_residual_delay_samples": int(gate["maximumResidualDelaySamples"]),
        "maximum_dc_offset": float(gate["maximumDcOffset"]),
        "minimum_stereo_correlation": float(gate["minimumFullBandStereoCorrelation"]),
        "minimum_low_band_stereo_correlation": float(gate["minimumLowBandStereoCorrelation"]),
        "low_band_cutoff_hz": float(global_cfg["bassMonoBelowHz"]),
        "expected_output_sample_rate_hz": int(global_cfg["workingSampleRateHz"]),
        "reject_on_duration_loss": bool(gate["rejectOnUnexpectedDurationLoss"]),
        "max_delay_ms": float(global_cfg["latencyDetectionMaxMs"]),
        "true_peak_oversample": int(global_cfg["truePeakOversampleFactor"]),
    }


class AppV3(legacy.App):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.advanced_source_var = legacy.tk.StringVar()
        self.advanced_reference_var = legacy.tk.StringVar()
        self.advanced_master_var = legacy.tk.StringVar()
        self.advanced_status_var = legacy.tk.StringVar(value="고급 기능 준비")
        self._build_advanced_tab()

    def _worker(self, folder, files):
        # v2 rendering path is kept intact; v3 adds a strict post-render gate.
        super()._worker(folder, files)
        try:
            self._quality_gate_batch(files)
        except Exception as exc:
            self.after(0, self.append_log, f"[v3 Quality Gate ERROR] {exc}")
            self.after(0, self.status_var.set, "마스터링 완료 / v3 품질검사 오류 확인 필요")

    def _quality_gate_batch(self, files):
        if not self.last_output_dir:
            return
        genre = self.genre_var.get()
        kwargs = _gate_kwargs(genre)
        results = []
        for src in files:
            dst = Path(self.last_output_dir) / f"{src.stem}_MASTER.wav"
            if not dst.exists():
                continue
            result = evaluate_master(src, dst, **kwargs)
            results.append((src.name, result))

        if not results:
            return
        json_path, html_path = write_quality_reports(self.last_output_dir, results)
        pass_count = sum(result.status == "PASS" for _, result in results)
        warn_count = sum(result.status == "WARN" for _, result in results)
        fail_count = sum(result.status == "FAIL" for _, result in results)
        message = (
            f"v3 Quality Gate: PASS {pass_count} / WARN {warn_count} / FAIL {fail_count}"
            f" | report: {html_path.name}"
        )
        self.after(0, self.append_log, message)
        self.after(0, self.status_var.set, message)
        if fail_count:
            self.after(
                0,
                lambda: legacy.messagebox.showwarning(
                    "v3 품질검사",
                    f"FAIL {fail_count}곡이 있습니다.\n{html_path}\n\n"
                    "FAIL 곡은 바로 배포하지 말고 리포트를 확인하세요.",
                ),
            )

    def _build_advanced_tab(self):
        self.advanced_tab = legacy.ttk.Frame(self.notebook)
        self.notebook.add(self.advanced_tab, text="⑤ 고급 복원 / 품질검사")

        intro = legacy.ttk.LabelFrame(self.advanced_tab, text="선택 기능 — 정상곡에는 사용하지 않는 것이 원칙")
        intro.pack(fill="x", padx=14, pady=(14, 8))
        legacy.ttk.Label(
            intro,
            text=(
                "기본 마스터링은 그대로 두고 실제 문제가 있는 파일에만 복원 기능을 사용합니다. "
                "AI 도구가 없어도 분석/Quality Gate/Reference Assist/Codec Preview는 동작합니다."
            ),
            wraplength=850,
            justify="left",
            font=("Malgun Gothic", 10, "bold"),
        ).pack(anchor="w", padx=12, pady=10)

        files = legacy.ttk.LabelFrame(self.advanced_tab, text="파일")
        files.pack(fill="x", padx=14, pady=8)
        self._file_row(files, "작업 파일", self.advanced_source_var, self._choose_advanced_source, 0)
        self._file_row(files, "참조 파일", self.advanced_reference_var, self._choose_reference, 1)
        self._file_row(files, "비교 마스터", self.advanced_master_var, self._choose_master, 2)

        actions = legacy.ttk.LabelFrame(self.advanced_tab, text="고급 기능")
        actions.pack(fill="x", padx=14, pady=8)
        buttons = [
            ("파일 정밀 분석", self.analyze_advanced_source),
            ("약한 Noise Repair", self.noise_repair),
            ("DeepFilterNet 복원", self.deepfilter_repair),
            ("Vocal / Instrument Stem", self.separate_stems),
            ("Reference Assist 적용", self.reference_assist),
            ("AAC/MP3 Codec Preview", self.codec_preview),
            ("원본 ↔ 마스터 Quality Gate", self.manual_quality_gate),
            ("옵션 AI 도구 설치", self.install_ai_tools),
        ]
        for index, (label, command) in enumerate(buttons):
            legacy.ttk.Button(actions, text=label, command=command).grid(
                row=index // 2, column=index % 2, sticky="ew", padx=6, pady=5, ipady=4
            )
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        legacy.ttk.Label(
            self.advanced_tab,
            textvariable=self.advanced_status_var,
            font=("Malgun Gothic", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(4, 4))
        result = legacy.ttk.LabelFrame(self.advanced_tab, text="결과")
        result.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.advanced_log = legacy.tk.Text(result, height=16, wrap="word", font=("Consolas", 9))
        self.advanced_log.pack(fill="both", expand=True, padx=8, pady=8)
        self._show_tool_status()

    def _file_row(self, parent, label, variable, command, row):
        legacy.ttk.Label(parent, text=label, width=12).grid(row=row, column=0, padx=(10, 4), pady=5, sticky="w")
        legacy.ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, padx=4, pady=5, sticky="ew")
        legacy.ttk.Button(parent, text="선택", command=command).grid(row=row, column=2, padx=(4, 10), pady=5)
        parent.columnconfigure(1, weight=1)

    def _choose_file(self, title):
        return legacy.filedialog.askopenfilename(
            title=title,
            filetypes=[("Audio", "*.wav *.flac *.mp3 *.m4a *.aac *.ogg"), ("All files", "*.*")],
        )

    def _choose_advanced_source(self):
        path = self._choose_file("작업할 오디오 파일 선택")
        if path:
            self.advanced_source_var.set(path)

    def _choose_reference(self):
        path = self._choose_file("Reference 오디오 선택")
        if path:
            self.advanced_reference_var.set(path)

    def _choose_master(self):
        path = self._choose_file("비교할 마스터 파일 선택")
        if path:
            self.advanced_master_var.set(path)

    def _append_advanced(self, text):
        self.advanced_log.insert("end", text + "\n")
        self.advanced_log.see("end")

    def _set_advanced_result(self, title, text):
        self.advanced_log.delete("1.0", "end")
        self.advanced_log.insert("end", f"[{title}]\n{text}\n")
        self.advanced_status_var.set(title)

    def _require_source(self):
        path = Path(self.advanced_source_var.get().strip())
        if not path.exists():
            legacy.messagebox.showwarning("파일 필요", "먼저 작업 파일을 선택하세요.")
            return None
        return path

    def _background(self, label, func):
        self.advanced_status_var.set(f"{label} 처리 중...")

        def worker():
            try:
                text = func()
            except Exception as exc:
                self.after(0, self._set_advanced_result, f"{label} 실패", str(exc))
                return
            self.after(0, self._set_advanced_result, f"{label} 완료", text)

        threading.Thread(target=worker, daemon=True).start()

    def _show_tool_status(self):
        tools = detect_optional_tools()
        text = (
            "Optional tools\n"
            f"  noisereduce: {'READY' if tools.noisereduce else 'not installed'}\n"
            f"  DeepFilterNet: {'READY' if tools.deepfilternet else 'not installed'}\n"
            f"  audio-separator: {'READY' if tools.audio_separator else 'not installed'}\n"
            "정상곡에는 복원 도구를 사용하지 마세요."
        )
        self.advanced_log.insert("end", text + "\n")

    def analyze_advanced_source(self):
        source = self._require_source()
        if not source:
            return

        def task():
            metrics = analyze_file(source)
            return json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2, default=str)

        self._background("정밀 분석", task)

    def noise_repair(self):
        source = self._require_source()
        if not source:
            return

        def task():
            out_dir = source.parent / "HARU_REPAIR"
            destination = out_dir / f"{source.stem}_DENOISE.wav"
            reduce_noise_file(source, destination, strength=0.45)
            return f"보수적 spectral noise repair 완료\n{destination}\n원본과 반드시 A/B 비교하세요."

        self._background("Noise Repair", task)

    def deepfilter_repair(self):
        source = self._require_source()
        if not source:
            return

        def task():
            out_dir = source.parent / "HARU_REPAIR" / "DEEPFILTER"
            created = run_deepfilternet(source, out_dir)
            names = "\n".join(str(path) for path in created) or str(out_dir)
            return f"DeepFilterNet delay compensation ON\n{names}\n보컬/음성성 노이즈 문제에만 사용하세요."

        self._background("DeepFilterNet", task)

    def separate_stems(self):
        source = self._require_source()
        if not source:
            return

        def task():
            out_dir = source.parent / "HARU_REPAIR" / "STEMS"
            created = run_audio_separator(source, out_dir)
            names = "\n".join(str(path) for path in created) or str(out_dir)
            return f"Stem separation 완료\n{names}\n첫 실행에서는 모델 다운로드가 발생할 수 있습니다."

        self._background("Stem Separation", task)

    def reference_assist(self):
        source = self._require_source()
        if not source:
            return
        reference = Path(self.advanced_reference_var.get().strip())
        if not reference.exists():
            legacy.messagebox.showwarning("Reference 필요", "참조 파일을 선택하세요.")
            return

        def task():
            profile = v2.get_profile(self.genre_var.get())
            maximum = float(profile.get("maxAutomaticEqDb", 1.0))
            plan = build_reference_plan(source, reference, max_correction_db=maximum)
            chain = ffmpeg_equalizer_chain(plan)
            out_dir = source.parent / "HARU_REFERENCE"
            out_dir.mkdir(parents=True, exist_ok=True)
            destination = out_dir / f"{source.stem}_REF_ASSIST.wav"
            if chain:
                rc, _, err = legacy.run_ffmpeg(
                    self.ffmpeg,
                    [
                        "-y", "-hide_banner", "-i", str(source),
                        "-af", chain,
                        "-ar", "48000", "-c:a", "pcm_s24le", str(destination),
                    ],
                )
                if rc != 0:
                    raise RuntimeError((err or "Reference Assist FFmpeg error")[-4000:])
            else:
                shutil.copy2(source, destination)
            plan_path = out_dir / f"{source.stem}_reference_plan.json"
            plan_path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            lines = [f"{item.band}: {item.gain_db:+.2f} dB" for item in plan.corrections]
            return "Reference Assist 적용 완료\n" + str(destination) + "\n" + ("\n".join(lines) if lines else "톤 보정 불필요")

        self._background("Reference Assist", task)

    def codec_preview(self):
        source = self._require_source()
        if not source:
            return

        def task():
            out_dir = source.parent / "HARU_CODEC_PREVIEW"
            results = create_codec_previews(source, out_dir, ffmpeg=self.ffmpeg)
            lines = [
                f"{item.codec}: {item.metrics.lufs_i:.2f} LUFS / {item.metrics.true_peak_dbtp:.2f} dBTP"
                for item in results
            ]
            return "Codec roundtrip 완료\n" + "\n".join(lines) + f"\n{out_dir}"

        self._background("Codec Preview", task)

    def manual_quality_gate(self):
        source = self._require_source()
        if not source:
            return
        master = Path(self.advanced_master_var.get().strip())
        if not master.exists():
            legacy.messagebox.showwarning("마스터 필요", "비교 마스터 파일을 선택하세요.")
            return

        def task():
            result = evaluate_master(source, master, **_gate_kwargs(self.genre_var.get()))
            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str)

        self._background("Quality Gate", task)

    def install_ai_tools(self):
        installer = ROOT / "INSTALL_AI_TOOLS.bat"
        if not installer.exists():
            legacy.messagebox.showerror("설치 파일 없음", str(installer))
            return
        try:
            os.startfile(installer)
        except Exception as exc:
            legacy.messagebox.showerror("실행 실패", str(exc))


if __name__ == "__main__":
    AppV3().mainloop()
