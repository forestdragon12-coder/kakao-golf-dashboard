import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analytics import strategy_profile
from db import database


class StrategyProfileTests(unittest.TestCase):
    def test_build_strategy_profiles_returns_stable_schema_with_sparse_data(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = Path(tmpdir) / "golf.db"
                with patch.object(database, "DB_PATH", test_db), patch.object(strategy_profile, "DB_PATH", test_db):
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
                                ("2026-03-10", "베르힐", "2026-03-20", "봄", "평일", "1부", None, 10, 8, 110000, 100000, 120000, 0, 8, 0, 0, 0, None, None),
                                ("2026-03-13", "베르힐", "2026-03-20", "봄", "평일", "1부", None, 7, 5, 110000, 100000, 120000, 0, 5, 0, 0, 0, None, None),
                            ],
                        )
                        await db.commit()

                    result = await strategy_profile.build_strategy_profiles("2026-03-10", "2026-03-13")

                    self.assertIn("profiles", result)
                    self.assertIn("glossary", result)
                    self.assertEqual(len(result["profiles"]), 1)

                    profile = result["profiles"][0]
                    self.assertEqual(profile["course_name"], "베르힐")
                    self.assertIn("base_tier", profile)
                    self.assertIn("discount_dependency", profile)
                    self.assertIn("discount_amplification", profile)
                    self.assertIn(profile["base_tier"]["grade"], {"A", "B+", "B", "C+", "C", "D", "N/A"})
                    self.assertIn(profile["discount_dependency"]["label"], {"높음", "보통", "낮음", "판단보류"})
                    self.assertIn(profile["discount_amplification"]["label"], {"높음", "보통", "낮음", "판단보류"})

        asyncio.run(scenario())

    def test_build_strategy_profiles_uses_market_comparison_when_competitors_exist(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = Path(tmpdir) / "golf.db"
                with patch.object(database, "DB_PATH", test_db), patch.object(strategy_profile, "DB_PATH", test_db):
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
                                ("2026-03-10", "자사", "2026-03-20", "봄", "평일", "1부", None, 10, 10, 100000, 90000, 110000, 0, 10, 0, 0, 0, None, None),
                                ("2026-03-13", "자사", "2026-03-20", "봄", "평일", "1부", None, 7, 6, 100000, 90000, 110000, 0, 6, 0, 0, 0, None, None),
                                ("2026-03-13", "타사A", "2026-03-20", "봄", "평일", "1부", None, 7, 9, 98000, 90000, 105000, 0, 9, 0, 0, 0, None, None),
                                ("2026-03-16", "타사A", "2026-03-20", "봄", "평일", "1부", None, 4, 8, 98000, 90000, 105000, 0, 8, 0, 0, 0, None, None),
                            ],
                        )
                        await db.execute(
                            """
                            INSERT INTO discount_response_metrics
                            (event_date, course_name, play_date, part_type, membership_type, event_type,
                             baseline_open_slots, open_slots_d1, open_slots_d3, open_slots_d5, open_slots_d7,
                             drop_rate_d1, drop_rate_d3, drop_rate_d5, drop_rate_d7,
                             control_part_type, control_drop_rate_d3, control_drop_rate_d7,
                             historical_drop_rate_d3, historical_drop_rate_d7,
                             response_score, response_grade, confidence_grade, holdout_reason)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                "2026-03-13", "자사", "2026-03-20", "1부", None, "가격인하형",
                                6, None, 0, None, None,
                                None, 1.0, None, None,
                                None, None, None,
                                None, None,
                                80.0, "강함", "medium", None,
                            ),
                        )
                        await db.commit()

                    result = await strategy_profile.build_strategy_profiles("2026-03-10", "2026-03-16")
                    profile_map = {item["course_name"]: item for item in result["profiles"]}
                    self.assertIn("자사", profile_map)

                    amplification = profile_map["자사"]["discount_amplification"]
                    self.assertIsNotNone(amplification["value"])
                    self.assertEqual(amplification["is_provisional"], False)
                    self.assertIn(amplification["confidence"], {"low", "medium"})
                    self.assertIn(amplification["label"], {"높음", "보통", "낮음", "판단보류"})

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
