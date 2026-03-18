"""
전일 대비 가격 변동 감지 → price_change_events / price_change_facts 저장

슬롯 동일성은 slot_identity_key를 우선 사용하고, legacy slot_group_key와 병행 호환한다.
이벤트 유형: 인하 / 인상 / 특가부착 / 특가해제
멱등성: detected_at 날짜 기존 레코드 삭제 후 재삽입
"""
import aiosqlite
from datetime import date, timedelta
from loguru import logger

from db.database import DB_PATH


async def detect_price_changes(report_date: str = None) -> int:
    """
    report_date(당일) vs report_date-1(전일) 스냅샷 비교
    → price_change_events 삽입 (기존 당일 레코드 초기화 후 재생성)

    Args:
        report_date: 'YYYY-MM-DD' 형식. None이면 오늘 날짜 사용

    Returns:
        감지된 가격 변동 이벤트 수
    """
    if report_date is None:
        report_date = date.today().isoformat()

    prev_date = (date.fromisoformat(report_date) - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # ── 당일 이벤트 초기화 (멱등성 보장)
        await db.execute("DELETE FROM price_change_events WHERE detected_at = ?", (report_date,))
        await db.execute("DELETE FROM price_change_facts WHERE change_detected_at = ?", (report_date,))

        # ── 당일 vs 전일: slot_identity_key 기준 동일 슬롯 JOIN
        #    시간별 수집 시 같은 날 여러 행 → 최신 스냅샷만 비교
        query = """
            WITH today_latest AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(slot_identity_key, slot_group_key)
                    ORDER BY collected_at DESC
                ) AS _rn
                FROM tee_time_snapshots WHERE collected_date = ?
            ),
            prev_latest AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(slot_identity_key, slot_group_key)
                    ORDER BY collected_at DESC
                ) AS _rn
                FROM tee_time_snapshots WHERE collected_date = ?
            )
            SELECT
                t.id             AS snapshot_id,
                t.course_id,
                t.course_name,
                t.play_date,
                t.tee_time,
                t.part_type,
                t.course_sub,
                t.membership_type,
                t.source_channel,
                t.course_variant,
                COALESCE(t.slot_identity_key, t.slot_group_key) AS slot_identity_key,
                COALESCE(t.sale_price_krw, t.listed_price_krw, t.price_krw) AS new_price,
                t.promo_flag     AS new_promo,
                COALESCE(t.price_badge, t.promo_text) AS new_price_badge,
                COALESCE(t.promo_text, t.price_badge) AS new_promo_text,
                COALESCE(p.sale_price_krw, p.listed_price_krw, p.price_krw) AS old_price,
                p.promo_flag     AS old_promo,
                COALESCE(p.price_badge, p.promo_text) AS old_price_badge
            FROM today_latest t
            JOIN prev_latest p
              ON  COALESCE(t.slot_identity_key, t.slot_group_key) = COALESCE(p.slot_identity_key, p.slot_group_key)
             AND  t._rn = 1
             AND  p._rn = 1
            WHERE COALESCE(t.sale_price_krw, t.listed_price_krw, t.price_krw) IS NOT NULL
              AND COALESCE(p.sale_price_krw, p.listed_price_krw, p.price_krw) IS NOT NULL
              AND COALESCE(t.sale_price_krw, t.listed_price_krw, t.price_krw)
                  != COALESCE(p.sale_price_krw, p.listed_price_krw, p.price_krw)
        """
        async with db.execute(query, (report_date, prev_date)) as cur:
            changed_slots = await cur.fetchall()

        event_count = 0
        for row in changed_slots:
            old_p = row["old_price"]
            new_p = row["new_price"]
            delta = new_p - old_p
            delta_pct = round(delta / old_p * 100, 2)

            # ── 이벤트 유형 판정
            #    특가 상태 변화 우선 → 그 다음 가격 방향
            old_promo = row["old_promo"] or 0
            new_promo = row["new_promo"] or 0

            if old_promo == 0 and new_promo == 1:
                event_type = "특가부착"
            elif old_promo == 1 and new_promo == 0:
                event_type = "특가해제"
            elif delta < 0:
                event_type = "인하"
            else:
                event_type = "인상"

            await db.execute(
                """
                INSERT INTO price_change_events
                    (course_name, play_date, tee_time, course_sub, membership_type,
                     detected_at,
                     old_price_krw, new_price_krw, delta_price_krw, delta_pct,
                     event_type, promo_flag_after, promo_text_after)
                VALUES (?,?,?,?,?, ?, ?,?,?,?, ?,?,?)
                """,
                (
                    row["course_name"], row["play_date"],
                    row["tee_time"], row["course_sub"], row["membership_type"],
                    report_date,
                    old_p, new_p, delta, delta_pct,
                    event_type, new_promo, row["new_promo_text"],
                ),
            )
            event_row = await db.execute("SELECT last_insert_rowid()")
            event_id = (await event_row.fetchone())[0]
            count_7d = await _count_recent_price_changes(
                db,
                row["slot_identity_key"],
                report_date,
            )
            first_discount_dday = await _find_first_discount_dday(
                db,
                row["slot_identity_key"],
                report_date,
            )
            await db.execute(
                """
                INSERT INTO price_change_facts
                    (price_change_event_id, slot_identity_key, course_id, course_name, play_date,
                     tee_time, part_type, course_variant, source_channel, change_detected_at,
                     previous_price_krw, current_price_krw, delta_krw, delta_pct, change_type,
                     promo_flag_before, promo_flag_after, price_badge_before, price_badge_after,
                     price_change_count_7d)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event_id, row["slot_identity_key"], row["course_id"], row["course_name"], row["play_date"],
                    row["tee_time"], row["part_type"], row["course_variant"], row["source_channel"], report_date,
                    old_p, new_p, delta, delta_pct, event_type,
                    old_promo, new_promo, row["old_price_badge"], row["new_price_badge"], count_7d,
                ),
            )
            await db.execute(
                """
                UPDATE tee_time_snapshots
                SET previous_price_krw = ?, price_changed_flag = 1,
                    price_change_delta_krw = ?, price_change_delta_pct = ?,
                    price_change_count_7d = ?, first_discount_dday = COALESCE(first_discount_dday, ?)
                WHERE id = ?
                """,
                (old_p, delta, delta_pct, count_7d, first_discount_dday, row["snapshot_id"]),
            )
            event_count += 1

        await db.commit()

    logger.info(
        f"[가격변동감지] {report_date} vs {prev_date}: {event_count}건 감지"
    )
    return event_count


async def get_change_summary(report_date: str = None) -> dict:
    """
    price_change_events를 요약 → 브리핑용 딕셔너리 반환

    Returns:
        {
          "total": int,
          "by_type": {"인하": N, "인상": N, "특가부착": N, "특가해제": N},
          "by_course": {course_name: {"count": N, "max_delta": N}},
          "biggest_cut": {course_name, play_date, tee_time, delta_price_krw, delta_pct} | None,
        }
    """
    if report_date is None:
        report_date = date.today().isoformat()

    result = {
        "date": report_date,
        "total": 0,
        "by_type": {"인하": 0, "인상": 0, "특가부착": 0, "특가해제": 0},
        "by_course": {},
        "biggest_cut": None,
    }

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM price_change_events WHERE detected_at = ?",
            (report_date,),
        ) as cur:
            rows = await cur.fetchall()

    result["total"] = len(rows)
    biggest_delta = 0

    for row in rows:
        et = row["event_type"]
        if et in result["by_type"]:
            result["by_type"][et] += 1

        cn = row["course_name"]
        if cn not in result["by_course"]:
            result["by_course"][cn] = {"count": 0, "max_abs_delta": 0}
        result["by_course"][cn]["count"] += 1
        abs_d = abs(row["delta_price_krw"])
        if abs_d > result["by_course"][cn]["max_abs_delta"]:
            result["by_course"][cn]["max_abs_delta"] = abs_d

        # 최대 인하 슬롯 (절대값 기준 음수)
        if row["delta_price_krw"] < biggest_delta:
            biggest_delta = row["delta_price_krw"]
            result["biggest_cut"] = {
                "course_name":   row["course_name"],
                "play_date":     row["play_date"],
                "tee_time":      row["tee_time"],
                "course_sub":    row["course_sub"],
                "delta_price_krw": row["delta_price_krw"],
                "delta_pct":     row["delta_pct"],
            }

    return result


async def _count_recent_price_changes(
    db: aiosqlite.Connection,
    slot_identity_key: str,
    report_date: str,
) -> int:
    async with db.execute(
        """
        SELECT COUNT(*)
        FROM price_change_facts
        WHERE slot_identity_key = ?
          AND change_detected_at BETWEEN date(?, '-6 day') AND ?
        """,
        (slot_identity_key, report_date, report_date),
    ) as cur:
        row = await cur.fetchone()
    return int(row[0] or 0) + 1


async def _find_first_discount_dday(
    db: aiosqlite.Connection,
    slot_identity_key: str,
    report_date: str,
) -> int | None:
    async with db.execute(
        """
        SELECT MIN(d_day)
        FROM tee_time_snapshots
        WHERE COALESCE(slot_identity_key, slot_group_key) = ?
          AND collected_date <= ?
          AND promo_flag = 1
        """,
        (slot_identity_key, report_date),
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row and row[0] is not None else None
