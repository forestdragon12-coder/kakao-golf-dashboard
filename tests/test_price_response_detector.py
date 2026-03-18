import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analytics import price_response_detector
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


class PriceResponseDetectorTests(unittest.TestCase):
    def test_detect_price_responses_tracks_segment_level_inventory_flow(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = Path(tmpdir) / "golf.db"
                with patch.object(database, "DB_PATH", test_db), patch.object(price_response_detector, "DB_PATH", test_db):
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
                                ("2026-03-12", "테스트CC", "2026-03-20", "봄", "평일", "1부", None, 8, 10, 100000, 90000, 110000, 0, 10, 0, 0, 0, None, None),
                                ("2026-03-12", "테스트CC", "2026-03-20", "봄", "평일", "2부", None, 8, 8, 95000, 90000, 100000, 0, 8, 0, 0, 0, None, None),
                                ("2026-03-13", "테스트CC", "2026-03-20", "봄", "평일", "1부", None, 7, 10, 85000, 80000, 95000, 4, 10, 0, 0, 1, None, None),
                                ("2026-03-13", "테스트CC", "2026-03-20", "봄", "평일", "2부", None, 7, 8, 95000, 90000, 100000, 0, 8, 0, 0, 0, None, None),
                                ("2026-03-16", "테스트CC", "2026-03-20", "봄", "평일", "1부", None, 4, 4, 85000, 80000, 90000, 2, 4, 0, 0, 1, None, None),
                                ("2026-03-16", "테스트CC", "2026-03-20", "봄", "평일", "2부", None, 4, 7, 95000, 90000, 100000, 0, 7, 0, 0, 0, None, None),
                                ("2026-03-20", "테스트CC", "2026-03-20", "봄", "평일", "1부", None, 0, 1, 85000, 80000, 90000, 1, 1, 0, 0, 1, None, None),
                                ("2026-03-20", "테스트CC", "2026-03-20", "봄", "평일", "2부", None, 0, 6, 95000, 90000, 100000, 0, 6, 0, 0, 0, None, None),
                            ],
                        )
                        await db.commit()

                    count = await price_response_detector.detect_price_responses("2026-03-13")
                    self.assertEqual(count, 1)

                    async with database.aiosqlite.connect(test_db) as db:
                        async with db.execute(
                            """
                            SELECT event_type, baseline_open_slots, open_slots_d3, open_slots_d7,
                                   drop_rate_d3, drop_rate_d7, control_drop_rate_d3,
                                   response_grade, confidence_grade
                            FROM discount_response_metrics
                            """
                        ) as cur:
                            row = await cur.fetchone()

                    self.assertEqual(row[0], "복합할인형")
                    self.assertEqual(row[1], 10)
                    self.assertEqual(row[2], 4)
                    self.assertEqual(row[3], 1)
                    self.assertEqual(row[4], 0.6)
                    self.assertEqual(row[5], 0.9)
                    self.assertEqual(row[6], 0.125)
                    self.assertEqual(row[7], "강함")
                    self.assertEqual(row[8], "high")

        _run_async(scenario())


if __name__ == "__main__":
    unittest.main()
