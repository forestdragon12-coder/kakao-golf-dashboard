"""
시간별 수집 분석기 — 매시간 수집 후 경량 실행

1. hourly_summary: 수집 시점별 잔여석/가격 요약
2. hourly_price_events: 직전 수집 대비 가격 변동 감지
"""
import aiosqlite
from datetime import date
from loguru import logger

from db.database import DB_PATH


async def build_hourly_summary_from_db(collected_at: str):
    """DB에서 해당 collected_at 스냅샷을 집계하여 hourly_summary 생성."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT
                course_name, play_date, collected_date, d_day,
                COUNT(*) AS remaining,
                MIN(price_krw) AS min_price,
                CAST(ROUND(AVG(price_krw), 0) AS INTEGER) AS avg_price,
                MAX(price_krw) AS max_price,
                SUM(CASE WHEN promo_flag = 1 THEN 1 ELSE 0 END) AS promo_count
            FROM tee_time_snapshots
            WHERE collected_at = ? AND price_krw IS NOT NULL
            GROUP BY course_name, play_date
        """, (collected_at,)) as cur:
            rows = await cur.fetchall()

        if not rows:
            return 0

        for r in rows:
            await db.execute("""
                INSERT OR REPLACE INTO hourly_summary
                (collected_at, collected_date, course_name, play_date, d_day,
                 remaining, min_price, avg_price, max_price, promo_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                collected_at, r["collected_date"], r["course_name"], r["play_date"],
                r["d_day"], r["remaining"], r["min_price"], r["avg_price"],
                r["max_price"], r["promo_count"],
            ))

        await db.commit()

    logger.debug(f"[시간별] hourly_summary {len(rows)}건 저장 ({collected_at})")
    return len(rows)


async def detect_hourly_price_changes(collected_at: str, collected_date: str = None):
    """직전 수집 대비 가격 변동 감지 → hourly_price_events 저장."""
    if collected_date is None:
        collected_date = date.today().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 직전 수집 시각 찾기 (같은 날, 현재보다 이전)
        cur = await db.execute("""
            SELECT DISTINCT collected_at FROM tee_time_snapshots
            WHERE collected_date = ? AND collected_at < ?
            ORDER BY collected_at DESC LIMIT 1
        """, (collected_date, collected_at))
        prev_row = await cur.fetchone()

        if not prev_row:
            return 0

        prev_at = prev_row[0]

        # 기존 이벤트 삭제 (멱등성)
        await db.execute(
            "DELETE FROM hourly_price_events WHERE detected_at = ?",
            (collected_at,),
        )

        # 같은 슬롯의 가격 비교
        query = """
            SELECT
                n.course_name,
                n.play_date,
                n.tee_time,
                n.course_sub,
                COALESCE(n.slot_identity_key, n.slot_group_key) AS slot_identity_key,
                COALESCE(p.sale_price_krw, p.listed_price_krw, p.price_krw) AS old_price,
                COALESCE(n.sale_price_krw, n.listed_price_krw, n.price_krw) AS new_price,
                p.promo_flag AS old_promo,
                n.promo_flag AS new_promo
            FROM tee_time_snapshots n
            JOIN tee_time_snapshots p
              ON COALESCE(n.slot_identity_key, n.slot_group_key) = COALESCE(p.slot_identity_key, p.slot_group_key)
             AND n.collected_at = ?
             AND p.collected_at = ?
            WHERE COALESCE(n.sale_price_krw, n.listed_price_krw, n.price_krw) IS NOT NULL
              AND COALESCE(p.sale_price_krw, p.listed_price_krw, p.price_krw) IS NOT NULL
              AND (
                  COALESCE(n.sale_price_krw, n.listed_price_krw, n.price_krw)
                  != COALESCE(p.sale_price_krw, p.listed_price_krw, p.price_krw)
                  OR n.promo_flag != p.promo_flag
              )
        """

        async with db.execute(query, (collected_at, prev_at)) as cur:
            changed = await cur.fetchall()

        event_count = 0
        for row in changed:
            old_p = row["old_price"]
            new_p = row["new_price"]
            delta = new_p - old_p
            delta_pct = round(delta / old_p * 100, 2) if old_p else 0

            if row["old_promo"] == 0 and row["new_promo"] == 1:
                event_type = "특가부착"
            elif row["old_promo"] == 1 and row["new_promo"] == 0:
                event_type = "특가해제"
            elif delta < 0:
                event_type = "인하"
            else:
                event_type = "인상"

            await db.execute("""
                INSERT INTO hourly_price_events
                (detected_at, prev_collected_at, course_name, play_date,
                 tee_time, course_sub, slot_identity_key,
                 old_price_krw, new_price_krw, delta_krw, delta_pct,
                 event_type, old_promo_flag, new_promo_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                collected_at, prev_at, row["course_name"], row["play_date"],
                row["tee_time"], row["course_sub"], row["slot_identity_key"],
                old_p, new_p, delta, delta_pct,
                event_type, row["old_promo"], row["new_promo"],
            ))
            event_count += 1

        await db.commit()

    if event_count > 0:
        logger.info(f"[시간별] 가격변동 {event_count}건 감지 ({prev_at} → {collected_at})")
    return event_count
