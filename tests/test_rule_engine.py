import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analytics import rule_engine
from db import database


def _run_async(coro):
    """asyncio.run() 대체: 이미 실행 중인 이벤트 루프가 있어도 동작"""
    try:
        asyncio.get_running_loop()
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except RuntimeError:
        return asyncio.run(coro)


class RuleEngineTests(unittest.TestCase):
    def test_evaluate_rules_detects_core_signals(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = Path(tmpdir) / "golf.db"
                with patch.object(database, "DB_PATH", test_db), patch.object(rule_engine, "DB_PATH", test_db):
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
                                (
                                    "2026-03-13", "테스트CC", "2026-03-20", "봄", "평일", "1부",
                                    None, 7, 2, 150000, 140000, 160000, 0, 2, 0, 0, 0, None, None,
                                ),
                                (
                                    "2026-03-13", "테스트CC", "2026-03-20", "봄", "평일", "2부",
                                    None, 7, 8, 90000, 80000, 100000, 6, 8, 0, 4, 1, None, None,
                                ),
                                (
                                    "2026-03-13", "해피니스", "2026-03-21", "봄", "토요일", "1부",
                                    "대중제", 8, 6, 70000, 65000, 75000, 4, 6, 0, 2, 1, 1, None,
                                ),
                                (
                                    "2026-03-11", "반복CC", "2026-03-21", "봄", "토요일", "2부",
                                    None, 10, 7, 90000, 85000, 95000, 3, 7, 0, 0, 1, None, None,
                                ),
                                (
                                    "2026-03-12", "반복CC", "2026-03-22", "봄", "토요일", "2부",
                                    None, 11, 6, 91000, 86000, 96000, 2, 6, 0, 0, 1, None, None,
                                ),
                                (
                                    "2026-03-13", "반복CC", "2026-03-23", "봄", "토요일", "2부",
                                    None, 12, 5, 92000, 87000, 97000, 2, 5, 0, 0, 1, None, None,
                                ),
                            ],
                        )
                        await db.execute(
                            """
                            INSERT INTO member_open_events
                            (course_name, play_date, detected_at, member_slot_count, member_sub_names,
                             min_price_krw, max_price_krw, promo_flag)
                            VALUES (?,?,?,?,?,?,?,?)
                            """,
                            ("해피니스", "2026-03-21", "2026-03-13", 4, '["해피(회원제)"]', 88000, 105000, 1),
                        )
                        await db.commit()

                    summary = await rule_engine.evaluate_rules("2026-03-13")

                    self.assertTrue(any(item["course_name"] == "테스트CC" for item in summary["high_defense"]))
                    self.assertTrue(any(item["course_name"] == "테스트CC" for item in summary["premium_candidates"]))
                    self.assertTrue(any(item["course_name"] == "반복CC" for item in summary["repeat_discount"]))
                    self.assertTrue(any(item["course_name"] == "해피니스" for item in summary["member_open_alerts"]))
                    self.assertIn("actions", summary)
                    self.assertIn("signals", summary)
                    self.assertIn("summary_counts", summary)
                    self.assertIn("risks", summary)
                    self.assertTrue(any(item["action"] == "가격유지" for item in summary["actions"]))
                    self.assertTrue(any(item["action"] == "공급증가주의" for item in summary["actions"]))
                    self.assertTrue(all("priority_rank" in item for item in summary["actions"]))

        _run_async(scenario())


if __name__ == "__main__":
    unittest.main()
