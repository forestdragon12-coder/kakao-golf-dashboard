"""
당일 수집 스냅샷 → daily_course_metrics 집계

집계 단위: (course_name, play_date, part_type, membership_type)
회원제 오픈 판단: 골드레이크·해피니스 전용 (has_member_tier 활용)
member_open_events: 회원제 슬롯 최초 관측일 기록
멱등성: report_date 기존 레코드 삭제 후 재집계
"""
import json
import aiosqlite
from datetime import date
from loguru import logger

from db.database import DB_PATH
from config.courses import has_member_tier


async def aggregate_daily(report_date: str = None) -> int:
    """
    report_date 기준 tee_time_snapshots → daily_course_metrics 집계

    Args:
        report_date: 'YYYY-MM-DD' 형식. None이면 오늘 날짜 사용

    Returns:
        삽입된 행 수 (코스×플레이일×파트×멤버십 조합 수)
    """
    if report_date is None:
        report_date = date.today().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # ── 기존 당일 집계 초기화 (멱등성)
        await db.execute(
            "DELETE FROM daily_course_metrics WHERE report_date = ?",
            (report_date,),
        )

        # ── (course_name, play_date, part_type, membership_type) 그룹 집계
        #    시간별 수집 시 같은 슬롯 중복 방지: 하루 최신 스냅샷만 집계
        agg_query = """
            WITH latest_snap AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(slot_identity_key, slot_group_key)
                    ORDER BY collected_at DESC
                ) AS _rn
                FROM tee_time_snapshots
                WHERE collected_date = ?
            )
            SELECT
                course_name,
                play_date,
                season,
                weekday_type,
                part_type,
                membership_type,
                d_day,
                COUNT(*)                                              AS open_slots,
                CAST(ROUND(AVG(price_krw), 0) AS INTEGER)            AS avg_price,
                MIN(price_krw)                                        AS min_price,
                MAX(price_krw)                                        AS max_price,
                SUM(CASE WHEN promo_flag = 1           THEN 1 ELSE 0 END) AS promo_cnt,
                SUM(CASE WHEN price_type LIKE '%그린피%' THEN 1 ELSE 0 END) AS greenfee_cnt,
                SUM(CASE WHEN price_type LIKE '%카트비%' THEN 1 ELSE 0 END) AS cart_cnt,
                SUM(CASE WHEN pax_condition LIKE '3인%' THEN 1 ELSE 0 END) AS pax3_cnt,
                MAX(CASE WHEN promo_flag = 1           THEN 1 ELSE 0 END) AS disc_flag
            FROM latest_snap
            WHERE _rn = 1
              AND price_krw IS NOT NULL
            GROUP BY course_name, play_date, part_type, membership_type
        """
        async with db.execute(agg_query, (report_date,)) as cur:
            agg_rows = await cur.fetchall()

        # ── 회원제 오픈 여부 맵: (course_name, play_date) → 1 / 없으면 0
        async with db.execute(
            """
            SELECT DISTINCT course_name, play_date
            FROM tee_time_snapshots
            WHERE collected_date = ?
              AND membership_type = '회원제'
            """,
            (report_date,),
        ) as cur:
            member_open_map = {
                (r["course_name"], r["play_date"]): 1
                for r in await cur.fetchall()
            }

        # ── daily_course_metrics 삽입
        inserted = 0
        for row in agg_rows:
            cn = row["course_name"]
            pd = row["play_date"]

            # member_open_flag: 회원제 구분 있는 골프장만 판단, 나머지는 NULL
            if has_member_tier(cn):
                member_open_flag = member_open_map.get((cn, pd), 0)
            else:
                member_open_flag = None

            await db.execute(
                """
                INSERT INTO daily_course_metrics
                    (report_date, course_name, play_date,
                     season, weekday_type, part_type, membership_type, d_day,
                     observed_open_slots,
                     avg_price_krw, min_price_krw, max_price_krw,
                     promo_slot_count, greenfee_slot_count, cart_extra_slot_count,
                     pax_3plus_count, discount_event_flag,
                     member_open_flag, confidence_score)
                VALUES (?,?,?, ?,?,?,?,?, ?, ?,?,?, ?,?,?, ?,?, ?,?)
                """,
                (
                    report_date, cn, pd,
                    row["season"], row["weekday_type"],
                    row["part_type"], row["membership_type"],
                    row["d_day"],
                    row["open_slots"],
                    row["avg_price"], row["min_price"], row["max_price"],
                    row["promo_cnt"], row["greenfee_cnt"], row["cart_cnt"],
                    row["pax3_cnt"], row["disc_flag"],
                    member_open_flag,
                    None,   # confidence_score: baseline 구현 후 채움
                ),
            )
            inserted += 1

        # ── member_open_events 업데이트
        await _update_member_open_events(db, report_date)

        await db.commit()

    logger.info(f"[일간집계] {report_date}: {inserted}개 그룹 집계 완료")
    return inserted


async def _update_member_open_events(db: aiosqlite.Connection, report_date: str):
    """
    오늘 관측된 회원제 슬롯 중 최초 등장한 play_date만 member_open_events에 기록.
    이전 날짜에 이미 기록된 play_date는 스킵 (최초 감지일 보존).
    """
    # 오늘 관측된 회원제 슬롯 집계
    async with db.execute(
        """
        SELECT
            course_name,
            play_date,
            COUNT(*)              AS slot_count,
            MIN(price_krw)        AS min_price,
            MAX(price_krw)        AS max_price,
            MAX(promo_flag)       AS has_promo,
            GROUP_CONCAT(DISTINCT course_sub) AS sub_names
        FROM tee_time_snapshots
        WHERE collected_date = ?
          AND membership_type = '회원제'
        GROUP BY course_name, play_date
        """,
        (report_date,),
    ) as cur:
        today_member_rows = await cur.fetchall()

    for row in today_member_rows:
        cn, pd = row["course_name"], row["play_date"]

        # 이미 기록된 play_date면 스킵 (최초 감지일 보존)
        async with db.execute(
            "SELECT id FROM member_open_events WHERE course_name=? AND play_date=?",
            (cn, pd),
        ) as cur2:
            if await cur2.fetchone():
                continue

        # course_sub 목록 → JSON array
        sub_names_raw = row["sub_names"] or ""
        sub_list = [s.strip() for s in sub_names_raw.split(",") if s.strip()]
        sub_json = json.dumps(sub_list, ensure_ascii=False)

        await db.execute(
            """
            INSERT INTO member_open_events
                (course_name, play_date, detected_at,
                 member_slot_count, member_sub_names,
                 min_price_krw, max_price_krw, promo_flag)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                cn, pd, report_date,
                row["slot_count"], sub_json,
                row["min_price"], row["max_price"], row["has_promo"],
            ),
        )
        logger.debug(f"  [회원제오픈] {cn} / {pd}: {row['slot_count']}슬롯 최초 감지")


async def get_aggregation_summary(report_date: str = None) -> dict:
    """
    daily_course_metrics 기반 당일 요약 반환 (브리핑용)

    Returns:
        {
          "date": str,
          "courses": {course_name: {"total_slots": N, "promo_slots": N, "min_price": N}},
          "member_opens_today": [{course_name, play_date, slot_count}],
        }
    """
    if report_date is None:
        report_date = date.today().isoformat()

    summary = {
        "date": report_date,
        "courses": {},
        "member_opens_today": [],
    }

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 골프장별 총 슬롯 / 특가 슬롯 / 최저가
        async with db.execute(
            """
            SELECT
                course_name,
                SUM(observed_open_slots)  AS total_slots,
                SUM(promo_slot_count)     AS promo_slots,
                CAST(
                    ROUND(
                        SUM(COALESCE(avg_price_krw, 0) * COALESCE(observed_open_slots, 0))
                        / NULLIF(SUM(COALESCE(observed_open_slots, 0)), 0),
                        0
                    ) AS INTEGER
                )                         AS avg_price,
                MIN(min_price_krw)        AS min_price,
                MAX(max_price_krw)        AS max_price
            FROM daily_course_metrics
            WHERE report_date = ?
              AND (membership_type IS NULL OR membership_type = '대중제')
            GROUP BY course_name
            """,
            (report_date,),
        ) as cur:
            for r in await cur.fetchall():
                summary["courses"][r["course_name"]] = {
                    "total_slots": r["total_slots"],
                    "promo_slots": r["promo_slots"],
                    "avg_price":   r["avg_price"],
                    "min_price":   r["min_price"],
                    "max_price":   r["max_price"],
                }

        # 오늘 최초 감지된 회원제 오픈
        async with db.execute(
            """
            SELECT course_name, play_date, member_slot_count, promo_flag
            FROM member_open_events
            WHERE detected_at = ?
            ORDER BY course_name, play_date
            """,
            (report_date,),
        ) as cur:
            for r in await cur.fetchall():
                summary["member_opens_today"].append({
                    "course_name":  r["course_name"],
                    "play_date":    r["play_date"],
                    "slot_count":   r["member_slot_count"],
                    "promo_flag":   r["promo_flag"],
                })

    return summary
