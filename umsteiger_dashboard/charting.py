from __future__ import annotations

from collections import defaultdict

from .models import AverageScoreSeries, DailyPoint, DailyScoreSeries, ScoreRecord

COLORS = ["#2563eb", "#f97316", "#22c55e", "#a855f7", "#ef4444", "#14b8a6"]
PLAYER_COLORS = {
    "Salvatore Lauricella": "#7DAD4C",
    "Antonio Robert": "#DA421E",
    "Laura Santa Cruz": "#007A5B",
    "Rajas Sane": "#F0D722",
    "Andrea Petrus": "#7E5330",
}


def _color_for_player(player: str, fallback_index: int) -> str:
    return PLAYER_COLORS.get(player, COLORS[fallback_index % len(COLORS)])


def build_daily_score_series(records: list[ScoreRecord]) -> list[DailyScoreSeries]:
    players = sorted({record.player for record in records})
    dates = sorted({record.date for record in records})
    score_lookup: dict[tuple[str, str], int] = {}

    for record in records:
        if record.score is None:
            continue
        score_lookup[(record.player, record.date)] = record.score

    series: list[DailyScoreSeries] = []
    for index, player in enumerate(players):
        points = [DailyPoint(date=record_date, score=score_lookup.get((player, record_date))) for record_date in dates]
        series.append(DailyScoreSeries(player=player, color=_color_for_player(player, index), points=points))

    return series


def build_average_score_series(records: list[ScoreRecord]) -> list[AverageScoreSeries]:
    grouped_scores: dict[str, list[int]] = defaultdict(list)
    for record in records:
        if record.score is not None:
            grouped_scores[record.player].append(record.score)

    series: list[AverageScoreSeries] = []
    ranked_players = sorted(grouped_scores, key=lambda player: (-sum(grouped_scores[player]) / len(grouped_scores[player]), player))
    for index, player in enumerate(ranked_players):
        scores = grouped_scores[player]
        series.append(
            AverageScoreSeries(
                player=player,
                color=_color_for_player(player, index),
                average_score=sum(scores) / len(scores),
                games_played=len(scores),
            )
        )

    return series