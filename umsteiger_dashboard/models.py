from dataclasses import dataclass
from typing import Literal

ParseStatus = Literal["parsed", "missing", "unknown"]
WarningKind = Literal["unparsed-line", "unknown-player", "missing-score", "duplicate-score"]


@dataclass(frozen=True)
class ScoreRecord:
    id: str
    date: str
    player: str
    score: int | None
    max_score: int | None
    source: str
    status: ParseStatus


@dataclass(frozen=True)
class ParseWarning:
    line_number: int
    kind: WarningKind
    message: str
    line: str


@dataclass(frozen=True)
class ParseResult:
    records: list[ScoreRecord]
    warnings: list[ParseWarning]
    players: list[str]


@dataclass(frozen=True)
class DailyPoint:
    date: str
    score: int | None


@dataclass(frozen=True)
class DailyScoreSeries:
    player: str
    color: str
    points: list[DailyPoint]


@dataclass(frozen=True)
class AverageScoreSeries:
    player: str
    color: str
    average_score: float
    games_played: int