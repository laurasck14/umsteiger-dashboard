from __future__ import annotations

import cgi
import html
import io
import json
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .charting import build_average_score_series, build_daily_score_series
from .models import AverageScoreSeries, DailyScoreSeries, ParseWarning, ScoreRecord
from .parser import parse_whatsapp_export
from .storage import (
    STATE_PATH,
    export_records_to_csv,
    export_records_to_json,
    import_records_from_csv,
    import_records_from_json,
    load_state,
    save_state_with_warnings,
)


def _escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _warning_counts(warnings: Iterable[ParseWarning]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for warning in warnings:
        counts[warning.kind] = counts.get(warning.kind, 0) + 1
    return counts


def _dates_for_series(series: list[DailyScoreSeries]) -> list[str]:
    if not series:
        return []
    return [point.date for point in series[0].points]


def _render_daily_chart(series: list[DailyScoreSeries]) -> str:
    width = 980
    height = 360
    padding_x = 52
    padding_top = 28
    padding_bottom = 54
    dates = _dates_for_series(series)
    score_values = [point.score for entry in series for point in entry.points if point.score is not None]
    max_score = max([500, *score_values]) if score_values else 500
    inner_width = width - (padding_x * 2)
    inner_height = height - padding_top - padding_bottom

    def x_for_index(index: int) -> float:
        if len(dates) <= 1:
            return padding_x + inner_width / 2
        return padding_x + (index / (len(dates) - 1)) * inner_width

    def y_for_score(score: int) -> float:
        return padding_top + inner_height - ((score / max_score) * inner_height)

    pieces = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Daily score chart" class="chart">']
    pieces.append(f'<rect x="0" y="0" width="{width}" height="{height}" rx="24" fill="#ffffff" stroke="#e5e7eb" />')
    pieces.append(f'<line x1="{padding_x}" y1="{padding_top + inner_height}" x2="{padding_x + inner_width}" y2="{padding_top + inner_height}" stroke="#cbd5e1" stroke-width="2" />')
    pieces.append(f'<line x1="{padding_x}" y1="{padding_top}" x2="{padding_x}" y2="{padding_top + inner_height}" stroke="#cbd5e1" stroke-width="2" />')

    for index, date_value in enumerate(dates):
        x = x_for_index(index)
        pieces.append(f'<text x="{x:.1f}" y="{height - 18}" fill="#475569" font-size="12" text-anchor="middle">{_escape(date_value[5:])}</text>')

    for entry in series:
        current_segment: list[str] = []
        for index, point in enumerate(entry.points):
            if point.score is None:
                if current_segment:
                    pieces.append(
                        f'<polyline fill="none" points="{" ".join(current_segment)}" stroke="{entry.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />'
                    )
                    current_segment = []
                continue

            x = x_for_index(index)
            y = y_for_score(point.score)
            current_segment.append(f"{x:.1f},{y:.1f}")
            pieces.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{entry.color}" />')

        if current_segment:
            pieces.append(
                f'<polyline fill="none" points="{" ".join(current_segment)}" stroke="{entry.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />'
            )

    pieces.append("</svg>")
    return "".join(pieces)


def _render_average_chart(series: list[AverageScoreSeries]) -> str:
    width = 980
    bar_height = 30
    gap = 16
    left_padding = 200
    right_padding = 120
    top_padding = 28
    bottom_padding = 24
    height = max(180, top_padding + bottom_padding + len(series) * (bar_height + gap))
    max_value = max([1.0, *[item.average_score for item in series]])
    usable_width = width - left_padding - right_padding

    pieces = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Average score chart" class="chart">']
    pieces.append(f'<rect x="0" y="0" width="{width}" height="{height}" rx="24" fill="#ffffff" stroke="#e5e7eb" />')

    for index, entry in enumerate(series):
        y = top_padding + index * (bar_height + gap)
        bar_width = (entry.average_score / max_value) * usable_width
        pieces.append(f'<text x="24" y="{y + 20}" fill="#111827" font-size="14">{_escape(entry.player)}</text>')
        pieces.append(f'<rect x="{left_padding}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" rx="12" fill="{entry.color}" />')
        pieces.append(f'<text x="{left_padding + bar_width + 10:.1f}" y="{y + 20}" fill="#111827" font-size="14">{int(round(entry.average_score))}</text>')

    pieces.append("</svg>")
    return "".join(pieces)


def _render_table(headers: list[str], rows: list[list[object]]) -> str:
    table = ["<table>", "<thead><tr>"]
    for header in headers:
        table.append(f"<th>{_escape(header)}</th>")
    table.append("</tr></thead><tbody>")
    for row in rows:
        table.append("<tr>")
        for cell in row:
            table.append(f"<td>{_escape(cell)}</td>")
        table.append("</tr>")
    table.append("</tbody></table>")
    return "".join(table)


def _render_metrics(records: list[ScoreRecord], warnings: list[ParseWarning]) -> str:
    players = sorted({record.player for record in records})
    dates = sorted({record.date for record in records})
    values = [
        ("Score rows", len(records)),
        ("Players", len(players)),
        ("Days", len(dates)),
        ("Warnings", len(warnings)),
    ]
    pieces = ['<div class="metrics">']
    for label, value in values:
        pieces.append(f'<div class="metric"><span>{_escape(label)}</span><strong>{value}</strong></div>')
    pieces.append("</div>")
    return "".join(pieces)


def _render_page(stored_state, status_message: str | None = None) -> str:
    records = stored_state.records if stored_state else []
    warnings = stored_state.warnings if stored_state else []
    source_name = stored_state.source_name if stored_state else ""
    imported_at = stored_state.imported_at if stored_state else ""
    daily_series = build_daily_score_series(records)
    average_series = build_average_score_series(records)

    parts = ["<!doctype html>", "<html lang='en'>", "<head>"]
    parts.append('<meta charset="utf-8" />')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1" />')
    parts.append("<title>Umsteiger Dashboard</title>")
    parts.append(
        """
        <style>
          :root {
            color-scheme: light;
            --bg: #f8fafc;
            --panel: rgba(255, 255, 255, 0.94);
            --panel-strong: #ffffff;
            --border: rgba(148, 163, 184, 0.24);
            --text: #0f172a;
            --muted: #475569;
            --accent: #2563eb;
            --warn: #f59e0b;
          }
          * { box-sizing: border-box; }
          html, body { margin: 0; min-height: 100%; background: linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
          body { padding: 32px; }
          .page { max-width: 1200px; margin: 0 auto; display: grid; gap: 24px; }
          .hero, .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 24px; box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08); }
          .hero { padding: 28px; }
          .hero h1 { margin: 0 0 8px; font-size: clamp(2rem, 4vw, 3.5rem); }
          .hero p { margin: 0; max-width: 70ch; color: var(--muted); line-height: 1.6; }
          .toolbar { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin-top: 20px; }
          .uploader, .links { padding: 18px; border-radius: 18px; background: #ffffff; border: 1px solid var(--border); }
          .uploader form { display: grid; gap: 12px; }
          input[type='file'], button, .download { width: 100%; border-radius: 999px; border: 1px solid var(--border); padding: 12px 16px; font: inherit; }
          input[type='file'] { background: #ffffff; color: var(--text); }
          button, .download { display: inline-flex; justify-content: center; align-items: center; background: linear-gradient(135deg, #38bdf8, #0ea5e9); color: #082f49; font-weight: 700; text-decoration: none; }
          .links { display: grid; gap: 12px; align-content: start; }
          .status { color: #0f172a; background: rgba(37, 99, 235, 0.08); border: 1px solid rgba(37, 99, 235, 0.16); padding: 12px 16px; border-radius: 14px; }
          .muted { color: var(--muted); }
          .metrics, .warning-metrics { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
          .metric { padding: 18px; border-radius: 18px; background: #f8fafc; border: 1px solid var(--border); display: grid; gap: 8px; }
          .metric span { color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; }
          .metric strong { font-size: 1.8rem; }
          .panel { padding: 24px; display: grid; gap: 16px; }
          .grid-2 { display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
          .chart { width: 100%; height: auto; display: block; }
          table { width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 18px; }
          th, td { padding: 12px 14px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
          th { color: var(--accent); text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; }
          td { color: var(--text); }
          .tag { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 999px; background: rgba(148, 163, 184, 0.1); color: var(--muted); }
          .warning-list { overflow-x: auto; }
          .footer { color: var(--muted); font-size: 0.92rem; }
          @media (max-width: 700px) { body { padding: 16px; } .hero, .panel { padding: 18px; } }
        </style>
        """
    )
    parts.append("</head><body><div class='page'>")
    parts.append("<section class='hero'>")
    parts.append("<h1>Umsteiger Dashboard</h1>")
    parts.append("<p>A fully local browser dashboard for WhatsApp score exports from the Umsteigen daily challenge. Upload a chat export, inspect the daily score line chart, and compare player averages without sending data to a server.</p>")

    if records:
        parts.append("<section class='panel' style='margin-top: 20px;'>")
        parts.append("<h2>Daily scores</h2>")
        parts.append(_render_daily_chart(daily_series))
        parts.append("</section>")

        parts.append("<section class='panel' style='margin-top: 20px;'>")
        parts.append("<h2>Average score over time</h2>")
        parts.append(_render_average_chart(average_series))
        parts.append("</section>")
    else:
        parts.append("<section class='panel' style='margin-top: 20px;'><h2>Daily scores</h2><p class='muted'>Upload a WhatsApp export or a previously exported CSV/JSON backup to populate the dashboard.</p></section>")

    if status_message:
        parts.append(f"<div class='status' style='margin-top: 20px;'>{_escape(status_message)}</div>")
    parts.append("<div class='toolbar' style='margin-top: 20px;'>")
    parts.append("<div class='uploader'>")
    parts.append("<form action='/upload' method='post' enctype='multipart/form-data'>")
    parts.append("<label><strong>Import WhatsApp TXT, CSV, or JSON</strong><br><span class='muted'>TXT files are parsed as exports, CSV and JSON files are treated as saved dashboard backups.</span></label>")
    parts.append("<input type='file' name='upload_file' accept='.txt,.csv,.json' required />")
    parts.append("<button type='submit'>Import file</button>")
    parts.append("</form></div>")
    parts.append("<div class='links'>")
    parts.append("<a class='download' href='/export.csv'>Download CSV</a>")
    parts.append("<a class='download' href='/export.json'>Download JSON</a>")
    parts.append(f"<div class='tag'>Local state file: {_escape(STATE_PATH.name)}</div>")
    parts.append("</div></div>")
    parts.append("</section>")

    if imported_at:
        parts.append(f"<section class='panel'><p class='footer'>Last import: {_escape(imported_at)}")
        if source_name:
            parts.append(f" from {_escape(source_name)}")
        parts.append(".</p></section>")

    parts.append("</div></body></html>")
    return "".join(parts)


def _load_current_state():
    return load_state()


def _save_parsed_result(records: list[ScoreRecord], warnings: list[ParseWarning], source_name: str) -> None:
    imported_at = datetime.now(timezone.utc).isoformat()
    save_state_with_warnings(records, warnings, imported_at, source_name)


def _handle_upload(handler: BaseHTTPRequestHandler) -> None:
    content_length = int(handler.headers.get("Content-Length", "0"))
    form = cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": handler.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(content_length),
        },
    )

    file_item = form["upload_file"] if "upload_file" in form else None
    if file_item is None or not getattr(file_item, "filename", None):
        handler.send_response(HTTPStatus.BAD_REQUEST)
        handler.send_header("Content-Type", "text/plain; charset=utf-8")
        handler.end_headers()
        handler.wfile.write(b"Missing upload_file field")
        return

    filename = Path(file_item.filename).name
    raw_bytes = file_item.file.read()
    text = raw_bytes.decode("utf-8", errors="replace")
    suffix = Path(filename).suffix.lower()

    if suffix == ".csv":
        records = import_records_from_csv(text)
        warnings: list[ParseWarning] = []
    elif suffix == ".json":
        records = import_records_from_json(text)
        warnings = []
    else:
        parsed = parse_whatsapp_export(text)
        records = parsed.records
        warnings = parsed.warnings

    _save_parsed_result(records, warnings, filename)

    handler.send_response(HTTPStatus.SEE_OTHER)
    handler.send_header("Location", "/")
    handler.end_headers()


def _handle_export(handler: BaseHTTPRequestHandler, content: str, filename: str, content_type: str) -> None:
    encoded = content.encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed_url = urlparse(self.path)
        current_state = _load_current_state()

        if parsed_url.path == "/export.csv":
            records = current_state.records if current_state else []
            _handle_export(self, export_records_to_csv(records), "umsteiger-scores.csv", "text/csv; charset=utf-8")
            return

        if parsed_url.path == "/export.json":
            records = current_state.records if current_state else []
            _handle_export(self, export_records_to_json(records), "umsteiger-scores.json", "application/json; charset=utf-8")
            return

        html_body = _render_page(current_state)
        encoded = html_body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/upload":
            _handle_upload(self)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown path")

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Serving Umsteiger Dashboard on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        server.server_close()