"""
구간 단위 할인 이벤트와 할인 반응을 측정한다.

분석 단위:
- course_name
- play_date
- part_type
- membership_type

기존 슬롯 생존 여부 대신, 할인 전후 잔여티 감소 속도를 비교한다.
"""
from __future__ import annotations

from datetime import date, timedelta

import aiosqlite
from loguru import logger

from db.database import DB_PATH

PRICE_DROP_KRW = -10000
PRICE_DROP_PCT = -0.05
PROMO_RATIO_JUMP = 0.20
MIN_BASELINE_SLOTS = 4
HISTORICAL_LOOKBACK_DAYS = 21
FUTURE_WINDOWS = (1, 3, 5, 7)


async def detect_price_responses(report_date: str | None = None) -> int:
    """
    report_date 기준 구간 단위 할인 이벤트를 생성하고 반응을 기록한다.

    Returns:
        삽입된 discount_response_metrics 행 수
    """
    if report_date is None:
        report_date = date.today().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        await db.execute("DELETE FROM discount_events WHERE event_date = ?", (report_date,))
        await db.execute("DELETE FROM discount_response_metrics WHERE event_date = ?", (report_date,))

        metrics = await _load_metrics(db, report_date)
        prev_metrics = await _load_metrics(
            db,
            (date.fromisoformat(report_date) - timedelta(days=1)).isoformat(),
        )

        event_rows = _build_discount_events(metrics, prev_metrics, report_date)
        inserted = 0

        for event in event_rows:
            await db.execute(
                """
                INSERT INTO discount_events
                    (event_date, course_name, play_date, part_type, membership_type,
                     weekday_type, d_day, event_type,
                     baseline_open_slots, baseline_avg_price_krw, baseline_min_price_krw,
                     baseline_promo_ratio, price_delta_krw, price_delta_pct, promo_ratio_delta,
                     control_part_type, confidence_grade, holdout_reason)
                VALUES (?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?, ?,?,?,?)
                """,
                (
                    report_date,
                    event["course_name"],
                    event["play_date"],
                    event["part_type"],
                    event["membership_type"],
                    event["weekday_type"],
                    event["d_day"],
                    event["event_type"],
                    event["baseline_open_slots"],
                    event["baseline_avg_price_krw"],
                    event["baseline_min_price_krw"],
                    event["baseline_promo_ratio"],
                    event["price_delta_krw"],
                    event["price_delta_pct"],
                    event["promo_ratio_delta"],
                    event["control_part_type"],
                    event["confidence_grade"],
                    event["holdout_reason"],
                ),
            )

            response = await _build_response_metric(db, event, report_date)
            await db.execute(
                """
                INSERT INTO discount_response_metrics
                    (event_date, course_name, play_date, part_type, membership_type, event_type,
                     baseline_open_slots,
                     open_slots_d1, open_slots_d3, open_slots_d5, open_slots_d7,
                     drop_rate_d1, drop_rate_d3, drop_rate_d5, drop_rate_d7,
                     control_part_type, control_drop_rate_d3, control_drop_rate_d7,
                     historical_drop_rate_d3, historical_drop_rate_d7,
                     response_score, response_grade, confidence_grade, holdout_reason)
                VALUES (?,?,?,?,?, ?, ?, ?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?,?)
                """,
                (
                    report_date,
                    event["course_name"],
                    event["play_date"],
                    event["part_type"],
                    event["membership_type"],
                    event["event_type"],
                    event["baseline_open_slots"],
                    response["open_slots_d1"],
                    response["open_slots_d3"],
                    response["open_slots_d5"],
                    response["open_slots_d7"],
                    response["drop_rate_d1"],
                    response["drop_rate_d3"],
                    response["drop_rate_d5"],
                    response["drop_rate_d7"],
                    event["control_part_type"],
                    response["control_drop_rate_d3"],
                    response["control_drop_rate_d7"],
                    response["historical_drop_rate_d3"],
                    response["historical_drop_rate_d7"],
                    response["response_score"],
                    response["response_grade"],
                    response["confidence_grade"],
                    response["holdout_reason"],
                ),
            )
            inserted += 1

        await db.commit()

    logger.info("[반응측정V2] {}: {}건 기록", report_date, inserted)
    return inserted


async def _load_metrics(db: aiosqlite.Connection, report_date: str) -> dict[tuple, dict]:
    async with db.execute(
        """
        SELECT *
        FROM daily_course_metrics
        WHERE report_date = ?
        """,
        (report_date,),
    ) as cur:
        rows = await cur.fetchall()

    metrics: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row["course_name"],
            row["play_date"],
            row["part_type"],
            row["membership_type"],
        )
        metrics[key] = dict(row)
    return metrics


def _build_discount_events(metrics: dict[tuple, dict], prev_metrics: dict[tuple, dict], report_date: str) -> list[dict]:
    events: list[dict] = []
    event_keys: set[tuple] = set()

    for key, current in metrics.items():
        previous = prev_metrics.get(key)
        if previous is None:
            continue

        baseline_open_slots = current.get("observed_open_slots") or 0
        if baseline_open_slots < MIN_BASELINE_SLOTS:
            continue

        current_avg = current.get("avg_price_krw")
        previous_avg = previous.get("avg_price_krw")
        current_min = current.get("min_price_krw")
        previous_min = previous.get("min_price_krw")
        current_promo_ratio = _safe_ratio(current.get("promo_slot_count"), baseline_open_slots)
        previous_promo_ratio = _safe_ratio(previous.get("promo_slot_count"), previous.get("observed_open_slots"))

        avg_delta_krw = _diff(current_avg, previous_avg)
        avg_delta_pct = _safe_pct_change(current_avg, previous_avg)
        min_delta_krw = _diff(current_min, previous_min)
        min_delta_pct = _safe_pct_change(current_min, previous_min)
        promo_ratio_delta = round(current_promo_ratio - previous_promo_ratio, 4)

        price_drop = _is_price_drop(avg_delta_krw, avg_delta_pct) or _is_price_drop(min_delta_krw, min_delta_pct)
        promo_jump = (
            promo_ratio_delta >= PROMO_RATIO_JUMP
            or (previous_promo_ratio == 0.0 and current_promo_ratio >= PROMO_RATIO_JUMP)
        )
        if not price_drop and not promo_jump:
            continue

        event_type = "복합할인형" if price_drop and promo_jump else ("가격인하형" if price_drop else "특가확대형")
        confidence_grade = "high" if price_drop and promo_jump else "medium"
        holdout_reason = None

        control_part_type = _pick_control_part_type(metrics, key, event_keys)
        if control_part_type is None:
            confidence_grade = "low"

        event_keys.add(key)
        events.append(
            {
                "event_date": report_date,
                "course_name": current["course_name"],
                "play_date": current["play_date"],
                "part_type": current["part_type"],
                "membership_type": current["membership_type"],
                "weekday_type": current["weekday_type"],
                "d_day": current["d_day"],
                "event_type": event_type,
                "baseline_open_slots": baseline_open_slots,
                "baseline_avg_price_krw": current_avg,
                "baseline_min_price_krw": current_min,
                "baseline_promo_ratio": current_promo_ratio,
                "price_delta_krw": avg_delta_krw if price_drop else min_delta_krw,
                "price_delta_pct": avg_delta_pct if price_drop else min_delta_pct,
                "promo_ratio_delta": promo_ratio_delta,
                "control_part_type": control_part_type,
                "confidence_grade": confidence_grade,
                "holdout_reason": holdout_reason,
            }
        )

    return events


def _pick_control_part_type(metrics: dict[tuple, dict], event_key: tuple, event_keys: set[tuple]) -> str | None:
    course_name, play_date, part_type, membership_type = event_key
    candidates: list[dict] = []
    for key, row in metrics.items():
        if key == event_key or key in event_keys:
            continue
        if row["course_name"] != course_name or row["play_date"] != play_date:
            continue
        if row["membership_type"] != membership_type:
            continue
        if (row.get("observed_open_slots") or 0) <= 0:
            continue
        candidates.append(row)

    if not candidates:
        return None

    candidates.sort(key=lambda item: abs((item.get("observed_open_slots") or 0) - (metrics[event_key].get("observed_open_slots") or 0)))
    return candidates[0]["part_type"]


async def _build_response_metric(db: aiosqlite.Connection, event: dict, report_date: str) -> dict:
    baseline_open_slots = event["baseline_open_slots"] or 0
    future_slots = {
        window: await _load_future_open_slots(db, event, report_date, window)
        for window in FUTURE_WINDOWS
    }
    drop_rates = {
        window: _drop_rate(baseline_open_slots, future_slots[window])
        for window in FUTURE_WINDOWS
    }

    control_drop_rate_d3 = await _load_control_drop_rate(db, event, report_date, 3)
    control_drop_rate_d7 = await _load_control_drop_rate(db, event, report_date, 7)
    historical_drop_rate_d3 = await _load_historical_drop_rate(db, event, report_date, 3)
    historical_drop_rate_d7 = await _load_historical_drop_rate(db, event, report_date, 7)

    holdout_reason = event["holdout_reason"]
    confidence_grade = event["confidence_grade"]
    if all(future_slots[window] is None for window in FUTURE_WINDOWS):
        holdout_reason = _merge_reason(holdout_reason, "future_observation_missing")
        confidence_grade = "low"

    response_score = _score_response(
        drop_rate_d3=drop_rates[3],
        drop_rate_d7=drop_rates[7],
        control_drop_rate_d3=control_drop_rate_d3,
        control_drop_rate_d7=control_drop_rate_d7,
        historical_drop_rate_d3=historical_drop_rate_d3,
        historical_drop_rate_d7=historical_drop_rate_d7,
        holdout_reason=holdout_reason,
    )
    response_grade = _grade_response(response_score, holdout_reason)

    return {
        "open_slots_d1": future_slots[1],
        "open_slots_d3": future_slots[3],
        "open_slots_d5": future_slots[5],
        "open_slots_d7": future_slots[7],
        "drop_rate_d1": drop_rates[1],
        "drop_rate_d3": drop_rates[3],
        "drop_rate_d5": drop_rates[5],
        "drop_rate_d7": drop_rates[7],
        "control_drop_rate_d3": control_drop_rate_d3,
        "control_drop_rate_d7": control_drop_rate_d7,
        "historical_drop_rate_d3": historical_drop_rate_d3,
        "historical_drop_rate_d7": historical_drop_rate_d7,
        "response_score": response_score,
        "response_grade": response_grade,
        "confidence_grade": confidence_grade,
        "holdout_reason": holdout_reason,
    }


async def _load_future_open_slots(
    db: aiosqlite.Connection,
    event: dict,
    report_date: str,
    days_after: int,
) -> int | None:
    target_date = (date.fromisoformat(report_date) + timedelta(days=days_after)).isoformat()
    async with db.execute(
        """
        SELECT 1
        FROM daily_course_metrics
        WHERE report_date = ?
          AND course_name = ?
        LIMIT 1
        """,
        (target_date, event["course_name"]),
    ) as cur:
        course_collected = await cur.fetchone()

    if not course_collected:
        return None

    async with db.execute(
        """
        SELECT observed_open_slots
        FROM daily_course_metrics
        WHERE report_date = ?
          AND course_name = ?
          AND play_date = ?
          AND part_type = ?
          AND membership_type IS ?
        LIMIT 1
        """,
        (
            target_date,
            event["course_name"],
            event["play_date"],
            event["part_type"],
            event["membership_type"],
        ),
    ) as cur:
        row = await cur.fetchone()

    return row["observed_open_slots"] if row else 0


async def _load_control_drop_rate(
    db: aiosqlite.Connection,
    event: dict,
    report_date: str,
    days_after: int,
) -> float | None:
    control_part_type = event.get("control_part_type")
    if not control_part_type:
        return None

    target_date = (date.fromisoformat(report_date) + timedelta(days=days_after)).isoformat()
    baseline = event["baseline_open_slots"] or 0

    async with db.execute(
        """
        SELECT observed_open_slots
        FROM daily_course_metrics
        WHERE report_date = ?
          AND course_name = ?
          AND play_date = ?
          AND part_type = ?
          AND membership_type IS ?
        LIMIT 1
        """,
        (
            report_date,
            event["course_name"],
            event["play_date"],
            control_part_type,
            event["membership_type"],
        ),
    ) as cur:
        baseline_row = await cur.fetchone()
    if not baseline_row:
        return None

    async with db.execute(
        """
        SELECT observed_open_slots
        FROM daily_course_metrics
        WHERE report_date = ?
          AND course_name = ?
          AND play_date = ?
          AND part_type = ?
          AND membership_type IS ?
        LIMIT 1
        """,
        (
            target_date,
            event["course_name"],
            event["play_date"],
            control_part_type,
            event["membership_type"],
        ),
    ) as cur:
        target_row = await cur.fetchone()
    if not target_row:
        return None

    control_baseline = baseline_row["observed_open_slots"] or 0
    return _drop_rate(control_baseline, target_row["observed_open_slots"])


async def _load_historical_drop_rate(
    db: aiosqlite.Connection,
    event: dict,
    report_date: str,
    days_after: int,
) -> float | None:
    start_date = (date.fromisoformat(report_date) - timedelta(days=HISTORICAL_LOOKBACK_DAYS)).isoformat()
    async with db.execute(
        """
        SELECT
            cur.observed_open_slots AS current_slots,
            nxt.observed_open_slots AS future_slots
        FROM daily_course_metrics cur
        JOIN daily_course_metrics nxt
          ON cur.course_name = nxt.course_name
         AND cur.play_date = nxt.play_date
         AND cur.part_type = nxt.part_type
         AND cur.membership_type IS nxt.membership_type
         AND date(nxt.report_date) = date(cur.report_date, ?)
        WHERE cur.report_date BETWEEN ? AND ?
          AND cur.course_name = ?
          AND cur.part_type = ?
          AND cur.membership_type IS ?
          AND cur.weekday_type = ?
          AND ABS(cur.d_day - ?) <= 2
        """,
        (
            f"+{days_after} day",
            start_date,
            report_date,
            event["course_name"],
            event["part_type"],
            event["membership_type"],
            event["weekday_type"],
            event["d_day"],
        ),
    ) as cur:
        rows = await cur.fetchall()

    rates = [
        _drop_rate(row["current_slots"], row["future_slots"])
        for row in rows
        if row["current_slots"] is not None and row["future_slots"] is not None
    ]
    if not rates:
        return None
    return round(sum(rates) / len(rates), 4)


def _score_response(
    *,
    drop_rate_d3: float | None,
    drop_rate_d7: float | None,
    control_drop_rate_d3: float | None,
    control_drop_rate_d7: float | None,
    historical_drop_rate_d3: float | None,
    historical_drop_rate_d7: float | None,
    holdout_reason: str | None,
) -> float | None:
    if holdout_reason:
        return None
    if drop_rate_d3 is None and drop_rate_d7 is None:
        return None

    score = 0.0
    if drop_rate_d3 is not None:
        score += drop_rate_d3 * 55
    if drop_rate_d7 is not None:
        score += drop_rate_d7 * 45
    if control_drop_rate_d3 is not None and drop_rate_d3 is not None:
        score += max(-20.0, min(20.0, (drop_rate_d3 - control_drop_rate_d3) * 40))
    if control_drop_rate_d7 is not None and drop_rate_d7 is not None:
        score += max(-15.0, min(15.0, (drop_rate_d7 - control_drop_rate_d7) * 30))
    if historical_drop_rate_d3 is not None and drop_rate_d3 is not None:
        score += max(-10.0, min(10.0, (drop_rate_d3 - historical_drop_rate_d3) * 25))
    if historical_drop_rate_d7 is not None and drop_rate_d7 is not None:
        score += max(-10.0, min(10.0, (drop_rate_d7 - historical_drop_rate_d7) * 20))
    return round(score, 2)


def _grade_response(score: float | None, holdout_reason: str | None) -> str:
    if holdout_reason:
        return "판단보류"
    if score is None:
        return "판단보류"
    if score >= 55:
        return "강함"
    if score >= 30:
        return "보통"
    return "약함"


def _drop_rate(baseline_slots: int | None, future_slots: int | None) -> float | None:
    if baseline_slots is None or future_slots is None or baseline_slots <= 0:
        return None
    return round((baseline_slots - future_slots) / baseline_slots, 4)


def _safe_ratio(numerator: int | None, denominator: int | None) -> float:
    if not numerator or not denominator:
        return 0.0
    return round(numerator / denominator, 4)


def _safe_pct_change(current: int | None, previous: int | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / previous, 4)


def _diff(current: int | None, previous: int | None) -> int | None:
    if current is None or previous is None:
        return None
    return current - previous


def _is_price_drop(delta_krw: int | None, delta_pct: float | None) -> bool:
    if delta_krw is not None and delta_krw <= PRICE_DROP_KRW:
        return True
    if delta_pct is not None and delta_pct <= PRICE_DROP_PCT:
        return True
    return False


def _merge_reason(left: str | None, right: str | None) -> str | None:
    if not left:
        return right
    if not right or left == right:
        return left
    return f"{left},{right}"
