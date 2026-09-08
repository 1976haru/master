from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable

from .quality_gate import QualityGateResult


def write_quality_reports(
    output_dir: str | Path,
    rows: Iterable[tuple[str, QualityGateResult]],
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    items = list(rows)

    json_path = output / "HARU_QUALITY_GATE.json"
    json_payload = [
        {"track": track, **result.to_dict()}
        for track, result in items
    ]
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
        detail_text = " / ".join(details) if details else "OK"
        delay = "?" if result.residual_delay_samples is None else str(result.residual_delay_samples)
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(track)}</td>"
            f"<td><strong>{html.escape(result.status)}</strong></td>"
            f"<td>{result.processed.lufs_i:.2f}</td>"
            f"<td>{result.processed.true_peak_dbtp:.2f}</td>"
            f"<td>{result.processed.lra_lu:.2f}</td>"
            f"<td>{delay}</td>"
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
        "table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ddd;"
        "padding:8px;text-align:left}th{background:#f3f3f3}.summary{font-size:18px;margin:12px 0 20px}"
        "</style></head><body>"
        "<h1>HARU Mastering Quality Gate</h1>"
        f"<div class='summary'>PASS {counts.get('PASS',0)} / WARN {counts.get('WARN',0)} / FAIL {counts.get('FAIL',0)}</div>"
        "<table><thead><tr><th>Track</th><th>Status</th><th>LUFS-I</th><th>dBTP</th>"
        "<th>LRA</th><th>Delay(samples)</th><th>Duration Δ(ms)</th><th>Notes</th>"
        "</tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table></body></html>",
        encoding="utf-8",
    )
    return json_path, html_path
