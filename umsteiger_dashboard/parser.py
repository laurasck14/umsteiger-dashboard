from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .models import ParseResult, ParseWarning, ScoreRecord

LINE_PATTERN = re.compile(
    r"^(?P<date>\d{1,2}[./]\d{1,2}[./]\d{2,4}),\s*(?P<time>\d{1,2}:\d{2})\s*-\s*(?P<sender>[^:]+):\s*(?P<message>.*)$"
)
SYSTEM_LINE_PATTERN = re.compile(
    r"^(?P<date>\d{1,2}[./]\d{1,2}[./]\d{2,4}),\s*(?P<time>\d{1,2}:\d{2})\s*-\s*(?P<message>.*)$"
)
SCORE_PATTERN = re.compile(r"(?P<score>\d{1,3})\s*/\s*(?P<max_score>\d{1,3})")
PLAIN_SCORE_PATTERN = re.compile(r"^\d{1,3}$")


@dataclass
class _ParsedLine:
    date: str
    sender: str
    message: str
    line_number: int
    line: str


def _normalize_date(raw_date: str) -> str:
    separator = "." if "." in raw_date else "/"
    day_text, month_text, year_text = [part.strip() for part in raw_date.split(separator)]
    year_value = int(year_text)
    if year_value < 100:
        year_value += 2000
    normalized = date(year_value, int(month_text), int(day_text))
    return normalized.isoformat()


def _extract_score(message: str) -> tuple[int | None, int | None, str]:
    trimmed = message.strip()
    if not trimmed:
        return (None, None, "missing")

    if re.search(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", trimmed):
        return (None, None, "missing")

    if PLAIN_SCORE_PATTERN.fullmatch(trimmed) is not None:
        score = int(trimmed)
        if 0 <= score <= 500:
            return (score, None, "parsed")
        return (None, None, "missing")

    if "umsteigen.app" not in trimmed.lower():
        return (None, None, "missing")

    explicit_match = SCORE_PATTERN.search(trimmed)
    if explicit_match is not None:
        score = int(explicit_match.group("score"))
        max_score = int(explicit_match.group("max_score"))
        if 0 <= score <= 500 and 0 < max_score <= 500:
            return (score, max_score, "parsed")
        return (None, None, "missing")

    return (None, None, "missing")


def _warning(line_number: int, kind: str, message: str, line: str) -> ParseWarning:
    return ParseWarning(line_number=line_number, kind=kind, message=message, line=line)


def _record_id(record_date: str, player: str, score: int, line_number: int) -> str:
    return f"{record_date}:{player}:{score}:{line_number}"


def parse_whatsapp_export(text: str, known_players: list[str] | None = None) -> ParseResult:
    warnings: list[ParseWarning] = []
    records: list[ScoreRecord] = []
    players: set[str] = set()
    seen_score_keys: set[tuple[str, str]] = set()
    allowed_players = {player.strip().lower() for player in known_players} if known_players else None

    def finalize(parsed_line: _ParsedLine | None) -> None:
        if parsed_line is None:
            return

        sender = parsed_line.sender.strip()
        sender_key = sender.lower()

        if allowed_players is not None and sender_key not in allowed_players:
            return

        score, max_score, status = _extract_score(parsed_line.message)
        if score is None:
            return

        players.add(sender)
        record_date = parsed_line.date
        score_key = (record_date, sender_key)
        if score_key in seen_score_keys:
            warnings.append(
                _warning(
                    parsed_line.line_number,
                    "duplicate-score",
                    f"Duplicate score for {sender} on {record_date}.",
                    parsed_line.line,
                )
            )
        else:
            seen_score_keys.add(score_key)

        records.append(
            ScoreRecord(
                id=_record_id(record_date, sender, score, parsed_line.line_number),
                date=record_date,
                player=sender,
                score=score,
                max_score=max_score,
                source=parsed_line.line,
                status=status,
            )
        )

    current_line: _ParsedLine | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        header_match = LINE_PATTERN.match(raw_line)
        if header_match is not None:
            finalize(current_line)
            current_line = _ParsedLine(
                date=_normalize_date(header_match.group("date")),
                sender=header_match.group("sender"),
                message=header_match.group("message"),
                line_number=line_number,
                line=raw_line,
            )
            continue

        if SYSTEM_LINE_PATTERN.match(stripped) is not None:
            finalize(current_line)
            current_line = None
            continue

        if current_line is not None:
            current_line = _ParsedLine(
                date=current_line.date,
                sender=current_line.sender,
                message=f"{current_line.message}\n{stripped}",
                line_number=current_line.line_number,
                line=f"{current_line.line}\n{stripped}",
            )
            continue

        continue

    finalize(current_line)

    return ParseResult(records=records, warnings=warnings, players=sorted(players))