from __future__ import annotations

import html
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .analysis import analyze_file
from .quality_gate import QualityGateResult


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _refresh_final_metrics(
    output_dir: Path,
    track: str,
    result: QualityGateResult,
) -> QualityGateResult:
    """Use the actual final WAV after Tail/codec/alignment post-processing in reports."""
    final_path = output_dir / f"{Path(track).stem}_MASTER.wav"
    if not final_path.exists():
        return result
    try:
        actual = analyze_file(final_path)
    except Exception:
        return result

    post_gain = float(result.processed.lufs_i - actual.lufs_i)
    warnings = result.warnings
    if post_gain > 0.03:
        warning = f"codec safety attenuation applied: -{post_gain:.2f} dB"
        if warning not in warnings:
            warnings = warnings + (warning,)
    return replace(result, processed=actual, warnings=warnings)


def write_quality_reports(
    output_dir: str | Path,
    rows: Iterable[tuple[str, QualityGateResult]],
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    items = [
        (track, _refresh_final_metrics(output, track, result))
        for track, result in rows
    ]

    json_path = output / "HARU_QUALITY_GATE.json"
    json_payload = []
    for track, result in items:
        payload = {"track": track, **result.to_dict()}
        payload["crest_factor_change_db"] = -float(result.crest_factor_loss_db)
        json_payload.append(_json_safe(payload))
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for _, result in items:
        counts[result.status] = counts.get(result.status, 0) + 1

    table_rows: list[str] = []
    for track, result in items:
        details = list(result.issues) + list(result.warnings)
        if result.delay_note and result.delay_classification in {"INFO", "WARN"}:
            details.append(result.delay_note)
        detail_text = " / ".join(dict.fromkeys(details)) if details else "OK"
        delay = "?" if result.residual_delay_samples is None else str(result.residual_delay_samples)
        delay_windows = ",".join(str(value) for value in result.delay_window_estimates_samples) or "?"
        delay_confidence = f"{result.delay_confidence:.2f}" if result.delay_window_estimates_samples else "?"
        delay_class = result.delay_classification
        if result.delay_auto_aligned:
            delay_class = "AUTO-ALIGNED"
        if result.tail_hard_cut:
            tail = "HARD CUT"
        elif result.tail_energetic_end:
            tail = "ENERGETIC"
        else:
            tail = "SAFE"
        dynamics = "RISK" if result.lra_guard_triggered else "SAFE"
        crest_change = -float(result.crest_factor_loss_db)
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(track)}</td>"
            f"<td><strong>{html.escape(result.status)}</strong></td>"
            f"<td>{result.processed.lufs_i:.2f}</td>"
            f"<td>{result.processed.true_peak_dbtp:.2f}</td>"
            f"<td>{result.processed.lra_lu:.2f}</td>"
            f"<td>{result.lra_reduction_lu:.2f}</td>"
            f"<td>{crest_change:+.2f}</td>"
            f"<td>{dynamics}</td>"
            f"<td>{result.low_band_stereo_correlation:.3f}</td>"
            f"<td>{delay}</td>"
            f"<td>{html.escape(delay_class)}</td>"
            f"<td>{delay_confidence}</td>"
            f"<td>{html.escape(delay_windows)}</td>"
            f"<td>{tail}</td>"
            f"<td>{result.tail_end_rms_dbfs:.1f}</td>"
            f"<td>{result.tail_last_sample_dbfs:.1f}</td>"
            f"<td>{result.duration_delta_ms:.2f}</td>"
            f"<td>{html.escape(detail_text)}</td>"
            "</tr>"
        )

    html_path = output / "HARU_QUALITY_GATE.html"
    html_path.write_text(
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>HARU Mastering Quality Gate</title>"
        "<style>body{font-family:Segoe UI,Malgun Gothic,sans-serif;margin:24px;color:#222}"
        "table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #ddd;"
        "padding:6px;text-align:left}th{background:#f3f3f3}.summary{font-size:18px;margin:12px 0 20px}"
        "</style></head><body>"
        "<h1>HARU Mastering Quality Gate v3.4</h1>"
        f"<div class='summary'>PASS {counts.get('PASS',0)} / WARN {counts.get('WARN',0)} / FAIL {counts.get('FAIL',0)}</div>"
        "<table><thead><tr><th>Track</th><th>Status</th><th>LUFS-I</th><th>dBTP</th>"
        "<th>LRA</th><th>LRA 감소</th><th>Crest 변화</th><th>Dynamics</th>"
        "<th>저역상관</th><th>Delay</th><th>Delay 판정</th><th>신뢰도</th><th>구간값</th>"
        "<th>Tail</th><th>End RMS</th><th>Last Sample</th><th>Duration Δ</th><th>Notes</th>"
        "</tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table></body></html>",
        encoding="utf-8",
    )
    return json_path, html_path
