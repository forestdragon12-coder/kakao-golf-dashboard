"""
db/database.py 단위 테스트

test_parser_and_db.py 에서 이미 다루는 항목(기본 insert_snapshots 중복, backfill)과
겹치지 않도록 별도 함수·경로·엣지케이스에 집중한다.
"""

import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


# ──────────────────────────────────────────────────────────────
# 헬퍼: 임시 DB로 database 모듈을 격리하는 컨텍스트 매니저
# ──────────────────────────────────────────────────────────────

class _TempDB:
    """TemporaryDirectory + DB_PATH 패치를 묶어 반복 보일러플레이트 제거."""

    def __init__(self):
        self._tmpdir = None
        self._patcher = None
        self.path: Path | None = None

    async def __aenter__(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmpdir.name) / "golf.db"
        self._patcher = patch.object(database, "DB_PATH", self.path)
        self._patcher.start()
        await database.init_db()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._patcher.stop()
        self._tmpdir.cleanup()

    def connect(self):
        return database.aiosqlite.connect(self.path)


# ──────────────────────────────────────────────────────────────
# 1. 순수 함수(helper/utility) 테스트
# ──────────────────────────────────────────────────────────────

class TestMakeHash(unittest.TestCase):
    """make_hash: MD5 기반 수집 고유키"""

    def test_deterministic(self):
        h1 = database.make_hash("CC", "2026-03-17T05:00:00", "2026-03-20", "07:00", "A코스")
        h2 = database.make_hash("CC", "2026-03-17T05:00:00", "2026-03-20", "07:00", "A코스")
        self.assertEqual(h1, h2)

    def test_different_inputs_produce_different_hashes(self):
        h1 = database.make_hash("CC", "2026-03-17T05:00:00", "2026-03-20", "07:00")
        h2 = database.make_hash("CC", "2026-03-17T05:00:00", "2026-03-20", "07:30")
        self.assertNotEqual(h1, h2)

    def test_empty_course_sub_defaults(self):
        h1 = database.make_hash("CC", "2026-03-17T05:00:00", "2026-03-20", "07:00")
        h2 = database.make_hash("CC", "2026-03-17T05:00:00", "2026-03-20", "07:00", "")
        self.assertEqual(h1, h2)

    def test_collected_at_matters(self):
        """같은 날 다른 시간 수집 → 다른 해시"""
        h1 = database.make_hash("CC", "2026-03-17T05:00:00", "2026-03-20", "07:00")
        h2 = database.make_hash("CC", "2026-03-17T12:00:00", "2026-03-20", "07:00")
        self.assertNotEqual(h1, h2)

    def test_returns_valid_md5_hex(self):
        h = database.make_hash("CC", "2026-03-17T05:00:00", "2026-03-20", "07:00")
        self.assertEqual(len(h), 32)
        int(h, 16)  # ValueError if not valid hex


class TestMakeSlotKey(unittest.TestCase):
    """make_slot_key: collected_date 제외 → 날짜 간 동일 슬롯 추적"""

    def test_deterministic(self):
        k1 = database.make_slot_key("CC", "2026-03-20", "07:00", "A코스")
        k2 = database.make_slot_key("CC", "2026-03-20", "07:00", "A코스")
        self.assertEqual(k1, k2)

    def test_empty_sub_default(self):
        k1 = database.make_slot_key("CC", "2026-03-20", "07:00")
        k2 = database.make_slot_key("CC", "2026-03-20", "07:00", "")
        self.assertEqual(k1, k2)


class TestNormalizeCourseVariant(unittest.TestCase):
    """normalize_course_variant: 코스·멤버십·가격유형 결합"""

    def test_all_none_returns_standard(self):
        self.assertEqual(database.normalize_course_variant(), "standard")

    def test_single_value(self):
        self.assertEqual(database.normalize_course_variant(course_sub="동악"), "동악")

    def test_multiple_values_joined(self):
        result = database.normalize_course_variant(course_sub="동악", membership_type="대중제")
        self.assertEqual(result, "동악|대중제")

    def test_three_values_joined(self):
        result = database.normalize_course_variant("동악", "대중제", "카트비별도")
        self.assertEqual(result, "동악|대중제|카트비별도")

    def test_whitespace_stripped(self):
        result = database.normalize_course_variant(course_sub="  동악  ", membership_type=" 대중제 ")
        self.assertEqual(result, "동악|대중제")

    def test_empty_string_price_type_ignored(self):
        result = database.normalize_course_variant(course_sub="동악", price_type="  ")
        self.assertEqual(result, "동악")


class TestMakeSlotIdentityKey(unittest.TestCase):
    def test_deterministic(self):
        k1 = database.make_slot_identity_key(1, "2026-03-20", "07:00", "1부", "standard", "kakao_mobile")
        k2 = database.make_slot_identity_key(1, "2026-03-20", "07:00", "1부", "standard", "kakao_mobile")
        self.assertEqual(k1, k2)

    def test_none_part_type_treated_as_empty(self):
        k = database.make_slot_identity_key(1, "2026-03-20", "07:00", None, "standard", "kakao_mobile")
        raw = "1|2026-03-20|07:00||standard|kakao_mobile"
        expected = hashlib.md5(raw.encode()).hexdigest()
        self.assertEqual(k, expected)

    def test_none_source_channel_becomes_unknown(self):
        k = database.make_slot_identity_key(1, "2026-03-20", "07:00", "1부", "standard", None)
        raw = "1|2026-03-20|07:00|1부|standard|unknown_channel"
        expected = hashlib.md5(raw.encode()).hexdigest()
        self.assertEqual(k, expected)

    def test_none_variant_becomes_standard(self):
        k = database.make_slot_identity_key(1, "2026-03-20", "07:00", "1부", None, "kakao_mobile")
        raw = "1|2026-03-20|07:00|1부|standard|kakao_mobile"
        expected = hashlib.md5(raw.encode()).hexdigest()
        self.assertEqual(k, expected)


class TestMakeSlotObservationKey(unittest.TestCase):
    def test_deterministic(self):
        k1 = database.make_slot_observation_key("abc123", "2026-03-17T05:00:00")
        k2 = database.make_slot_observation_key("abc123", "2026-03-17T05:00:00")
        self.assertEqual(k1, k2)

    def test_different_time_produces_different_key(self):
        k1 = database.make_slot_observation_key("abc123", "2026-03-17T05:00:00")
        k2 = database.make_slot_observation_key("abc123", "2026-03-17T12:00:00")
        self.assertNotEqual(k1, k2)


class TestLatestSnapshotCte(unittest.TestCase):
    def test_default_params(self):
        cte = database.latest_snapshot_cte()
        self.assertIn("tee_time_snapshots", cte)
        self.assertIn("WHERE collected_date = ?", cte)

    def test_custom_table_and_params(self):
        cte = database.latest_snapshot_cte(date_params=":dt", table="my_table")
        self.assertIn("my_table", cte)
        self.assertIn("WHERE collected_date = :dt", cte)


# ──────────────────────────────────────────────────────────────
# 2. _prepare_snapshot_row 테스트
# ──────────────────────────────────────────────────────────────

class TestPrepareSnapshotRow(unittest.TestCase):
    """_prepare_snapshot_row: 파생 필드 자동 생성"""

    def _minimal_row(self, **overrides):
        base = {
            "crawl_run_id": 1,
            "course_id": 1,
            "course_name": "테스트CC",
            "collected_date": "2026-03-17",
            "play_date": "2026-03-20",
            "tee_time": "07:00",
            "course_sub": "동악",
            "price_krw": 90000,
            "d_day": 3,
            "part_type": "1부",
            "season": "봄",
            "weekday_type": "평일",
        }
        base.update(overrides)
        return base

    def test_generates_hash_key_when_missing(self):
        row = self._minimal_row()
        prepared = database._prepare_snapshot_row(row)
        self.assertIsNotNone(prepared["hash_key"])
        self.assertEqual(len(prepared["hash_key"]), 32)

    def test_preserves_existing_hash_key(self):
        row = self._minimal_row(hash_key="existing-hash")
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["hash_key"], "existing-hash")

    def test_generates_slot_group_key(self):
        row = self._minimal_row()
        prepared = database._prepare_snapshot_row(row)
        self.assertIsNotNone(prepared["slot_group_key"])

    def test_preserves_existing_slot_group_key(self):
        row = self._minimal_row(slot_group_key="existing-slot")
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["slot_group_key"], "existing-slot")

    def test_default_source_channel(self):
        row = self._minimal_row()
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["source_channel"], "kakao_mobile")

    def test_custom_source_channel_preserved(self):
        row = self._minimal_row(source_channel="naver")
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["source_channel"], "naver")

    def test_course_variant_generated(self):
        row = self._minimal_row(course_sub="동악", membership_type="대중제")
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["course_variant"], "동악|대중제")

    def test_course_variant_standard_when_no_sub(self):
        row = self._minimal_row(course_sub=None, membership_type=None, price_type=None)
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["course_variant"], "standard")

    def test_collected_at_fallback(self):
        """collected_at 없으면 collected_date + T05:00:00"""
        row = self._minimal_row()
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["collected_at"], "2026-03-17T05:00:00")

    def test_collected_at_preserved(self):
        row = self._minimal_row(collected_at="2026-03-17T12:30:00")
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["collected_at"], "2026-03-17T12:30:00")

    def test_default_slot_status(self):
        row = self._minimal_row()
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["slot_status"], "available")
        self.assertEqual(prepared["status_reason"], "observed_in_listing")

    def test_listed_price_falls_back_to_price_krw(self):
        row = self._minimal_row(price_krw=90000)
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["listed_price_krw"], 90000)
        self.assertEqual(prepared["sale_price_krw"], 90000)

    def test_listed_price_explicit(self):
        row = self._minimal_row(price_krw=90000, listed_price_krw=100000, sale_price_krw=85000)
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["listed_price_krw"], 100000)
        self.assertEqual(prepared["sale_price_krw"], 85000)

    def test_price_badge_falls_back_to_promo_text(self):
        row = self._minimal_row(promo_text="특가")
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["price_badge"], "특가")

    def test_price_changed_defaults(self):
        row = self._minimal_row()
        prepared = database._prepare_snapshot_row(row)
        self.assertEqual(prepared["price_changed_flag"], 0)
        self.assertEqual(prepared["price_change_count_7d"], 0)
        self.assertIsNone(prepared["price_change_delta_krw"])

    def test_slot_identity_key_generated(self):
        row = self._minimal_row()
        prepared = database._prepare_snapshot_row(row)
        self.assertIsNotNone(prepared["slot_identity_key"])
        self.assertEqual(len(prepared["slot_identity_key"]), 32)

    def test_slot_observation_key_generated(self):
        row = self._minimal_row()
        prepared = database._prepare_snapshot_row(row)
        self.assertIsNotNone(prepared["slot_observation_key"])
        self.assertEqual(len(prepared["slot_observation_key"]), 32)


# ──────────────────────────────────────────────────────────────
# 3. init_db — 테이블 생성·스키마 검증
# ──────────────────────────────────────────────────────────────

class TestInitDb(unittest.TestCase):
    def test_creates_all_core_tables(self):
        expected_tables = {
            "courses", "crawl_runs", "tee_time_snapshots", "daily_summary",
            "price_change_events", "price_response_metrics",
            "discount_events", "discount_response_metrics",
            "daily_course_metrics", "member_open_events",
            "baseline_models", "slot_status_history",
            "price_change_facts", "slot_velocity_facts",
            "course_segment_daily_facts", "competitive_segment_facts",
            "unsold_slots", "hourly_summary", "hourly_price_events",
        }

        async def scenario():
            async with _TempDB() as tdb:
                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ) as cur:
                        tables = {row[0] for row in await cur.fetchall()}
                for t in expected_tables:
                    self.assertIn(t, tables, f"테이블 누락: {t}")

        _run_async(scenario())

    def test_creates_latest_daily_snapshots_view(self):
        async def scenario():
            async with _TempDB() as tdb:
                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT name FROM sqlite_master WHERE type='view'"
                    ) as cur:
                        views = {row[0] for row in await cur.fetchall()}
                self.assertIn("latest_daily_snapshots", views)

        _run_async(scenario())

    def test_idempotent_double_init(self):
        """init_db 두 번 호출해도 오류 없음"""
        async def scenario():
            async with _TempDB() as tdb:
                await database.init_db()  # 두 번째 호출
                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT count(*) FROM sqlite_master WHERE type='table'"
                    ) as cur:
                        count = (await cur.fetchone())[0]
                self.assertGreater(count, 0)

        _run_async(scenario())

    def test_creates_indexes(self):
        async def scenario():
            async with _TempDB() as tdb:
                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
                    ) as cur:
                        indexes = {row[0] for row in await cur.fetchall()}
                # 핵심 인덱스 몇 개만 확인
                self.assertIn("idx_snap_play", indexes)
                self.assertIn("idx_snap_course", indexes)
                self.assertIn("idx_sum_play", indexes)

        _run_async(scenario())


# ──────────────────────────────────────────────────────────────
# 4. migrate_db — 컬럼 추가 안전성
# ──────────────────────────────────────────────────────────────

class TestMigrateDb(unittest.TestCase):
    def test_migration_adds_columns(self):
        """init_db가 SCHEMA+MIGRATION 실행 후 모든 컬럼 존재 확인"""
        async def scenario():
            async with _TempDB() as tdb:
                async with tdb.connect() as db:
                    async with db.execute("PRAGMA table_info(tee_time_snapshots)") as cur:
                        cols = {row[1] for row in await cur.fetchall()}
                # MIGRATIONS에 있는 컬럼 전부 확인
                for table, col, _ in database.MIGRATIONS:
                    if table == "tee_time_snapshots":
                        self.assertIn(col, cols, f"컬럼 누락: {col}")

        _run_async(scenario())

    def test_migrate_idempotent(self):
        """migrate_db 두 번 호출해도 오류 없음"""
        async def scenario():
            async with _TempDB() as tdb:
                await database.migrate_db()  # 두 번째 호출
                async with tdb.connect() as db:
                    async with db.execute("PRAGMA table_info(tee_time_snapshots)") as cur:
                        cols = {row[1] for row in await cur.fetchall()}
                self.assertIn("collected_at", cols)

        _run_async(scenario())


# ──────────────────────────────────────────────────────────────
# 5. get_or_create_course
# ──────────────────────────────────────────────────────────────

class TestGetOrCreateCourse(unittest.TestCase):
    def test_creates_new_course(self):
        async def scenario():
            async with _TempDB():
                cid = await database.get_or_create_course("뉴CC")
                self.assertIsInstance(cid, int)
                self.assertGreater(cid, 0)

        _run_async(scenario())

    def test_returns_same_id_for_duplicate(self):
        async def scenario():
            async with _TempDB():
                cid1 = await database.get_or_create_course("뉴CC")
                cid2 = await database.get_or_create_course("뉴CC")
                self.assertEqual(cid1, cid2)

        _run_async(scenario())

    def test_different_courses_get_different_ids(self):
        async def scenario():
            async with _TempDB():
                cid1 = await database.get_or_create_course("A코스")
                cid2 = await database.get_or_create_course("B코스")
                self.assertNotEqual(cid1, cid2)

        _run_async(scenario())

    def test_course_persisted_in_table(self):
        async def scenario():
            async with _TempDB() as tdb:
                await database.get_or_create_course("영구CC")
                async with tdb.connect() as db:
                    async with db.execute("SELECT name FROM courses WHERE name=?", ("영구CC",)) as cur:
                        row = await cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "영구CC")

        _run_async(scenario())


# ──────────────────────────────────────────────────────────────
# 6. start_run / finish_run
# ──────────────────────────────────────────────────────────────

class TestRunLifecycle(unittest.TestCase):
    def test_start_run_returns_id(self):
        async def scenario():
            async with _TempDB():
                run_id = await database.start_run()
                self.assertIsInstance(run_id, int)
                self.assertGreater(run_id, 0)

        _run_async(scenario())

    def test_start_run_sets_status_running(self):
        async def scenario():
            async with _TempDB() as tdb:
                run_id = await database.start_run()
                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT status, started_at FROM crawl_runs WHERE id=?", (run_id,)
                    ) as cur:
                        row = await cur.fetchone()
                self.assertEqual(row[0], "running")
                self.assertIsNotNone(row[1])

        _run_async(scenario())

    def test_start_run_aborts_previous_running(self):
        """새 run 시작 시 이전 running 상태인 run은 aborted 처리"""
        async def scenario():
            async with _TempDB() as tdb:
                old_id = await database.start_run()
                new_id = await database.start_run()

                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT status, error_msg FROM crawl_runs WHERE id=?", (old_id,)
                    ) as cur:
                        old = await cur.fetchone()
                    async with db.execute(
                        "SELECT status FROM crawl_runs WHERE id=?", (new_id,)
                    ) as cur:
                        new = await cur.fetchone()

                self.assertEqual(old[0], "aborted")
                self.assertIn("interrupted", old[1])
                self.assertEqual(new[0], "running")

        _run_async(scenario())

    def test_finish_run_success(self):
        async def scenario():
            async with _TempDB() as tdb:
                run_id = await database.start_run()
                await database.finish_run(run_id, "done", 42)

                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT status, total_rows, finished_at, error_msg FROM crawl_runs WHERE id=?",
                        (run_id,),
                    ) as cur:
                        row = await cur.fetchone()

                self.assertEqual(row[0], "done")
                self.assertEqual(row[1], 42)
                self.assertIsNotNone(row[2])
                self.assertIsNone(row[3])

        _run_async(scenario())

    def test_finish_run_with_error(self):
        async def scenario():
            async with _TempDB() as tdb:
                run_id = await database.start_run()
                await database.finish_run(run_id, "error", 0, error="타임아웃")

                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT status, error_msg FROM crawl_runs WHERE id=?", (run_id,)
                    ) as cur:
                        row = await cur.fetchone()
                self.assertEqual(row[0], "error")
                self.assertEqual(row[1], "타임아웃")

        _run_async(scenario())

    def test_sequential_run_ids_increase(self):
        async def scenario():
            async with _TempDB():
                id1 = await database.start_run()
                await database.finish_run(id1, "done", 0)
                id2 = await database.start_run()
                self.assertGreater(id2, id1)

        _run_async(scenario())


# ──────────────────────────────────────────────────────────────
# 7. upsert_daily_summary
# ──────────────────────────────────────────────────────────────

class TestUpsertDailySummary(unittest.TestCase):
    def _make_summary(self, **overrides):
        base = {
            "course_id": 1,
            "course_name": "테스트CC",
            "collected_date": "2026-03-17",
            "play_date": "2026-03-20",
            "d_day": 3,
            "remaining_total": 10,
            "remaining_part1": 5,
            "remaining_part2": 5,
            "min_price": 80000,
            "max_price": 120000,
            "avg_price": 95000.0,
            "promo_count": 2,
            "season": "봄",
            "weekday_type": "평일",
        }
        base.update(overrides)
        return base

    def test_insert_single_row(self):
        async def scenario():
            async with _TempDB() as tdb:
                await database.upsert_daily_summary([self._make_summary()])
                async with tdb.connect() as db:
                    async with db.execute("SELECT count(*) FROM daily_summary") as cur:
                        count = (await cur.fetchone())[0]
                self.assertEqual(count, 1)

        _run_async(scenario())

    def test_upsert_updates_existing(self):
        """동일 (course_name, collected_date, play_date) → UPDATE"""
        async def scenario():
            async with _TempDB() as tdb:
                row = self._make_summary(remaining_total=10)
                await database.upsert_daily_summary([row])

                updated = self._make_summary(remaining_total=7, min_price=70000)
                await database.upsert_daily_summary([updated])

                async with tdb.connect() as db:
                    async with db.execute("SELECT count(*) FROM daily_summary") as cur:
                        count = (await cur.fetchone())[0]
                    async with db.execute(
                        "SELECT remaining_total, min_price FROM daily_summary"
                    ) as cur:
                        row = await cur.fetchone()

                self.assertEqual(count, 1)  # 중복 아닌 upsert
                self.assertEqual(row[0], 7)
                self.assertEqual(row[1], 70000)

        _run_async(scenario())

    def test_different_play_dates_separate_rows(self):
        async def scenario():
            async with _TempDB() as tdb:
                rows = [
                    self._make_summary(play_date="2026-03-20"),
                    self._make_summary(play_date="2026-03-21"),
                ]
                await database.upsert_daily_summary(rows)

                async with tdb.connect() as db:
                    async with db.execute("SELECT count(*) FROM daily_summary") as cur:
                        count = (await cur.fetchone())[0]
                self.assertEqual(count, 2)

        _run_async(scenario())

    def test_empty_list_does_nothing(self):
        async def scenario():
            async with _TempDB() as tdb:
                await database.upsert_daily_summary([])
                async with tdb.connect() as db:
                    async with db.execute("SELECT count(*) FROM daily_summary") as cur:
                        count = (await cur.fetchone())[0]
                self.assertEqual(count, 0)

        _run_async(scenario())

    def test_promo_count_defaults_to_zero(self):
        async def scenario():
            async with _TempDB() as tdb:
                row = self._make_summary()
                del row["promo_count"]
                await database.upsert_daily_summary([row])
                async with tdb.connect() as db:
                    async with db.execute("SELECT promo_count FROM daily_summary") as cur:
                        val = (await cur.fetchone())[0]
                self.assertEqual(val, 0)

        _run_async(scenario())

    def test_multiple_courses_same_date(self):
        async def scenario():
            async with _TempDB() as tdb:
                rows = [
                    self._make_summary(course_name="A코스"),
                    self._make_summary(course_name="B코스"),
                ]
                await database.upsert_daily_summary(rows)
                async with tdb.connect() as db:
                    async with db.execute("SELECT count(*) FROM daily_summary") as cur:
                        count = (await cur.fetchone())[0]
                self.assertEqual(count, 2)

        _run_async(scenario())


# ──────────────────────────────────────────────────────────────
# 8. insert_snapshots — 확장 엣지케이스
# ──────────────────────────────────────────────────────────────

class TestInsertSnapshots(unittest.TestCase):
    def _make_snapshot(self, **overrides):
        base = {
            "crawl_run_id": 1,
            "course_id": 1,
            "course_name": "테스트CC",
            "collected_date": "2026-03-17",
            "play_date": "2026-03-20",
            "tee_time": "07:00",
            "price_krw": 90000,
            "course_sub": "동악",
            "membership_type": None,
            "promo_flag": 0,
            "promo_text": None,
            "pax_condition": None,
            "price_type": None,
            "d_day": 3,
            "part_type": "1부",
            "season": "봄",
            "weekday_type": "평일",
        }
        base.update(overrides)
        return base

    def test_empty_list_returns_zero(self):
        async def scenario():
            async with _TempDB():
                result = await database.insert_snapshots([])
                self.assertEqual(result, 0)

        _run_async(scenario())

    def test_insert_single_snapshot(self):
        async def scenario():
            async with _TempDB():
                count = await database.insert_snapshots([self._make_snapshot()])
                self.assertEqual(count, 1)

        _run_async(scenario())

    def test_duplicate_hash_key_ignored(self):
        """동일 hash_key → INSERT OR IGNORE → count 0"""
        async def scenario():
            async with _TempDB():
                row = self._make_snapshot(hash_key="fixed-hash-001")
                first = await database.insert_snapshots([row])
                second = await database.insert_snapshots([row])
                self.assertEqual(first, 1)
                self.assertEqual(second, 0)

        _run_async(scenario())

    def test_auto_generated_hash_key_deduplicates(self):
        """hash_key 없는 동일 행 → 자동 생성 해시가 동일 → 중복 방지"""
        async def scenario():
            async with _TempDB():
                row = self._make_snapshot()  # hash_key 자동 생성
                first = await database.insert_snapshots([row])
                second = await database.insert_snapshots([row])
                self.assertEqual(first, 1)
                self.assertEqual(second, 0)

        _run_async(scenario())

    def test_different_tee_times_both_inserted(self):
        async def scenario():
            async with _TempDB():
                rows = [
                    self._make_snapshot(tee_time="07:00"),
                    self._make_snapshot(tee_time="07:30"),
                ]
                count = await database.insert_snapshots(rows)
                self.assertEqual(count, 2)

        _run_async(scenario())

    def test_slot_status_history_also_populated(self):
        """스냅샷 삽입 시 slot_status_history에도 기록"""
        async def scenario():
            async with _TempDB() as tdb:
                await database.insert_snapshots([self._make_snapshot()])
                async with tdb.connect() as db:
                    async with db.execute("SELECT count(*) FROM slot_status_history") as cur:
                        count = (await cur.fetchone())[0]
                self.assertGreater(count, 0)

        _run_async(scenario())

    def test_multiple_snapshots_batch(self):
        async def scenario():
            async with _TempDB():
                rows = [
                    self._make_snapshot(tee_time=f"0{h}:00", course_sub=f"코스{i}")
                    for h in range(6, 9)
                    for i in range(3)
                ]
                count = await database.insert_snapshots(rows)
                self.assertEqual(count, 9)

        _run_async(scenario())

    def test_promo_flag_stored(self):
        async def scenario():
            async with _TempDB() as tdb:
                row = self._make_snapshot(promo_flag=1, promo_text="특가")
                await database.insert_snapshots([row])
                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT promo_flag, promo_text FROM tee_time_snapshots"
                    ) as cur:
                        result = await cur.fetchone()
                self.assertEqual(result[0], 1)
                self.assertEqual(result[1], "특가")

        _run_async(scenario())

    def test_none_price_krw_allowed(self):
        """price_krw가 None이어도 삽입 가능"""
        async def scenario():
            async with _TempDB():
                row = self._make_snapshot(price_krw=None)
                count = await database.insert_snapshots([row])
                self.assertEqual(count, 1)

        _run_async(scenario())

    def test_different_collected_at_not_duplicate(self):
        """같은 슬롯이라도 collected_at이 다르면 별도 스냅샷"""
        async def scenario():
            async with _TempDB():
                row1 = self._make_snapshot(collected_at="2026-03-17T05:00:00")
                row2 = self._make_snapshot(collected_at="2026-03-17T12:00:00")
                count = await database.insert_snapshots([row1])
                count2 = await database.insert_snapshots([row2])
                self.assertEqual(count, 1)
                self.assertEqual(count2, 1)

        _run_async(scenario())

    def test_derived_fields_persisted(self):
        """source_channel, course_variant 등 파생 필드가 DB에 저장됨"""
        async def scenario():
            async with _TempDB() as tdb:
                row = self._make_snapshot(
                    course_sub="밸리", membership_type="대중제",
                )
                await database.insert_snapshots([row])
                async with tdb.connect() as db:
                    async with db.execute(
                        "SELECT source_channel, course_variant, slot_status, listed_price_krw "
                        "FROM tee_time_snapshots"
                    ) as cur:
                        result = await cur.fetchone()
                self.assertEqual(result[0], "kakao_mobile")
                self.assertEqual(result[1], "밸리|대중제")
                self.assertEqual(result[2], "available")
                self.assertEqual(result[3], 90000)  # listed_price falls back to price_krw

        _run_async(scenario())


if __name__ == "__main__":
    unittest.main()
