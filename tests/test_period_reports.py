import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analytics import report_payload_builder
from analytics import strategy_profile
from analytics.report_generator import (
    render_monthly_text_report,
    render_weekly_text_report,
    render_yearly_text_report,
)
from db import database


class PeriodReportTests(unittest.TestCase):
    def test_period_payloads_and_renderers_handle_partial_data(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = Path(tmpdir) / "golf.db"
                with patch.object(database, "DB_PATH", test_db), patch.object(report_payload_builder, "DB_PATH", test_db), patch.object(strategy_profile, "DB_PATH", test_db):
                    await database.init_db()

                    async with database.aiosqlite.connect(test_db) as db:
                        await db.executemany(
                            """
                            INSERT INTO daily_course_metrics
                            (report_date, course_name, play_date, season, weekday_type, part_type,
                             membership_type, d_day, observed_open_slots,
                             avg_price_krw, min_price_krw, max_price_krw,
                             promo_slot_count, greenfee_slot_count, cart_extra_slot_count,
                             pax_3plus_count, discount_event_flag, member_open_flag, confidence_score)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            [
                                ("2026-03-11", "베르힐", "2026-03-20", "봄", "평일", "1부", None, 9, 2, 120000, 110000, 130000, 0, 2, 0, 0, 0, None, None),
                                ("2026-03-12", "베르힐", "2026-03-21", "봄", "평일", "1부", None, 10, 3, 121000, 111000, 131000, 0, 3, 0, 0, 0, None, None),
                                ("2026-03-13", "푸른솔장성", "2026-03-22", "봄", "평일", "2부", None, 11, 8, 70000, 50000, 90000, 5, 8, 0, 2, 1, None, None),
                            ],
                        )
                        await db.commit()

                    weekly = await report_payload_builder.build_weekly_report_payload("2026-03-13")
                    monthly = await report_payload_builder.build_monthly_report_payload("2026-03-13")
                    yearly = await report_payload_builder.build_yearly_report_payload("2026-03-13")

                    weekly_text = render_weekly_text_report(weekly)
                    monthly_text = render_monthly_text_report(monthly)
                    yearly_text = render_yearly_text_report(yearly)

                    self.assertEqual(weekly["report_type"], "weekly")
                    self.assertEqual(monthly["report_type"], "monthly")
                    self.assertEqual(yearly["report_type"], "yearly")
                    self.assertIn("주간 총평", weekly_text)
                    self.assertIn("월간 개요", monthly_text)
                    self.assertIn("연간 총평", yearly_text)
                    self.assertTrue(weekly["evidence"]["strategy_profiles"])
                    self.assertIn("weekly_change_section", weekly)
                    self.assertIn("current_structure_section", weekly)
                    self.assertIn("berhill_focus_section", weekly)
                    self.assertIn("action_section", weekly)
                    self.assertTrue(weekly["risks"])
                    self.assertTrue(monthly["risks"])
                    self.assertTrue(yearly["risks"])

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
