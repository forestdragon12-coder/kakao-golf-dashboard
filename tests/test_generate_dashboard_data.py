"""
generate_dashboard_data.py 핵심 함수 테스트

- _load_previous_tab7: 파일 읽기 성공/실패/손상
- build_v5_data: skip_ai=True/False 분기
- get_metadata: 반환 구조 검증
- get_tab1, get_tab7: 빈 DB + 데이터 있는 DB
"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import generate_dashboard_data as gdd


# ─────────────────────────────────────────────
# 헬퍼: 인메모리 DB에 스키마 + 뷰 생성
# ─────────────────────────────────────────────
def _make_db():
    """인메모리 SQLite DB를 생성하고, generate_dashboard_data 가 사용하는
    테이블/뷰를 모두 세팅한 뒤 반환한다."""
    from db.database import SCHEMA, MIGRATIONS
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    # MIGRATION 컬럼 추가 (collected_at 등)
    existing_columns = {}
    for table, col, col_type in MIGRATIONS:
        if table not in existing_columns:
            existing_columns[table] = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in existing_columns[table]:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            existing_columns[table].add(col)
    db.commit()
    # weather 테이블 (별도 모듈에서 생성되지만 get_tab1 등에서 참조)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS weather_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_date TEXT NOT NULL,
            course_name TEXT NOT NULL,
            temperature REAL,
            rainfall REAL,
            humidity REAL,
            wind_speed REAL,
            precip_type INTEGER,
            sky_condition INTEGER,
            observed_at TEXT,
            UNIQUE(collected_date, course_name)
        );
        CREATE TABLE IF NOT EXISTS weather_forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            forecast_date TEXT NOT NULL,
            play_date TEXT NOT NULL,
            course_name TEXT NOT NULL,
            rain_prob INTEGER,
            temperature_high REAL,
            temperature_low REAL,
            precip_type INTEGER,
            sky_condition INTEGER,
            prev_rain_prob INTEGER,
            forecast_changed TEXT,
            UNIQUE(forecast_date, play_date, course_name)
        );
    """)
    return db


def _insert_snapshots(db, rows):
    """tee_time_snapshots 에 테스트 행 삽입.
    rows: list of dict (최소 키: course_name, collected_date, play_date, tee_time, price_krw)
    """
    for r in rows:
        db.execute("""
            INSERT INTO tee_time_snapshots
            (course_name, collected_date, collected_at, play_date, tee_time, price_krw,
             course_sub, membership_type, promo_flag, d_day, part_type, season, weekday_type,
             slot_identity_key, slot_group_key, slot_observation_key,
             slot_status, visible_flag, inventory_observed_flag)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r["course_name"],
            r["collected_date"],
            r.get("collected_at", r["collected_date"] + "T05:00:00"),
            r["play_date"],
            r["tee_time"],
            r["price_krw"],
            r.get("course_sub"),
            r.get("membership_type"),
            r.get("promo_flag", 0),
            r.get("d_day", 7),
            r.get("part_type", "1부"),
            r.get("season", "봄"),
            r.get("weekday_type", "평일"),
            # 유니크 키 생성
            f"sid_{r['course_name']}_{r['play_date']}_{r['tee_time']}_{r.get('course_sub','')}",
            f"sgk_{r['course_name']}_{r['play_date']}_{r['tee_time']}_{r.get('course_sub','')}",
            f"sok_{r['course_name']}_{r['collected_date']}_{r['play_date']}_{r['tee_time']}_{r.get('course_sub','')}",
            "available",
            1,
            1,
        ))
    db.commit()


def _insert_crawl_run(db, started_at, finished_at, status="success", total_rows=10):
    db.execute("""
        INSERT INTO crawl_runs (started_at, finished_at, status, total_rows)
        VALUES (?,?,?,?)
    """, (started_at, finished_at, status, total_rows))
    db.commit()


# ─────────────────────────────────────────────
# _load_previous_tab7 테스트
# ─────────────────────────────────────────────
class TestLoadPreviousTab7(unittest.TestCase):

    def test_loads_existing_json(self):
        """정상 JSON 파일에서 tab7 데이터를 읽는다."""
        tab7_payload = {"diagnostics": [{"course_name": "테스트CC"}], "data_days": 5}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"tab7": tab7_payload, "metadata": {}}, f, ensure_ascii=False)
            tmp_path = f.name

        with patch.object(gdd, "OUT_PATH", tmp_path):
            result = gdd._load_previous_tab7()

        self.assertEqual(result, tab7_payload)
        Path(tmp_path).unlink(missing_ok=True)

    def test_missing_file_returns_empty(self):
        """파일이 없으면 빈 dict 반환."""
        with patch.object(gdd, "OUT_PATH", "/nonexistent/path/dashboard_data.json"):
            result = gdd._load_previous_tab7()
        self.assertEqual(result, {})

    def test_corrupt_json_returns_empty(self):
        """손상된 JSON이면 빈 dict 반환."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json!!!}")
            tmp_path = f.name

        with patch.object(gdd, "OUT_PATH", tmp_path):
            result = gdd._load_previous_tab7()

        self.assertEqual(result, {})
        Path(tmp_path).unlink(missing_ok=True)

    def test_json_without_tab7_key_returns_empty(self):
        """JSON은 유효하지만 tab7 키가 없으면 빈 dict 반환."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"metadata": {}, "tab1": {}}, f)
            tmp_path = f.name

        with patch.object(gdd, "OUT_PATH", tmp_path):
            result = gdd._load_previous_tab7()

        self.assertEqual(result, {})
        Path(tmp_path).unlink(missing_ok=True)


# ─────────────────────────────────────────────
# get_metadata 테스트
# ─────────────────────────────────────────────
class TestGetMetadata(unittest.TestCase):

    def test_empty_db(self):
        """빈 DB에서 get_metadata 호출 시 기본 구조 반환."""
        db = _make_db()
        meta = gdd.get_metadata(db)

        self.assertIn("generated_at", meta)
        self.assertIn("latest_date", meta)
        self.assertIn("prev_date", meta)
        self.assertIn("all_dates", meta)
        self.assertIn("courses", meta)
        self.assertIn("member_courses", meta)
        self.assertIn("last_crawl", meta)

        self.assertIsNone(meta["latest_date"])
        self.assertIsNone(meta["prev_date"])
        self.assertEqual(meta["all_dates"], [])
        self.assertEqual(meta["courses"], [])
        db.close()

    def test_with_data(self):
        """데이터가 있는 DB에서 날짜/구장 목록 반환."""
        db = _make_db()
        _insert_snapshots(db, [
            {"course_name": "베르힐", "collected_date": "2026-03-15",
             "play_date": "2026-03-20", "tee_time": "07:00", "price_krw": 100000},
            {"course_name": "베르힐", "collected_date": "2026-03-16",
             "play_date": "2026-03-21", "tee_time": "07:30", "price_krw": 110000},
            {"course_name": "광주CC", "collected_date": "2026-03-16",
             "play_date": "2026-03-21", "tee_time": "08:00", "price_krw": 120000},
        ])
        meta = gdd.get_metadata(db)

        self.assertEqual(meta["latest_date"], "2026-03-16")
        self.assertEqual(meta["prev_date"], "2026-03-15")
        self.assertEqual(len(meta["all_dates"]), 2)
        self.assertIn("베르힐", meta["courses"])
        self.assertIn("광주CC", meta["courses"])
        self.assertIsNone(meta["last_crawl"])  # crawl_runs 미입력
        db.close()

    def test_with_crawl_run(self):
        """crawl_runs 데이터가 있으면 last_crawl 필드가 채워진다."""
        db = _make_db()
        _insert_snapshots(db, [
            {"course_name": "베르힐", "collected_date": "2026-03-16",
             "play_date": "2026-03-21", "tee_time": "07:00", "price_krw": 100000},
        ])
        _insert_crawl_run(db, "2026-03-16T05:00:00", "2026-03-16T05:10:00",
                          status="success", total_rows=50)

        meta = gdd.get_metadata(db)
        self.assertIsNotNone(meta["last_crawl"])
        self.assertEqual(meta["last_crawl"]["status"], "success")
        self.assertEqual(meta["last_crawl"]["total_rows"], 50)
        db.close()


# ─────────────────────────────────────────────
# build_v5_data 테스트 (탭 함수 모킹)
# ─────────────────────────────────────────────
class TestBuildV5Data(unittest.TestCase):

    def _mock_metadata(self):
        return {
            "generated_at": "2026-03-16 06:00",
            "latest_date": "2026-03-16",
            "prev_date": "2026-03-15",
            "all_dates": ["2026-03-15", "2026-03-16"],
            "courses": ["베르힐"],
            "member_courses": ["골드레이크", "해피니스"],
            "last_crawl": None,
        }

    @patch.object(gdd, "get_tab6_all", return_value={})
    @patch.object(gdd, "get_tab5b_all", return_value={})
    @patch.object(gdd, "get_tab5a", return_value={})
    @patch.object(gdd, "get_tab4", return_value={})
    @patch.object(gdd, "get_tab3_all", return_value={})
    @patch.object(gdd, "get_tab1_all", return_value={})
    @patch.object(gdd, "get_metadata")
    def test_skip_ai_uses_previous_tab7(self, mock_meta, *_mocks):
        """skip_ai=True 이면 get_tab7_all 대신 _load_previous_tab7 를 사용한다."""
        mock_meta.return_value = self._mock_metadata()
        previous_tab7 = {"2026-03-15": {"diagnostics": ["cached"]}}

        with patch.object(gdd, "_load_previous_tab7", return_value=previous_tab7) as mock_load, \
             patch.object(gdd, "get_tab7_all") as mock_gen:
            result = gdd.build_v5_data(MagicMock(), skip_ai=True)

        mock_load.assert_called_once()
        mock_gen.assert_not_called()
        self.assertEqual(result["tab7"], previous_tab7)

    @patch.object(gdd, "get_tab6_all", return_value={})
    @patch.object(gdd, "get_tab5b_all", return_value={})
    @patch.object(gdd, "get_tab5a", return_value={})
    @patch.object(gdd, "get_tab4", return_value={})
    @patch.object(gdd, "get_tab3_all", return_value={})
    @patch.object(gdd, "get_tab1_all", return_value={})
    @patch.object(gdd, "get_metadata")
    def test_no_skip_ai_generates_fresh_tab7(self, mock_meta, *_mocks):
        """skip_ai=False 이면 get_tab7_all 로 새로 생성한다."""
        mock_meta.return_value = self._mock_metadata()
        fresh_tab7 = {"2026-03-16": {"diagnostics": ["fresh"]}}

        with patch.object(gdd, "get_tab7_all", return_value=fresh_tab7) as mock_gen, \
             patch.object(gdd, "_load_previous_tab7") as mock_load:
            result = gdd.build_v5_data(MagicMock(), skip_ai=False)

        mock_gen.assert_called_once()
        mock_load.assert_not_called()
        self.assertEqual(result["tab7"], fresh_tab7)

    @patch.object(gdd, "get_tab6_all", return_value={})
    @patch.object(gdd, "get_tab5b_all", return_value={})
    @patch.object(gdd, "get_tab5a", return_value={})
    @patch.object(gdd, "get_tab4", return_value={})
    @patch.object(gdd, "get_tab3_all", return_value={})
    @patch.object(gdd, "get_tab1_all", return_value={})
    @patch.object(gdd, "get_metadata")
    def test_v5_contains_all_tabs(self, mock_meta, *_mocks):
        """build_v5_data 반환값에 필수 탭 키가 모두 존재한다."""
        mock_meta.return_value = self._mock_metadata()

        with patch.object(gdd, "get_tab7_all", return_value={}):
            result = gdd.build_v5_data(MagicMock(), skip_ai=False)

        for key in ["metadata", "tab1", "tab3", "tab4", "tab5a", "tab5b", "tab6", "tab7"]:
            self.assertIn(key, result, f"결과에 '{key}' 키가 없습니다")


# ─────────────────────────────────────────────
# get_tab1 테스트 (인메모리 DB)
# ─────────────────────────────────────────────
class TestGetTab1(unittest.TestCase):

    def test_empty_db(self):
        """빈 DB에서도 오류 없이 기본 구조를 반환한다."""
        db = _make_db()
        result = gdd.get_tab1(db, "2026-03-16", None)

        self.assertIn("kpi", result)
        self.assertIn("course_kpi", result)
        self.assertIn("price_changes", result)
        self.assertIn("consumption", result)
        db.close()

    def test_with_snapshots(self):
        """스냅샷 데이터가 있으면 KPI에 슬롯 수가 반영된다."""
        db = _make_db()
        _insert_snapshots(db, [
            {"course_name": "베르힐", "collected_date": "2026-03-16",
             "play_date": "2026-03-22", "tee_time": "07:00", "price_krw": 100000,
             "d_day": 6, "part_type": "1부"},
            {"course_name": "베르힐", "collected_date": "2026-03-16",
             "play_date": "2026-03-22", "tee_time": "07:07", "price_krw": 110000,
             "d_day": 6, "part_type": "1부"},
            {"course_name": "베르힐", "collected_date": "2026-03-16",
             "play_date": "2026-03-22", "tee_time": "11:00", "price_krw": 90000,
             "d_day": 6, "part_type": "2부", "promo_flag": 1},
        ])
        result = gdd.get_tab1(db, "2026-03-16", None)

        self.assertEqual(result["kpi"]["total_slots_today"], 3)
        self.assertEqual(result["kpi"]["total_promo_slots"], 1)
        # course_kpi 에 베르힐 포함 확인
        course_names = [c["course_name"] for c in result["course_kpi"]]
        self.assertIn("베르힐", course_names)
        db.close()

    def test_with_prev_date(self):
        """전일 데이터가 있으면 slot_delta 가 계산된다."""
        db = _make_db()
        # 전일: 4개 슬롯
        for i, t in enumerate(["07:00", "07:07", "07:14", "07:21"]):
            _insert_snapshots(db, [
                {"course_name": "베르힐", "collected_date": "2026-03-15",
                 "play_date": "2026-03-22", "tee_time": t, "price_krw": 100000},
            ])
        # 오늘: 2개 슬롯
        for t in ["07:00", "07:07"]:
            _insert_snapshots(db, [
                {"course_name": "베르힐", "collected_date": "2026-03-16",
                 "play_date": "2026-03-22", "tee_time": t, "price_krw": 100000},
            ])

        result = gdd.get_tab1(db, "2026-03-16", "2026-03-15")
        # 오늘 2 - 전일 4 = -2
        self.assertEqual(result["kpi"]["slot_delta"], -2)
        db.close()


# ─────────────────────────────────────────────
# get_tab7 테스트 (인메모리 DB)
# ─────────────────────────────────────────────
class TestGetTab7(unittest.TestCase):

    def test_empty_db(self):
        """빈 DB에서도 오류 없이 기본 구조를 반환한다."""
        db = _make_db()
        result = gdd.get_tab7(db, "2026-03-16", None)

        self.assertIn("diagnostics", result)
        self.assertIn("data_days", result)
        self.assertIn("rules_applicable", result)
        self.assertIn("rules_pending", result)
        self.assertIn("data_note", result)
        self.assertIsInstance(result["diagnostics"], list)
        self.assertEqual(len(result["diagnostics"]), 0)
        db.close()

    def test_with_snapshots(self):
        """스냅샷 데이터가 있으면 구장별 진단이 생성된다."""
        db = _make_db()
        # 여러 시간대 슬롯 삽입
        slots = []
        for t in ["07:00", "07:07", "07:14", "07:21", "11:00", "11:07", "14:00"]:
            slots.append({
                "course_name": "베르힐",
                "collected_date": "2026-03-16",
                "play_date": "2026-03-22",
                "tee_time": t,
                "price_krw": 100000,
                "d_day": 6,
                "part_type": "1부" if t < "11:00" else ("2부" if t < "14:00" else "오후"),
            })
        _insert_snapshots(db, slots)

        result = gdd.get_tab7(db, "2026-03-16", None)

        self.assertGreater(len(result["diagnostics"]), 0)
        diag_courses = [d["course_name"] for d in result["diagnostics"]]
        self.assertIn("베르힐", diag_courses)
        # 각 진단에는 findings 리스트가 있어야 함
        for diag in result["diagnostics"]:
            self.assertIn("findings", diag)
            self.assertIn("severity_max", diag)
        db.close()

    def test_tab7_all_delegates_to_tab7(self):
        """get_tab7_all 은 날짜별로 get_tab7 을 호출한다."""
        db = _make_db()
        _insert_snapshots(db, [
            {"course_name": "베르힐", "collected_date": "2026-03-15",
             "play_date": "2026-03-22", "tee_time": "07:00", "price_krw": 100000},
            {"course_name": "베르힐", "collected_date": "2026-03-16",
             "play_date": "2026-03-22", "tee_time": "07:07", "price_krw": 100000},
        ])

        result = gdd.get_tab7_all(db, ["2026-03-15", "2026-03-16"])

        self.assertIn("2026-03-15", result)
        self.assertIn("2026-03-16", result)
        # 각 날짜의 값도 유효한 tab7 구조
        for date_key in result:
            self.assertIn("diagnostics", result[date_key])
        db.close()


# ─────────────────────────────────────────────
# get_tab1_all 테스트
# ─────────────────────────────────────────────
class TestGetTab1All(unittest.TestCase):

    def test_generates_per_date(self):
        """날짜별로 tab1 데이터를 생성하고 date-keyed dict 를 반환한다."""
        db = _make_db()
        _insert_snapshots(db, [
            {"course_name": "베르힐", "collected_date": "2026-03-15",
             "play_date": "2026-03-22", "tee_time": "07:00", "price_krw": 100000},
            {"course_name": "베르힐", "collected_date": "2026-03-16",
             "play_date": "2026-03-22", "tee_time": "07:07", "price_krw": 110000},
        ])

        result = gdd.get_tab1_all(db, ["2026-03-15", "2026-03-16"])

        self.assertIn("2026-03-15", result)
        self.assertIn("2026-03-16", result)
        # 두 번째 날짜의 prev 는 첫 번째 날짜
        self.assertIn("kpi", result["2026-03-16"])
        db.close()


if __name__ == "__main__":
    unittest.main()
