"""
미판매 슬롯 추적기
매일 수집 후 실행 — 전날 경기의 미판매 슬롯을 기록
"""
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent.parent / "data" / "golf.db"


def record_unsold_slots(report_date=None):
    """전날 경기(play_date)의 미판매 슬롯을 unsold_slots 테이블에 기록.

    report_date: 수집일 (기본: 오늘)
    미판매 = report_date 전날이 play_date인데, 마지막 수집에 아직 남아있던 슬롯
    """
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    if not report_date:
        report_date = datetime.now().strftime("%Y-%m-%d")

    prev_collected = (datetime.strptime(report_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    count = db.execute(
        "SELECT COUNT(*) FROM tee_time_snapshots WHERE collected_date=? AND play_date=?",
        (prev_collected, report_date)).fetchone()[0]
    if count == 0:
        db.close()
        return 0

    unsold = [dict(r) for r in db.execute("""
        WITH latest_snap AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY COALESCE(slot_identity_key, slot_group_key)
                ORDER BY collected_at DESC
            ) AS _rn
            FROM tee_time_snapshots
            WHERE collected_date = ? AND play_date = ?
        )
        SELECT course_name, course_sub, membership_type, tee_time,
               price_krw, part_type, weekday_type, promo_flag, slot_group_key
        FROM latest_snap
        WHERE _rn = 1
        ORDER BY course_name, tee_time
    """, (prev_collected, report_date)).fetchall()]

    if not unsold:
        db.close()
        return 0

    # 기상 원인 조회
    weather_cause_map = {}
    try:
        wrows = [dict(r) for r in db.execute("""
            SELECT play_date, forecast_changed, rain_prob
            FROM weather_forecasts
            WHERE play_date = ? AND forecast_date <= ?
            ORDER BY forecast_date DESC LIMIT 1
        """, (report_date, report_date)).fetchall()]
        for wr in wrows:
            if wr.get("forecast_changed") == "악화" or (wr.get("rain_prob") and wr["rain_prob"] >= 60):
                weather_cause_map[wr["play_date"]] = "우천예보"
            elif wr.get("forecast_changed") == "호전":
                weather_cause_map[wr["play_date"]] = "맑음전환"
    except Exception:
        pass

    inserted = 0
    for slot in unsold:
        row = db.execute(
            "SELECT MIN(collected_date) FROM tee_time_snapshots WHERE slot_group_key=?",
            (slot["slot_group_key"],)).fetchone()
        first_seen = row[0] if row else prev_collected

        days_on_market = 0
        if first_seen:
            try:
                d1 = datetime.strptime(first_seen, "%Y-%m-%d")
                d2 = datetime.strptime(prev_collected, "%Y-%m-%d")
                days_on_market = (d2 - d1).days + 1
            except:
                days_on_market = 1

        try:
            w_cause = weather_cause_map.get(report_date)
            db.execute("""
                INSERT OR IGNORE INTO unsold_slots
                (play_date, course_name, course_sub, membership_type, tee_time,
                 price_krw, part_type, weekday_type, promo_flag,
                 first_seen_date, last_seen_date, days_on_market,
                 slot_group_key, recorded_date, weather_cause)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_date, slot["course_name"], slot["course_sub"],
                slot["membership_type"], slot["tee_time"],
                slot["price_krw"], slot["part_type"], slot["weekday_type"],
                slot["promo_flag"],
                first_seen, prev_collected, days_on_market,
                slot["slot_group_key"], report_date, w_cause,
            ))
            inserted += 1
        except Exception:
            pass

    db.commit()
    db.close()
    return inserted
