import unittest

from umsteiger_dashboard.parser import parse_whatsapp_export


class ParserTests(unittest.TestCase):
    def test_parse_whatsapp_export_handles_plain_and_formatted_scores(self) -> None:
        result = parse_whatsapp_export(
            """
19.09.2026, 09:01 - Anna: 452
19.09.2026, 09:02 - Ben: umsteigen.app · Berlin 🚇 19. Sept. 390 / 500 · Umsteige-Profi 🟢–🟡–🟢–🟢–🟢
            """.strip()
        )

        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0].date, "2026-09-19")
        self.assertEqual(result.records[0].player, "Anna")
        self.assertEqual(result.records[0].score, 452)
        self.assertEqual(result.records[1].player, "Ben")
        self.assertEqual(result.records[1].score, 390)
        self.assertEqual(result.records[1].max_score, 500)
        self.assertEqual(result.players, ["Anna", "Ben"])

    def test_parse_whatsapp_export_ignores_non_score_chatter(self) -> None:
        result = parse_whatsapp_export(
            """
19.09.2026, 09:01 - Anna: hello
19.09.2026, 09:02 - Clara: how are you?
            """.strip(),
        )

        self.assertEqual(result.records, [])
        self.assertEqual(result.warnings, [])

    def test_parse_whatsapp_export_rejects_out_of_range_scores(self) -> None:
        result = parse_whatsapp_export(
            """
19.09.2026, 09:01 - Anna: 501
19.09.2026, 09:02 - Ben: 0
            """.strip()
        )

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].player, "Ben")
        self.assertEqual(result.records[0].score, 0)

    def test_parse_whatsapp_export_marks_duplicate_scores(self) -> None:
        result = parse_whatsapp_export(
            """
19.09.2026, 09:01 - Anna: 400
19.09.2026, 09:02 - Anna: 450
            """.strip()
        )

        self.assertEqual(len(result.records), 2)
        self.assertTrue(any(warning.kind == "duplicate-score" for warning in result.warnings))

    def test_parse_whatsapp_export_ignores_multimedia_and_chatty_messages(self) -> None:
        result = parse_whatsapp_export(
            """
13/9/26, 8:10 - Laura Santa Cruz: Guten fucking Morgen
13/9/26, 8:10 - Cambiaste la descripción del grupo
17/9/26, 14:09 - Salvatore Lauricella: <Multimedia omitido>
17/9/26, 14:10 - Añadiste a Antonio Robert.
19.09.2026, 09:01 - Anna: 452
19.09.2026, 09:02 - Ben: umsteigen.app · Berlin 🚇 19. Sept. 390 / 500 · Umsteige-Profi 🟢–🟡–🟢–🟢–🟢
            """.strip()
        )

        self.assertEqual(len(result.records), 2)
        self.assertEqual([record.player for record in result.records], ["Anna", "Ben"])
        self.assertEqual([record.score for record in result.records], [452, 390])