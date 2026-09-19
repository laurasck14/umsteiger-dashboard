from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import ParseWarning, ScoreRecord

STATE_PATH = Path(__file__).resolve().parent.parent / ".umsteiger_state.json"


@dataclass(frozen=True)
class StoredState:
    records: list[ScoreRecord]
    warnings: list[ParseWarning]
    imported_at: str
    source_name: str


def _record_from_dict(payload: dict[str, object]) -> ScoreRecord:
    return ScoreRecord(
        id=str(payload["id"]),
        date=str(payload["date"]),
        player=str(payload["player"]),
        score=None if payload.get("score") in (None, "") else int(payload["score"]),
        max_score=None if payload.get("max_score") in (None, "") else int(payload["max_score"]),
        source=str(payload["source"]),
        status=str(payload["status"]),
    )


def save_state(records: list[ScoreRecord], imported_at: str, path: Path = STATE_PATH) -> None:
    save_state_with_warnings(records, [], imported_at, "", path=path)


def save_state_with_warnings(
    records: list[ScoreRecord],
    warnings: list[ParseWarning],
    imported_at: str,
    source_name: str,
    path: Path = STATE_PATH,
) -> None:
    payload = {
        "imported_at": imported_at,
        "source_name": source_name,
        "records": [asdict(record) for record in records],
        "warnings": [asdict(warning) for warning in warnings],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_state(path: Path = STATE_PATH) -> StoredState | None:
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    records = [_record_from_dict(record) for record in payload.get("records", [])]
    warnings = [ParseWarning(**warning) for warning in payload.get("warnings", []) if isinstance(warning, dict)]
    return StoredState(
        records=records,
        warnings=warnings,
        imported_at=str(payload.get("imported_at", "")),
        source_name=str(payload.get("source_name", "")),
    )


def export_records_to_json(records: list[ScoreRecord]) -> str:
    return json.dumps([asdict(record) for record in records], indent=2)


def import_records_from_json(text: str) -> list[ScoreRecord]:
    payload = json.loads(text)
    if isinstance(payload, dict):
        payload = payload.get("records", [])
    if not isinstance(payload, list):
        return []
    return [_record_from_dict(item) for item in payload if isinstance(item, dict)]


def export_records_to_csv(records: list[ScoreRecord]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "date", "player", "score", "max_score", "source", "status"])
    for record in records:
        writer.writerow([record.id, record.date, record.player, record.score if record.score is not None else "", record.max_score if record.max_score is not None else "", record.source, record.status])
    return buffer.getvalue()


def import_records_from_csv(text: str) -> list[ScoreRecord]:
    reader = csv.DictReader(io.StringIO(text))
    records: list[ScoreRecord] = []
    for row in reader:
        records.append(
            ScoreRecord(
                id=row["id"],
                date=row["date"],
                player=row["player"],
                score=None if row.get("score", "") == "" else int(row["score"]),
                max_score=None if row.get("max_score", "") == "" else int(row["max_score"]),
                source=row.get("source", ""),
                status=row.get("status", "missing"),
            )
        )
    return records