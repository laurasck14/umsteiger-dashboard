import unittest
import re

from umsteiger_dashboard.app import _render_daily_chart, _render_page
from umsteiger_dashboard.models import DailyPoint, DailyScoreSeries, ScoreRecord


class AppRenderingTests(unittest.TestCase):
    def test_daily_chart_stacks_faces_for_shared_peak_datapoints(self) -> None:
        points = [DailyPoint(date="2026-04-05", score=500)]
        chart = _render_daily_chart(
            [
                DailyScoreSeries(player="Salvatore Lauricella", color="#7DAD4C", points=points),
                DailyScoreSeries(player="Antonio Robert", color="#DA421E", points=points),
            ]
        )

        portrait_tags = re.findall(r'<image[^>]*class="daily-portrait"[^>]*/>', chart)
        portraits = [
            (re.search(r' x="([\d.]+)"', tag).group(1), re.search(r' y="([\d.]+)"', tag).group(1))
            for tag in portrait_tags
        ]
        self.assertEqual(len(portraits), 2)
        self.assertEqual(portraits[0][0], portraits[1][0])
        self.assertNotEqual(portraits[0][1], portraits[1][1])

    def test_daily_chart_places_face_on_latest_highest_score(self) -> None:
        points = [
            DailyPoint(date="2026-04-03", score=500),
            DailyPoint(date="2026-04-04", score=420),
            DailyPoint(date="2026-04-05", score=500),
        ]

        chart = _render_daily_chart([DailyScoreSeries(player="Laura Santa Cruz", color="#007A5B", points=points)])

        portrait_index = chart.index('class="daily-portrait"')
        self.assertGreater(portrait_index, chart.index('data-date="2026-04-05"'))
        self.assertGreater(portrait_index, chart.index('data-date="2026-04-03"'))

    def test_daily_chart_labels_every_third_date_and_exposes_filters(self) -> None:
        points = [DailyPoint(date=f"2026-09-{day:02d}", score=day * 10) for day in range(1, 17)]
        chart = _render_daily_chart([DailyScoreSeries(player="Laura", color="#007A5B", points=points)])

        self.assertEqual(chart.count("class=\"daily-date-label\""), 16)
        self.assertEqual(chart.count('style="display:"'), 6)
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
        self.assertIn("Number(point.dataset.score) >= Number(peak.dataset.score)", page)
        self.assertIn("const portraitRows = new Map();", page)