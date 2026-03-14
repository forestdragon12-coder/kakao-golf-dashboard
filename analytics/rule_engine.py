"""
일간 집계 + 가격변동/회원제 오픈 이벤트 기반 판단 룰 엔진

현재 데이터가 1일치만 있어도 A/E/F/H 룰은 동작하고,
가격변동/누적 이력이 쌓이면 B/C/D도 자동으로 활성화된다.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import aiosqlite
from loguru import logger

from db.database import DB_PATH


def _today() -> str:
    return date.today().isoformat()


def _safe_div(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


async def evaluate_rules(report_date: str | None = None) -> dict:
    """
    판단룰 A~H를 현재 누적 데이터 기준으로 평가한다.

    Returns:
        {
          "date": str,
          "high_defense": [...],          # 룰 A
          "repeat_discount": [...],       # 룰 B/F
          "price_response": [...],        # 룰 C/D
          "premium_candidates": [...],    # 룰 E
          "member_open_alerts": [...],    # 룰 H
        }
    """
    if report_date is None:
        report_date = _today()

    result = {
        "date": report_date,
        "high_defense": [],
        "repeat_discount": [],
        "price_response": [],
        "premium_candidates": [],
        "member_open_alerts": [],
        "actions": [],
        "signals": {},
        "summary_counts": {},
        "risks": [],
    }

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        metrics = await _load_daily_metrics(db, report_date)
        course_price_stats = await _load_course_price_stats(db, report_date)
        repeat_discount = await _load_repeat_discount_signals(db, report_date)
        price_response = await _load_price_response_signals(db, report_date)
        member_opens = await _load_member_open_alerts(db, report_date)

    for row in metrics:
        course_name = row["course_name"]
        price_stats = course_price_stats.get(course_name, {})
        course_avg_price = price_stats.get("avg_price") or 0
        course_min_open_slots = price_stats.get("min_open_slots") or 0
        promo_ratio = _safe_div(row["promo_slot_count"], row["observed_open_slots"])
        pax3_ratio = _safe_div(row["pax_3plus_count"], row["observed_open_slots"])

        # 룰 A: 특가 없이도 잔여티가 적은 구간 → 가격 유지 여력
        if row["discount_event_flag"] == 0 and row["observed_open_slots"] <= max(3, course_min_open_slots + 1):
            result["high_defense"].append({
                "course_name": course_name,
                "play_date": row["play_date"],
                "part_type": row["part_type"],
                "membership_type": row["membership_type"],
                "open_slots": row["observed_open_slots"],
                "min_price_krw": row["min_price_krw"],
                "reason": "무특가 저잔여",
            })

        # 룰 E: 비싼데도 잔여티가 적은 구간 → 프리미엄 유지 가능성
        if (
            row["discount_event_flag"] == 0
            and row["avg_price_krw"] is not None
            and row["avg_price_krw"] >= course_avg_price * 1.1
            and row["observed_open_slots"] <= max(4, course_min_open_slots + 2)
        ):
            result["premium_candidates"].append({
                "course_name": course_name,
                "play_date": row["play_date"],
                "part_type": row["part_type"],
                "membership_type": row["membership_type"],
                "avg_price_krw": int(row["avg_price_krw"]),
                "course_avg_price_krw": int(course_avg_price),
                "open_slots": row["observed_open_slots"],
                "reason": "고가 저잔여",
            })

        # 룰 F: 3인 이상 비중 높고 잔여도 많음 → 특가 의존/약세 구간
        if pax3_ratio >= 0.3 and row["observed_open_slots"] >= 4:
            result["repeat_discount"].append({
                "course_name": course_name,
                "play_date": row["play_date"],
                "part_type": row["part_type"],
                "membership_type": row["membership_type"],
                "signal": "3인특가의존",
                "signal_ratio": round(pax3_ratio, 2),
                "open_slots": row["observed_open_slots"],
            })

        # 현재 당일 특가 비중이 매우 높고 잔여가 많으면 약세 구간으로 간주
        if promo_ratio >= 0.5 and row["observed_open_slots"] >= 6:
            result["repeat_discount"].append({
                "course_name": course_name,
                "play_date": row["play_date"],
                "part_type": row["part_type"],
                "membership_type": row["membership_type"],
                "signal": "당일특가집중",
                "signal_ratio": round(promo_ratio, 2),
                "open_slots": row["observed_open_slots"],
            })

    result["repeat_discount"].extend(repeat_discount)
    result["price_response"] = price_response
    result["member_open_alerts"] = member_opens

    for key in ("high_defense", "repeat_discount", "price_response", "premium_candidates", "member_open_alerts"):
        result[key] = sorted(
            result[key],
            key=lambda item: (
                item.get("course_name", ""),
                item.get("play_date", ""),
                item.get("part_type", ""),
            ),
        )

    result["signals"] = {
        "high_defense": result["high_defense"],
        "repeat_discount": result["repeat_discount"],
        "price_response": result["price_response"],
        "premium_candidates": result["premium_candidates"],
        "member_open_alerts": result["member_open_alerts"],
    }
    result["actions"] = _build_actions(result["signals"])
    result["summary_counts"] = {
        key: len(value)
        for key, value in result["signals"].items()
    }
    result["risks"] = _build_risks(result)

    logger.info(
        "[룰엔진] {}: 방어력 {} / 반복할인 {} / 반응 {} / 프리미엄 {} / 회원제오픈 {}",
        report_date,
        len(result["high_defense"]),
        len(result["repeat_discount"]),
        len(result["price_response"]),
        len(result["premium_candidates"]),
        len(result["member_open_alerts"]),
    )
    return result


def _build_actions(signals: dict) -> list[dict]:
    actions = []

    for item in signals.get("high_defense", []):
        score = min(100, 55 + max(0, 6 - int(item.get("open_slots", 0))) * 7)
        actions.append(
            _make_action(
                source_signal="high_defense",
                action="가격유지",
                priority_score=score,
                course_name=item.get("course_name"),
                play_date=item.get("play_date"),
                part_type=item.get("part_type"),
                membership_type=item.get("membership_type"),
                course_sub=item.get("course_sub"),
                reason=item.get("reason", "무특가 저잔여"),
                evidence={
                    "open_slots": item.get("open_slots"),
                    "min_price_krw": item.get("min_price_krw"),
                },
            )
        )

    for item in signals.get("premium_candidates", []):
        score = min(100, 62 + max(0, 5 - int(item.get("open_slots", 0))) * 6)
        actions.append(
            _make_action(
                source_signal="premium_candidates",
                action="가격유지",
                priority_score=score,
                course_name=item.get("course_name"),
                play_date=item.get("play_date"),
                part_type=item.get("part_type"),
                membership_type=item.get("membership_type"),
                course_sub=item.get("course_sub"),
                reason=item.get("reason", "고가 저잔여"),
                evidence={
                    "open_slots": item.get("open_slots"),
                    "avg_price_krw": item.get("avg_price_krw"),
                    "course_avg_price_krw": item.get("course_avg_price_krw"),
                },
            )
        )

    for item in signals.get("repeat_discount", []):
        ratio = float(item.get("signal_ratio") or 0.0)
        score = min(100, 45 + int(ratio * 30) + min(25, int(item.get("open_slots", item.get("avg_open_slots", 0)) or 0) * 2))
        action = "티수조정검토" if ratio >= 0.75 and (item.get("days_observed") or 0) >= 3 else "추가할인검토"
        reason = "반복 약세 패턴" if action == "티수조정검토" else "특가/약세 신호 지속"
        actions.append(
            _make_action(
                source_signal="repeat_discount",
                action=action,
                priority_score=score,
                course_name=item.get("course_name"),
                play_date=item.get("play_date"),
                part_type=item.get("part_type"),
                membership_type=item.get("membership_type"),
                course_sub=item.get("course_sub"),
                reason=reason,
                evidence={
                    "signal": item.get("signal"),
                    "signal_ratio": ratio,
                    "open_slots": item.get("open_slots"),
                    "avg_open_slots": item.get("avg_open_slots"),
                    "days_observed": item.get("days_observed"),
                },
            )
        )

    for item in signals.get("price_response", []):
        grade = item.get("response_grade") or "없음"
        score_map = {"강함": 58, "보통": 48, "약함": 74, "없음": 82, "판단보류": 40}
        if grade in {"강함", "보통"}:
            action = "관망"
            reason = "할인 후 재고 감소 속도 개선"
        elif grade == "판단보류":
            action = "추가관찰"
            reason = "관측 구간 부족 또는 비교 데이터 미흡"
        else:
            action = "추가할인검토"
            reason = "할인 후 재고 감소 개선이 제한적"
        actions.append(
            _make_action(
                source_signal="price_response",
                action=action,
                priority_score=score_map.get(grade, 40),
                course_name=item.get("course_name"),
                play_date=item.get("play_date"),
                part_type=item.get("part_type"),
                membership_type=item.get("membership_type"),
                course_sub=item.get("course_sub"),
                reason=reason,
                evidence={
                    "response_grade": grade,
                    "response_speed": item.get("response_speed"),
                    "drop_rate_d3": item.get("drop_rate_d3"),
                    "drop_rate_d7": item.get("drop_rate_d7"),
                    "control_drop_rate_d3": item.get("control_drop_rate_d3"),
                },
            )
        )

    for item in signals.get("member_open_alerts", []):
        score = 68 + (8 if item.get("promo_flag") else 0)
        actions.append(
            _make_action(
                source_signal="member_open_alerts",
                action="공급증가주의",
                priority_score=min(100, score),
                course_name=item.get("course_name"),
                play_date=item.get("play_date"),
                part_type=item.get("part_type"),
                membership_type="회원제",
                course_sub=item.get("course_sub"),
                reason="회원제 신규 오픈 감지",
                evidence={
                    "slot_count": item.get("slot_count"),
                    "min_price_krw": item.get("min_price_krw"),
                    "max_price_krw": item.get("max_price_krw"),
                    "promo_flag": item.get("promo_flag"),
                },
            )
        )

    ranked = sorted(
        actions,
        key=lambda item: (-item["priority_score"], item.get("course_name") or "", item.get("play_date") or ""),
    )
    for index, item in enumerate(ranked, start=1):
        item["priority_rank"] = index
    return ranked


def _make_action(
    *,
    source_signal: str,
    action: str,
    priority_score: int,
    course_name: str | None,
    play_date: str | None,
    part_type: str | None,
    membership_type: str | None,
    course_sub: str | None,
    reason: str,
    evidence: dict,
) -> dict:
    return {
        "priority_rank": 0,
        "priority_score": priority_score,
        "severity": _score_to_severity(priority_score),
        "action": action,
        "course_name": course_name,
        "play_date": play_date,
        "part_type": part_type,
        "course_sub": course_sub,
        "membership_type": membership_type,
        "reason": reason,
        "source_signal": source_signal,
        "evidence": evidence,
    }


def _score_to_severity(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _build_risks(result: dict) -> list[dict]:
    risks = []
    if not result.get("price_response"):
        risks.append({
            "risk_type": "insufficient_history",
            "severity": "medium",
            "message": "할인 반응 해석은 추가 누적 수집 이후 신뢰도 상승",
        })
    repeat_discount = result.get("repeat_discount", [])
    if repeat_discount and not any((item.get("days_observed") or 0) >= 3 for item in repeat_discount):
        risks.append({
            "risk_type": "short_repeat_window",
            "severity": "low",
            "message": "반복 약세 판정은 관측 일수가 더 쌓이면 안정화됨",
        })
    if not result.get("actions"):
        risks.append({
            "risk_type": "low_signal_day",
            "severity": "low",
            "message": "당일 특이 신호가 적어 관망 중심 해석 필요",
        })
    return risks


async def _load_daily_metrics(db: aiosqlite.Connection, report_date: str):
    async with db.execute(
        """
        SELECT *
        FROM daily_course_metrics
        WHERE report_date = ?
          AND (membership_type IS NULL OR membership_type = '대중제')
        ORDER BY course_name, play_date, part_type
        """,
        (report_date,),
    ) as cur:
        return await cur.fetchall()


async def _load_course_price_stats(db: aiosqlite.Connection, report_date: str) -> dict:
    stats = {}
    async with db.execute(
        """
        SELECT
            course_name,
            AVG(avg_price_krw) AS avg_price,
            MIN(observed_open_slots) AS min_open_slots
        FROM daily_course_metrics
        WHERE report_date = ?
          AND (membership_type IS NULL OR membership_type = '대중제')
        GROUP BY course_name
        """,
        (report_date,),
    ) as cur:
        for row in await cur.fetchall():
            stats[row["course_name"]] = {
                "avg_price": row["avg_price"],
                "min_open_slots": row["min_open_slots"],
            }
    return stats


async def _load_repeat_discount_signals(db: aiosqlite.Connection, report_date: str) -> list[dict]:
    window_start = (date.fromisoformat(report_date) - timedelta(days=14)).isoformat()
    grouped = defaultdict(lambda: {"days": set(), "promo_days": set(), "pax3_days": set(), "open_slots": 0, "row_count": 0})

    async with db.execute(
        """
        SELECT
            course_name,
            weekday_type,
            part_type,
            COALESCE(membership_type, '단일') AS membership_type,
            report_date,
            CASE WHEN promo_slot_count > 0 THEN 1 ELSE 0 END AS has_promo,
            CASE WHEN pax_3plus_count > 0 THEN 1 ELSE 0 END AS has_pax3,
            observed_open_slots
        FROM daily_course_metrics
        WHERE report_date BETWEEN ? AND ?
          AND (membership_type IS NULL OR membership_type = '대중제')
        """,
        (window_start, report_date),
    ) as cur:
        rows = await cur.fetchall()

    for row in rows:
        key = (row["course_name"], row["weekday_type"], row["part_type"], row["membership_type"])
        grouped[key]["days"].add(row["report_date"])
        if row["has_promo"]:
            grouped[key]["promo_days"].add(row["report_date"])
        if row["has_pax3"]:
            grouped[key]["pax3_days"].add(row["report_date"])
        grouped[key]["open_slots"] += row["observed_open_slots"]
        grouped[key]["row_count"] += 1

    results = []
    for key, info in grouped.items():
        observed_days = len(info["days"])
        if observed_days < 3:
            continue

        promo_ratio = _safe_div(len(info["promo_days"]), observed_days)
        pax3_ratio = _safe_div(len(info["pax3_days"]), observed_days)
        if promo_ratio >= 0.6 or pax3_ratio >= 0.6:
            results.append({
                "course_name": key[0],
                "weekday_type": key[1],
                "part_type": key[2],
                "membership_type": None if key[3] == "단일" else key[3],
                "signal": "반복할인구간" if promo_ratio >= pax3_ratio else "반복3인구간",
                "signal_ratio": round(max(promo_ratio, pax3_ratio), 2),
                "days_observed": observed_days,
                "avg_open_slots": round(_safe_div(info["open_slots"], info["row_count"]), 1),
            })

    return results


async def _load_price_response_signals(db: aiosqlite.Connection, report_date: str) -> list[dict]:
    results = []
    async with db.execute(
        """
        SELECT
            course_name,
            play_date,
            part_type,
            membership_type,
            event_type,
            response_grade,
            baseline_open_slots,
            open_slots_d1,
            open_slots_d3,
            open_slots_d5,
            open_slots_d7,
            drop_rate_d3,
            drop_rate_d7,
            control_drop_rate_d3,
            control_drop_rate_d7,
            response_score,
            confidence_grade,
            holdout_reason
        FROM discount_response_metrics
        WHERE event_date = ?
        ORDER BY course_name, play_date, part_type
        """,
        (report_date,),
    ) as cur:
        rows = await cur.fetchall()

    for row in rows:
        grade = row["response_grade"] or "판단보류"
        if grade not in {"강함", "보통", "약함", "없음", "판단보류"}:
            grade = "판단보류"
        if grade in {"강함", "보통"}:
            signal = "할인반응양호"
        elif grade == "판단보류":
            signal = "할인반응보류"
        else:
            signal = "할인반응약함"
        results.append({
            "course_name": row["course_name"],
            "play_date": row["play_date"],
            "part_type": row["part_type"],
            "membership_type": row["membership_type"],
            "event_type": row["event_type"],
            "response_grade": grade,
            "response_speed": "3일" if row["drop_rate_d3"] is not None else ("7일" if row["drop_rate_d7"] is not None else "-"),
            "baseline_open_slots": row["baseline_open_slots"],
            "open_slots_d1": row["open_slots_d1"],
            "open_slots_d3": row["open_slots_d3"],
            "open_slots_d5": row["open_slots_d5"],
            "open_slots_d7": row["open_slots_d7"],
            "drop_rate_d3": row["drop_rate_d3"],
            "drop_rate_d7": row["drop_rate_d7"],
            "control_drop_rate_d3": row["control_drop_rate_d3"],
            "control_drop_rate_d7": row["control_drop_rate_d7"],
            "response_score": row["response_score"],
            "confidence_grade": row["confidence_grade"],
            "holdout_reason": row["holdout_reason"],
            "signal": signal,
        })

    return results


async def _load_member_open_alerts(db: aiosqlite.Connection, report_date: str) -> list[dict]:
    alerts = []
    async with db.execute(
        """
        SELECT
            course_name,
            play_date,
            member_slot_count,
            min_price_krw,
            max_price_krw,
            promo_flag
        FROM member_open_events
        WHERE detected_at = ?
        ORDER BY course_name, play_date
        """,
        (report_date,),
    ) as cur:
        rows = await cur.fetchall()

    for row in rows:
        alerts.append({
            "course_name": row["course_name"],
            "play_date": row["play_date"],
            "slot_count": row["member_slot_count"],
            "min_price_krw": row["min_price_krw"],
            "max_price_krw": row["max_price_krw"],
            "promo_flag": row["promo_flag"],
        })
    return alerts
