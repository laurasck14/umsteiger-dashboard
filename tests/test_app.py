import unittest

from umsteiger_dashboard.app import _render_daily_chart, _render_page
from umsteiger_dashboard.models import DailyPoint, DailyScoreSeries, ScoreRecord


class AppRenderingTests(unittest.TestCase):
    def test_daily_chart_labels_every_fifteenth_date_and_exposes_filters(self) -> None:
        points = [DailyPoint(date=f"2026-09-{day:02d}", score=day * 10) for day in range(1, 17)]
        chart = _render_daily_chart([DailyScoreSeries(player="Laura", color="#007A5B", points=points)])

        self.assertEqual(chart.count("class=\"daily-date-label\""), 16)
        self.assertEqual(chart.count('style="display:"'), 2)
        self.assertIn('data-date="2026-09-01"', chart)
        self.assertIn('data-date="2026-09-16"', chart)
        self.assertIn('data-score="10"', chart)
        self.assertIn('class="daily-series-segment"', chart)

    def test_page_includes_daily_player_and_timeframe_controls(self) -> None:
        class State:
            records = [ScoreRecord(id="1", date="2026-09-01", player="Laura", score=420, max_score=500, source="x", status="parsed")]
            warnings = []
            source_name = ""
            imported_at = "2026-09-01T00:00:00+00:00"

        page = _render_page(State())

        self.assertIn("daily-timeframe", page)
        self.assertIn("Last week", page)
        self.assertIn("Last month", page)
        self.assertIn("Scores by player for each day. Faces mark each player's highest score in the selected timeframe.", page)
        self.assertIn("Each player's average score across all recorded games.", page)