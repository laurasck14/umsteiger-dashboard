import unittest
from pathlib import Path

from umsteiger_dashboard.models import ParseWarning, ScoreRecord
from umsteiger_dashboard.storage import (
    export_records_to_csv,
    export_records_to_json,
    import_records_from_csv,
    import_records_from_json,
    load_state,
    save_state_with_warnings,
)


def _records() -> list[ScoreRecord]:
    return [
        ScoreRecord(id="1", date="2026-09-19", player="Anna", score=452, max_score=None, source="Anna: 452", status="parsed"),
        ScoreRecord(id="2", date="2026-09-19", player="Ben", score=390, max_score=500, source="Ben: 390 / 500", status="parsed"),
    ]


class StorageTests(unittest.TestCase):
    def test_storage_round_trip(self) -> None:
        state_path = Path(self._testMethodName + ".json")
        warnings = [ParseWarning(line_number=2, kind="missing-score", message="missing", line="line")]
        save_state_with_warnings(_records(), warnings, "2026-09-19T09:00:00Z", "sample.txt", path=state_path)

        loaded = load_state(path=state_path)

        try:
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.imported_at, "2026-09-19T09:00:00Z")
            self.assertEqual(loaded.source_name, "sample.txt")
            self.assertEqual(loaded.records, _records())
            self.assertEqual(loaded.warnings, warnings)
        finally:
            if state_path.exists():
                state_path.unlink()

    def test_csv_and_json_export_import_round_trip(self) -> None:
        records = _records()

        csv_text = export_records_to_csv(records)
        json_text = export_records_to_json(records)

        self.assertEqual(import_records_from_csv(csv_text), records)
        self.assertEqual(import_records_from_json(json_text), records)