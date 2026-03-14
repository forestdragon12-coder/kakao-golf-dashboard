"""
골프장별 전략 프로필을 계산한다.

핵심 지표:
- 기본 체급: 비할인 기준 소진력
- 할인 의존도: 할인 없을 때 대비 성과 격차
- 할인 증폭력: 타사 비할인 기준 대비 초과 소진 효과
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import aiosqlite

from db.database import DB_PATH

BASELINE_LOOKBACK_DAYS = 28
AMPLIFICATION_LOOKBACK_DAYS = 60
NON_DISCOUNT_PROMO_RATIO = 0.10

METRIC_GLOSSARY = [
    {
        "metric": "기본 체급",
        "description": "비할인 또는 약한 할인 구간에서의 기본 소진력을 기준으로 본 고유 판매력입니다.",
        "interpretation": "높을수록 할인 없이도 재고가 빠르게 줄어드는 편입니다.",
    },
    {
        "metric": "할인 의존도",
        "description": "할인 구간 성과 중 비할인 기준선으로 설명되지 않는 비중을 뜻합니다.",
        "interpretation": "높을수록 할인 없이 동일 소진 성과를 유지하기 어려울 수 있습니다.",
    },
    {
        "metric": "할인 증폭력",
        "description": "할인 적용 시 타사 비할인 구간 대비 추가 소진 개선이 얼마나 발생하는지를 뜻합니다.",
        "interpretation": "높을수록 할인 정책이 시장 대비 초과 소진으로 이어질 가능성이 큽니다.",
    },
]


async def build_daily_strategy_profiles(report_date: str) -> dict:
    start_date = (date.fromisoformat(report_date) - timedelta(days=BASELINE_LOOKBACK_DAYS - 1)).isoformat()
    return await build_strategy_profiles(start_date, report_date)


async def build_strategy_profiles(start_date: str, end_date: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        metrics = await _load_metrics(db, start_date, end_date)
        responses = await _load_responses(
            db,
            (date.fromisoformat(end_date) - timedelta(days=AMPLIFICATION_LOOKBACK_DAYS - 1)).isoformat(),
            end_date,
        )

    profiles = _build_profiles(metrics, responses)
    return {
        "profiles": profiles,
        "glossary": METRIC_GLOSSARY,
    }


async def _load_metrics(db: aiosqlite.Connection, start_date: str, end_date: str) -> list[dict]:
    async with db.execute(
        """
        SELECT report_date, course_name, play_date, part_type, membership_type,
               weekday_type, d_day, observed_open_slots, promo_slot_count, discount_event_flag
        FROM daily_course_metrics
        WHERE report_date BETWEEN ? AND ?
          AND (membership_type IS NULL OR membership_type = '대중제')
        ORDER BY report_date, course_name, play_date, part_type
        """,
        (start_date, end_date),
    ) as cur:
        return [dict(row) for row in await cur.fetchall()]


async def _load_responses(db: aiosqlite.Connection, start_date: str, end_date: str) -> list[dict]:
    async with db.execute(
        """
        SELECT event_date, course_name, play_date, part_type, membership_type,
               drop_rate_d3, drop_rate_d7, response_grade, confidence_grade
        FROM discount_response_metrics
        WHERE event_date BETWEEN ? AND ?
        ORDER BY event_date, course_name, play_date, part_type
        """,
        (start_date, end_date),
    ) as cur:
        return [dict(row) for row in await cur.fetchall()]


def _build_profiles(metrics: list[dict], responses: list[dict]) -> list[dict]:
    by_course: dict[str, dict] = defaultdict(lambda: {"rows": 0})
    metrics_by_key: dict[tuple, dict] = {}
    segment_rows: dict[tuple, list[dict]] = defaultdict(list)

    for row in metrics:
        by_course[row["course_name"]]["rows"] += 1
        key = (
            row["report_date"],
            row["course_name"],
            row["play_date"],
            row["part_type"],
            row["membership_type"],
        )
        metrics_by_key[key] = row
        segment_key = (
            row["course_name"],
            row["play_date"],
            row["part_type"],
            row["membership_type"],
        )
        segment_rows[segment_key].append(row)

    baseline_info = _build_baseline_info(segment_rows)
    market_profiles = _build_market_profiles(metrics, metrics_by_key, responses)
    valid_baselines = [item["baseline_drop_rate_d3"] for item in baseline_info.values() if item["baseline_drop_rate_d3"] is not None]
    min_rate = min(valid_baselines) if valid_baselines else 0.0
    max_rate = max(valid_baselines) if valid_baselines else 0.0

    profiles = []
    for course_name in sorted(by_course):
        base = baseline_info.get(course_name, {"baseline_drop_rate_d3": None, "sample_size": 0})
        dependency = _build_dependency_profile(course_name, responses, base["baseline_drop_rate_d3"])
        amplification = market_profiles.get(
            course_name,
            {
                "label": "판단보류",
                "value": None,
                "sample_size": 0,
                "market_gap_d3": None,
                "confidence": "low",
                "is_provisional": False,
            },
        )
        base_score = _scale_score(base["baseline_drop_rate_d3"], min_rate, max_rate)
        profiles.append(
            {
                "course_name": course_name,
                "base_tier": {
                    "grade": _grade_base_tier(base_score),
                    "score": base_score,
                    "baseline_drop_rate_d3": round(base["baseline_drop_rate_d3"], 4) if base["baseline_drop_rate_d3"] is not None else None,
                    "sample_size": base["sample_size"] or by_course[course_name]["rows"],
                },
                "discount_dependency": dependency,
                "discount_amplification": amplification,
                "recommended_action": _recommended_action(base_score, dependency.get("value", 0.0), amplification.get("value")),
            }
        )
    return profiles


def _build_baseline_info(segment_rows: dict[tuple, list[dict]]) -> dict[str, dict]:
    by_course: dict[str, dict] = defaultdict(lambda: {"rate_sum": 0.0, "count": 0})
    for key, rows in segment_rows.items():
        ordered = sorted(rows, key=lambda item: item["report_date"])
        for row in ordered:
            open_slots = row.get("observed_open_slots") or 0
            if not _is_non_discount_row(row):
                continue
            future_row = _find_future_row(ordered, row["report_date"], 3)
            if not future_row:
                continue
            rate = _drop_rate(open_slots, future_row.get("observed_open_slots"))
            if rate is None:
                continue
            by_course[key[0]]["rate_sum"] += rate
            by_course[key[0]]["count"] += 1

    result = {}
    for course_name, info in by_course.items():
        result[course_name] = {
            "baseline_drop_rate_d3": (info["rate_sum"] / info["count"]) if info["count"] else None,
            "sample_size": info["count"],
        }
    return result


def _build_dependency_profile(course_name: str, responses: list[dict], baseline_rate: float | None) -> dict:
    discounted_rates = [
        row["drop_rate_d3"]
        for row in responses
        if row["course_name"] == course_name and row.get("drop_rate_d3") is not None
    ]
    if baseline_rate is None or not discounted_rates:
        return {"label": "판단보류", "value": 0.0, "sample_size": len(discounted_rates)}

    dependency_values = []
    for actual_rate in discounted_rates:
        if actual_rate <= 0:
            continue
        uplift = max(0.0, actual_rate - baseline_rate)
        dependency_values.append(min(1.0, uplift / actual_rate))

    if not dependency_values:
        return {"label": "판단보류", "value": 0.0, "sample_size": len(discounted_rates)}

    value = sum(dependency_values) / len(dependency_values)
    return {
        "label": _label_dependency(value),
        "value": round(value, 4),
        "sample_size": len(dependency_values),
    }


def _build_market_profiles(metrics: list[dict], metrics_by_key: dict[tuple, dict], responses: list[dict]) -> dict[str, dict]:
    grouped: dict[str, dict] = defaultdict(lambda: {"gap_sum": 0.0, "count": 0})
    for response in responses:
        actual_rate = response.get("drop_rate_d3")
        if actual_rate is None:
            continue
        market_rate = _market_baseline_rate(metrics, metrics_by_key, response)
        if market_rate is None:
            continue
        grouped[response["course_name"]]["gap_sum"] += actual_rate - market_rate
        grouped[response["course_name"]]["count"] += 1

    result = {}
    for course_name, info in grouped.items():
        avg_gap = info["gap_sum"] / info["count"] if info["count"] else None
        value = _market_gap_to_score(avg_gap) if avg_gap is not None else None
        result[course_name] = {
            "label": _label_amplification(value),
            "value": value,
            "sample_size": info["count"],
            "market_gap_d3": round(avg_gap, 4) if avg_gap is not None else None,
            "confidence": "medium" if info["count"] >= 2 else "low",
            "is_provisional": False,
        }
    return result


def _market_baseline_rate(metrics: list[dict], metrics_by_key: dict[tuple, dict], response: dict) -> float | None:
    candidates = []
    for row in metrics:
        if row["report_date"] != response["event_date"]:
            continue
        if row["course_name"] == response["course_name"]:
            continue
        if not _is_non_discount_row(row):
            continue
        if row["part_type"] != response["part_type"]:
            continue
        if row["membership_type"] != response["membership_type"]:
            continue
        if row["play_date"] != response["play_date"] and abs((row["d_day"] or 0) - _response_d_day(metrics_by_key, response)) > 1:
            continue

        future_key = (
            (date.fromisoformat(row["report_date"]) + timedelta(days=3)).isoformat(),
            row["course_name"],
            row["play_date"],
            row["part_type"],
            row["membership_type"],
        )
        future_row = metrics_by_key.get(future_key)
        if not future_row:
            continue
        rate = _drop_rate(row.get("observed_open_slots"), future_row.get("observed_open_slots"))
        if rate is None:
            continue
        candidates.append(rate)

    if not candidates:
        return None
    return sum(candidates) / len(candidates)


def _response_d_day(metrics_by_key: dict[tuple, dict], response: dict) -> int:
    key = (
        response["event_date"],
        response["course_name"],
        response["play_date"],
        response["part_type"],
        response["membership_type"],
    )
    row = metrics_by_key.get(key)
    return int(row.get("d_day") or 0) if row else 0


def _find_future_row(rows: list[dict], current_date: str, days_after: int) -> dict | None:
    target = (date.fromisoformat(current_date) + timedelta(days=days_after)).isoformat()
    for row in rows:
        if row["report_date"] == target:
            return row
    return None


def _is_non_discount_row(row: dict) -> bool:
    open_slots = row.get("observed_open_slots") or 0
    promo_slots = row.get("promo_slot_count") or 0
    promo_ratio = _safe_ratio(promo_slots, open_slots)
    return row.get("discount_event_flag") == 0 and promo_ratio <= NON_DISCOUNT_PROMO_RATIO


def _scale_score(value: float | None, min_value: float, max_value: float) -> float | None:
    if value is None:
        return None
    if max_value <= min_value:
        return 100.0
    return round((value - min_value) / (max_value - min_value) * 100, 1)


def _market_gap_to_score(gap: float | None) -> float | None:
    if gap is None:
        return None
    return round(max(0.0, min(100.0, 50 + gap * 100)), 1)


def _safe_ratio(numerator: int | None, denominator: int | None) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def _drop_rate(baseline_slots: int | None, future_slots: int | None) -> float | None:
    if baseline_slots is None or future_slots is None or baseline_slots <= 0:
        return None
    return (baseline_slots - future_slots) / baseline_slots


def _grade_base_tier(score: float | None) -> str:
    if score is None:
        return "N/A"
    if score >= 85:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 55:
        return "B"
    if score >= 40:
        return "C+"
    if score >= 25:
        return "C"
    return "D"


def _label_dependency(value: float) -> str:
    if value >= 0.40:
        return "높음"
    if value >= 0.15:
        return "보통"
    return "낮음"


def _label_amplification(value: float | None) -> str:
    if value is None:
        return "판단보류"
    if value >= 60:
        return "높음"
    if value >= 45:
        return "보통"
    return "낮음"


def _recommended_action(base_score: float | None, dependency_ratio: float, amplification_score: float | None) -> str:
    if base_score is None:
        return "추가 관찰"
    if base_score >= 70 and dependency_ratio < 0.20:
        return "가격 방어"
    if amplification_score is not None and amplification_score >= 60:
        return "선택적 할인 유지"
    if dependency_ratio >= 0.40 and (amplification_score is None or amplification_score < 45):
        return "공급/상품 재설계 검토"
    return "운영 혼합 유지"
