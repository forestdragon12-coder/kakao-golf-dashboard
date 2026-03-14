import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db import database
from scraper.kakao_scraper import KakaoGolfScraper


class ParserTests(unittest.TestCase):
    def test_parse_blocks_extracts_price_promo_and_membership(self):
        sample = """06:54
75,000원
특가
동악
18홀
4인 필수
07:10
80,000원
카트비별도
밸리(대중제)
18홀
"""

        items = KakaoGolfScraper()._parse_blocks(sample)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["tee_time"], "06:54")
        self.assertEqual(items[0]["promo_flag"], 1)
        self.assertEqual(items[0]["promo_text"], "특가")
        self.assertEqual(items[0]["course_sub"], "동악")
        self.assertEqual(items[1]["price_type"], "카트비별도")
        self.assertEqual(items[1]["membership_type"], "대중제")


class DatabaseTests(unittest.TestCase):
    def test_insert_snapshots_counts_only_real_inserts(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = Path(tmpdir) / "golf.db"
                with patch.object(database, "DB_PATH", test_db):
                    await database.init_db()
                    row = {
                        "crawl_run_id": 1,
                        "course_id": 1,
                        "course_name": "테스트CC",
                        "collected_date": "2026-03-13",
                        "play_date": "2026-03-14",
                        "tee_time": "06:30",
                        "price_krw": 90000,
                        "course_sub": "동악",
                        "membership_type": None,
                        "promo_flag": 0,
                        "promo_text": None,
                        "pax_condition": None,
                        "price_type": None,
                        "d_day": 1,
                        "part_type": "1부",
                        "season": "봄",
                        "weekday_type": "토요일",
                        "hash_key": "unique-hash",
                        "slot_group_key": "unique-slot",
                    }

                    first = await database.insert_snapshots([row])
                    second = await database.insert_snapshots([row])

                    self.assertEqual(first, 1)
                    self.assertEqual(second, 0)

        asyncio.run(scenario())

    def test_init_db_backfills_missing_slot_group_key(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = Path(tmpdir) / "golf.db"
                with patch.object(database, "DB_PATH", test_db):
                    await database.init_db()
                    async with database.aiosqlite.connect(test_db) as db:
                        await db.execute(
                            """
                            INSERT INTO tee_time_snapshots
                            (crawl_run_id, course_id, course_name, collected_date, play_date,
                             tee_time, price_krw, course_sub, d_day, part_type, season, weekday_type, hash_key)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (1, 1, "테스트CC", "2026-03-13", "2026-03-14", "07:00", 85000, "동악", 1, "1부", "봄", "토요일", "legacy-hash"),
                        )
                        await db.commit()

                    await database.init_db()

                    async with database.aiosqlite.connect(test_db) as db:
                        async with db.execute(
                            """
                            SELECT slot_group_key, slot_identity_key, slot_status, listed_price_krw
                            FROM tee_time_snapshots
                            LIMIT 1
                            """
                        ) as cur:
                            row = await cur.fetchone()

                    self.assertIsNotNone(row[0])
                    self.assertIsNotNone(row[1])
                    self.assertEqual(row[2], "available")
                    self.assertEqual(row[3], 85000)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
