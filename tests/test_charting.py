import unittest

from umsteiger_dashboard.charting import build_average_score_series, build_daily_score_series
from umsteiger_dashboard.models import ScoreRecord


def _records() -> list[ScoreRecord]:
    return [
        ScoreRecord(id="1", date="2026-09-18", player="Anna", score=420, max_score=500, source="x", status="parsed"),
        ScoreRecord(id="2", date="2026-09-19", player="Anna", score=450, max_score=500, source="y", status="parsed"),
        ScoreRecord(id="3", date="2026-09-18", player="Ben", score=300, max_score=500, source="z", status="parsed"),
    ]


class ChartingTests(unittest.TestCase):
    def test_build_daily_score_series_fills_missing_dates_with_none(self) -> None:
        series = build_daily_score_series(_records())

        self.assertEqual(len(series), 2)
        self.assertEqual([point.score for point in series[0].points], [420, 450])
        self.assertEqual([point.score for point in series[1].points], [300, None])

    def test_build_average_score_series_uses_all_scored_rows(self) -> None:
        series = build_average_score_series(_records())

        self.assertEqual(len(series), 2)
        self.assertEqual(series[0].player, "Anna")
        self.assertEqual(series[0].average_score, 435)
        self.assertEqual(series[0].games_played, 2)

    def test_build_average_score_series_ranks_players_by_highest_average(self) -> None:
        records = [
            ScoreRecord(id="1", date="2026-09-18", player="Anna", score=100, max_score=500, source="x", status="parsed"),
            ScoreRecord(id="2", date="2026-09-19", player="Anna", score=200, max_score=500, source="x", status="parsed"),
            ScoreRecord(id="3", date="2026-09-18", player="Ben", score=250, max_score=500, source="y", status="parsed"),
            ScoreRecord(id="4", date="2026-09-19", player="Ben", score=300, max_score=500, source="y", status="parsed"),
            ScoreRecord(id="5", date="2026-09-18", player="Cara", score=50, max_score=500, source="z", status="parsed"),
        ]

        series = build_average_score_series(records)

        self.assertEqual([entry.player for entry in series], ["Ben", "Anna", "Cara"])
        self.assertEqual([entry.average_score for entry in series], [275, 150, 50])