import unittest

from analytics.report_payload_builder import build_daily_report_payload


class ReportPayloadBuilderTests(unittest.TestCase):
    def test_build_daily_report_payload_shapes_core_sections(self):
        payload = build_daily_report_payload(
            report_date="2026-03-13",
            total_rows=123,
            change_summary={
                "total": 2,
                "by_type": {"인하": 1, "인상": 0, "특가부착": 1, "특가해제": 0},
                "biggest_cut": {
                    "course_name": "테스트CC",
                    "play_date": "2026-03-20",
                    "tee_time": "07:10",
                    "delta_price_krw": -10000,
                },
            },
            agg_summary={
                "courses": {
                    "테스트CC": {"total_slots": 10, "promo_slots": 3, "avg_price": 90000, "min_price": 80000},
                    "베르힐": {"total_slots": 8, "promo_slots": 0, "avg_price": 115000, "min_price": 110000},
                },
                "member_opens_today": [],
            },
            rule_summary={
                "high_defense": [{"course_name": "베르힐", "play_date": "2026-03-20", "part_type": "1부", "open_slots": 2}],
                "repeat_discount": [{"course_name": "테스트CC", "play_date": "2026-03-21", "part_type": "2부", "signal": "당일특가집중"}],
                "price_response": [],
                "premium_candidates": [],
                "member_open_alerts": [],
            },
        )

        self.assertEqual(payload["report_type"], "daily")
        self.assertEqual(payload["summary"]["total_rows"], 123)
        self.assertEqual(payload["summary"]["total_courses"], 2)
        self.assertEqual(payload["summary"]["promo_slots"], 3)
        self.assertEqual(payload["evidence"]["price_change_watch"]["total"], 2)
        self.assertEqual(len(payload["evidence"]["course_board"]), 2)
        self.assertIn("management_snapshot", payload["summary"])
        self.assertIn("course_comparisons", payload["evidence"])
        self.assertIn("composite_issues", payload["evidence"])
        self.assertIn("strategy_profiles", payload["evidence"])
        self.assertIn("metric_glossary", payload["evidence"])
        self.assertIn("top_summary_section", payload)
        self.assertTrue(any(item["course_name"] == "테스트CC" for item in payload["course_focus"]))
        self.assertTrue(payload["risks"])
        self.assertTrue(payload["llm_constraints"])


if __name__ == "__main__":
    unittest.main()
