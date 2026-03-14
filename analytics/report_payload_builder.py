"""
보고서용 구조화 payload 생성기.

1차 구현은 일간 보고서 payload에 집중하고,
이후 주간/월간/연간 deterministic payload를 추가한다.
LLM과 deterministic renderer가 모두 같은 payload를 사용한다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import aiosqlite

from db.database import DB_PATH
from analytics.strategy_profile import build_strategy_profiles


def build_daily_report_payload(
    *,
    report_date: str,
    total_rows: int,
    change_summary: dict | None,
    agg_summary: dict | None,
    rule_summary: dict | None,
    prev_agg_summary: dict | None = None,
    prev_rule_summary: dict | None = None,
    strategy_profile: dict | None = None,
) -> dict:
    change_summary = change_summary or {}
    agg_summary = agg_summary or {}
    prev_agg_summary = prev_agg_summary or {}
    rule_summary = rule_summary or {}
    prev_rule_summary = prev_rule_summary or {}

    courses = agg_summary.get("courses", {})
    member_opens = agg_summary.get("member_opens_today", [])
    high_defense = rule_summary.get("high_defense", [])
    repeat_discount = rule_summary.get("repeat_discount", [])
    price_response = rule_summary.get("price_response", [])
    premium_candidates = rule_summary.get("premium_candidates", [])
    member_open_alerts = rule_summary.get("member_open_alerts", [])
    actions = rule_summary.get("actions", [])
    rule_risks = rule_summary.get("risks", [])
    strategy_profile = strategy_profile or {}
    profiles = strategy_profile.get("profiles", [])
    glossary = strategy_profile.get("glossary", [])
    management_snapshot = _build_management_snapshot(
        courses,
        prev_agg_summary.get("courses", {}),
        actions,
        prev_rule_summary.get("actions", []),
    )
    course_comparisons = _build_course_comparisons(
        courses,
        prev_agg_summary.get("courses", {}),
        actions,
        prev_rule_summary.get("actions", []),
        profiles,
    )
    composite_issues = _build_composite_issues(management_snapshot, course_comparisons)
    course_focus = _build_course_focus(
        courses,
        high_defense,
        repeat_discount,
        premium_candidates,
        member_open_alerts,
        profiles,
    )

    promo_slots = sum((info.get("promo_slots") or 0) for info in courses.values())
    total_slots = sum((info.get("total_slots") or 0) for info in courses.values())

    top_signals = []
    if high_defense:
        top_signals.append(f"{high_defense[0]['course_name']} 가격 유지 여력")
    if repeat_discount:
        top_signals.append(f"{repeat_discount[0]['course_name']} 할인 의존 신호")
    if member_open_alerts:
        top_signals.append(f"{member_open_alerts[0]['course_name']} 회원제 오픈")
    if not top_signals and courses:
        cheapest_course = min(
            courses.items(),
            key=lambda item: (item[1].get("min_price") or 999999, item[0]),
        )[0]
        top_signals.append(f"{cheapest_course} 최저가 관찰")

    payload = {
        "report_type": "daily",
        "report_date": report_date,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_window": {
            "start_date": report_date,
            "end_date": report_date,
            "observed_days": 1,
            "is_partial_window": True,
        },
        "data_quality": {
            "coverage_score": 1.0 if total_rows > 0 else 0.0,
            "missing_days": 0,
            "missing_courses": [],
            "confidence_note": _build_confidence_note(change_summary, price_response),
        },
        "summary": {
            "total_courses": len(courses),
            "total_slots": total_slots,
            "promo_slots": promo_slots,
            "promo_ratio": _safe_ratio(promo_slots, total_slots),
            "price_change_events": change_summary.get("total", 0),
            "price_response_events": len(price_response),
            "member_open_events": len(member_opens),
            "top_signals": top_signals,
            "total_rows": total_rows,
            "management_snapshot": management_snapshot,
        },
        "top_summary_section": {
            "one_line_conclusion": top_signals[0] if top_signals else "당일 특이 신호 제한적",
            "berhill_headline": next(
                (item["headline"] for item in course_focus
                 if item["course_name"] == "베르힐"),
                "베르힐 데이터 추가 관찰 필요",
            ),
            "priority_actions": [
                {
                    "course_name": item.get("course_name"),
                    "action": item.get("action"),
                    "reason": item.get("reason"),
                }
                for item in actions[:5]
            ],
        },
        "actions": actions,
        "evidence": {
            "price_change_watch": {
                "total": change_summary.get("total", 0),
                "by_type": change_summary.get(
                    "by_type",
                    {"인하": 0, "인상": 0, "특가부착": 0, "특가해제": 0},
                ),
                "by_course": change_summary.get("by_course", {}),
                "largest_cut": change_summary.get("biggest_cut"),
            },
            "discount_response": {
                "strong_count": sum(1 for item in price_response if item.get("response_grade") == "강함"),
                "weak_count": sum(1 for item in price_response if item.get("response_grade") == "약함"),
                "none_count": sum(1 for item in price_response if item.get("response_grade") == "없음"),
                "hold_count": sum(1 for item in price_response if item.get("response_grade") == "판단보류"),
                "samples": _compact_price_response_samples(price_response),
            },
            "defense_signals": high_defense[:8],
            "repeat_discount_signals": repeat_discount[:8],
            "member_open_signals": member_open_alerts,
            "course_board": _build_course_board(courses, high_defense, repeat_discount),
            "strategy_profiles": profiles,
            "metric_glossary": glossary,
            "course_comparisons": course_comparisons,
            "composite_issues": composite_issues,
        },
        "risks": _merge_risks(_build_daily_risks(change_summary, price_response, total_rows), rule_risks),
        "recommendations": _build_recommendations(actions),
        "course_focus": course_focus,
        "llm_constraints": [
            "수치를 변경하지 말 것",
            "action/severity/priority_score를 바꾸지 말 것",
            "payload에 없는 사실을 추가하지 말 것",
            "과장 표현을 쓰지 말 것",
            "데이터 부족 시 판단 보류를 명시할 것",
        ],
    }
    return payload


def _build_management_snapshot(
    courses: dict,
    prev_courses: dict,
    actions: list[dict],
    prev_actions: list[dict],
) -> dict:
    current_breakdown = _classify_course_actions(actions, courses)
    previous_breakdown = _classify_course_actions(prev_actions, prev_courses)

    promo_slots = sum((info.get("promo_slots") or 0) for info in courses.values())
    total_slots = sum((info.get("total_slots") or 0) for info in courses.values())
    prev_promo_slots = sum((info.get("promo_slots") or 0) for info in prev_courses.values())
    prev_total_slots = sum((info.get("total_slots") or 0) for info in prev_courses.values())
    current_avg_price = _weighted_avg_price(courses)
    prev_avg_price = _weighted_avg_price(prev_courses)

    return {
        "discount_priority_courses": _movement_metric(
            previous_breakdown["discount_priority_courses"],
            current_breakdown["discount_priority_courses"],
            unit="개",
            meaning_up="즉시 할인 검토 코스 확대",
            meaning_down="즉시 할인 검토 코스 축소",
        ),
        "defense_priority_courses": _movement_metric(
            previous_breakdown["defense_priority_courses"],
            current_breakdown["defense_priority_courses"],
            unit="개",
            meaning_up="가격 방어 우선 코스 확대",
            meaning_down="가격 방어 우선 코스 축소",
        ),
        "mixed_response_courses": _movement_metric(
            previous_breakdown["mixed_response_courses"],
            current_breakdown["mixed_response_courses"],
            unit="개",
            meaning_up="혼합 대응 코스 확대",
            meaning_down="혼합 대응 코스 축소",
        ),
        "promo_ratio": _ratio_metric(
            prev_promo_slots,
            prev_total_slots,
            promo_slots,
            total_slots,
            meaning_up="할인 노출 범위 확대",
            meaning_down="할인 노출 범위 축소",
        ),
        "avg_price": _price_metric(
            prev_avg_price,
            current_avg_price,
            down_meaning="전반적 가격 인하",
            up_meaning="전반적 가격 방어",
        ),
    }


def _build_course_comparisons(
    courses: dict,
    prev_courses: dict,
    actions: list[dict],
    prev_actions: list[dict],
    strategy_profiles: list[dict],
) -> list[dict]:
    current_course_actions = _course_action_breakdown(actions)
    prev_course_actions = _course_action_breakdown(prev_actions)
    profile_map = {item["course_name"]: item for item in strategy_profiles}

    comparisons = []
    for course_name in sorted(set(courses) | set(prev_courses)):
        current = courses.get(course_name, {})
        previous = prev_courses.get(course_name, {})
        current_actions = current_course_actions.get(course_name, _empty_course_action_breakdown())
        previous_actions = prev_course_actions.get(course_name, _empty_course_action_breakdown())
        status = _determine_course_status(current_actions)
        comparisons.append(
            {
                "course_name": course_name,
                "status": status,
                "avg_price_metric": _price_metric(
                    previous.get("avg_price"),
                    current.get("avg_price"),
                    down_meaning="전반적 가격 인하",
                    up_meaning="전반적 가격 방어",
                ),
                "min_price_metric": _price_metric(
                    previous.get("min_price"),
                    current.get("min_price"),
                    down_meaning="공격적 할인 강화",
                    up_meaning="최저 판매가 상향",
                ),
                "promo_metric": _ratio_metric(
                    previous.get("promo_slots"),
                    previous.get("total_slots"),
                    current.get("promo_slots"),
                    current.get("total_slots"),
                    meaning_up="할인 적용 범위 확대",
                    meaning_down="할인 적용 범위 축소",
                ),
                "discount_days_metric": _count_metric(
                    previous_actions["discount_days"],
                    current_actions["discount_days"],
                    meaning_up="추가 대응 필요 날짜 증가",
                    meaning_down="할인 필요 구간 축소",
                ),
                "defense_days_metric": _count_metric(
                    previous_actions["defense_days"],
                    current_actions["defense_days"],
                    meaning_up="방어 가능 날짜 확대",
                    meaning_down="방어 가능 날짜 축소",
                ),
                "interpretation": _build_course_interpretation(status, current_actions),
                "today_action": _build_course_recommendation(status, current_actions),
                "confidence": _extract_profile_confidence(profile_map.get(course_name)),
            }
        )
    return comparisons


def _build_composite_issues(management_snapshot: dict, course_comparisons: list[dict]) -> list[dict]:
    issues = []
    discount_priority = sum(1 for item in course_comparisons if item["status"]["code"] == "discount")
    defense_priority = sum(1 for item in course_comparisons if item["status"]["code"] == "defense")
    mixed_priority = sum(1 for item in course_comparisons if item["status"]["code"] == "mixed")

    promo_metric = management_snapshot.get("promo_ratio") or {}
    avg_price_metric = management_snapshot.get("avg_price") or {}

    if discount_priority:
        issues.append(
            {
                "issue": "할인 검토 우선 코스 존재",
                "current_level": f"{discount_priority}개 코스",
                "change": promo_metric.get("delta_text", "변화 정보 없음"),
                "impact": "가격 인하 또는 공급 조정 판단이 필요한 코스가 존재함",
                "recommendation": "우선순위 코스부터 할인 강도와 적용 날짜를 재점검",
            }
        )
    if defense_priority:
        issues.append(
            {
                "issue": "가격 방어 가능 구간 유지",
                "current_level": f"{defense_priority}개 코스",
                "change": avg_price_metric.get("delta_text", "변화 정보 없음"),
                "impact": "무분별한 할인 확산 없이 가격 유지 여지가 남아 있음",
                "recommendation": "방어 우선 코스는 가격 유지 중심으로 운영",
            }
        )
    if mixed_priority:
        issues.append(
            {
                "issue": "날짜별 혼합 대응 필요",
                "current_level": f"{mixed_priority}개 코스",
                "change": management_snapshot.get("mixed_response_courses", {}).get("delta_text", "변화 정보 없음"),
                "impact": "같은 코스 안에서도 할인과 방어를 날짜별로 나눠 판단해야 함",
                "recommendation": "코스 단위가 아니라 날짜 단위로 가격 정책을 분리 적용",
            }
        )
    return issues


async def build_weekly_report_payload(report_date: str | None = None) -> dict:
    if report_date is None:
        report_date = date.today().isoformat()
    start_date = (date.fromisoformat(report_date) - timedelta(days=6)).isoformat()
    return await _build_period_payload("weekly", report_date, start_date)


async def build_monthly_report_payload(report_date: str | None = None) -> dict:
    if report_date is None:
        report_date = date.today().isoformat()
    start_date = (date.fromisoformat(report_date) - timedelta(days=29)).isoformat()
    return await _build_period_payload("monthly", report_date, start_date)


async def build_yearly_report_payload(report_date: str | None = None) -> dict:
    if report_date is None:
        report_date = date.today().isoformat()
    start_date = (date.fromisoformat(report_date) - timedelta(days=364)).isoformat()
    return await _build_period_payload("yearly", report_date, start_date)


def _build_confidence_note(change_summary: dict, price_response: list[dict]) -> str:
    if change_summary.get("total", 0) <= 0:
        return "가격 변동 누적 데이터 부족"
    if not price_response:
        return "할인 반응 추적 데이터 부족"
    return "일간 보고서 기준 최소 요건 충족"


def _build_course_board(courses: dict, high_defense: list[dict], repeat_discount: list[dict]) -> list[dict]:
    defense_counts = _count_by_course(high_defense)
    weakness_counts = _count_by_course(repeat_discount)

    board = []
    for course_name, info in sorted(courses.items()):
        total_slots = info.get("total_slots") or 0
        promo_slots = info.get("promo_slots") or 0
        board.append(
            {
                "course_name": course_name,
                "total_slots": total_slots,
                "promo_slots": promo_slots,
                "promo_ratio": _safe_ratio(promo_slots, total_slots),
                "min_price_krw": info.get("min_price"),
                "defense_signals": defense_counts.get(course_name, 0),
                "weakness_signals": weakness_counts.get(course_name, 0),
                "member_open_flag": None,
            }
        )
    return board


def _build_course_focus(
    courses: dict,
    high_defense: list[dict],
    repeat_discount: list[dict],
    premium_candidates: list[dict],
    member_open_alerts: list[dict],
    strategy_profiles: list[dict],
) -> list[dict]:
    focus = []
    defense_counts = _count_by_course(high_defense)
    weakness_counts = _count_by_course(repeat_discount)
    premium_counts = _count_by_course(premium_candidates)
    member_courses = {item["course_name"] for item in member_open_alerts}
    profile_map = {item["course_name"]: item for item in strategy_profiles}

    for course_name, info in sorted(courses.items()):
        signals = []
        if weakness_counts.get(course_name, 0):
            signals.append("weakness")
            headline = "할인 의존/약세 신호 존재"
        elif defense_counts.get(course_name, 0):
            signals.append("defense")
            headline = "가격 방어 신호 존재"
        elif premium_counts.get(course_name, 0):
            signals.append("premium")
            headline = "프리미엄 가능성 관찰"
        else:
            headline = "당일 특이 신호 제한적"

        if member_courses.intersection({course_name}):
            signals.append("member_open")
            headline = "회원제 공급 변화 감지"

        focus.append(
            {
                "course_name": course_name,
                "headline": headline,
                "signals": signals,
                "strategy_profile": profile_map.get(course_name),
                "key_metrics": {
                    "total_slots": info.get("total_slots") or 0,
                    "promo_ratio": _safe_ratio(info.get("promo_slots") or 0, info.get("total_slots") or 0),
                    "min_price_krw": info.get("min_price"),
                },
            }
        )
    return focus


def _build_daily_risks(change_summary: dict, price_response: list[dict], total_rows: int) -> list[dict]:
    risks = []
    if total_rows <= 0:
        risks.append({
            "risk_type": "no_data",
            "severity": "high",
            "message": "수집 데이터가 없어 일간 해석 불가",
        })
    if change_summary.get("total", 0) <= 0:
        risks.append({
            "risk_type": "data_shortage",
            "severity": "medium",
            "message": "전일 비교 데이터 부족으로 가격 변동 해석 제한",
        })
    if not price_response:
        risks.append({
            "risk_type": "response_shortage",
            "severity": "medium",
            "message": "할인 반응 평가는 추가 누적 수집 후 신뢰도 상승",
        })
    return risks


def _count_by_course(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        course_name = item.get("course_name")
        if not course_name:
            continue
        counts[course_name] = counts.get(course_name, 0) + 1
    return counts


def _compact_price_response_samples(items: list[dict]) -> list[dict]:
    samples = []
    seen = set()
    for item in items:
        key = (
            item.get("course_name"),
            item.get("play_date"),
            item.get("part_type"),
            item.get("response_grade"),
        )
        if key in seen:
            continue
        seen.add(key)
        samples.append(
            {
                "course_name": item.get("course_name"),
                "play_date": item.get("play_date"),
                "part_type": item.get("part_type"),
                "response_grade": item.get("response_grade"),
                "response_speed": item.get("response_speed"),
                "drop_rate_d3": item.get("drop_rate_d3"),
                "control_drop_rate_d3": item.get("control_drop_rate_d3"),
            }
        )
        if len(samples) >= 8:
            break
    return samples


def _safe_ratio(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 4)


def _weighted_avg_price(courses: dict) -> int | None:
    weighted_sum = 0
    total_slots = 0
    for info in courses.values():
        avg_price = info.get("avg_price")
        slots = info.get("total_slots") or 0
        if avg_price is None or slots <= 0:
            continue
        weighted_sum += int(avg_price) * slots
        total_slots += slots
    if total_slots <= 0:
        return None
    return round(weighted_sum / total_slots)


def _empty_course_action_breakdown() -> dict:
    return {
        "discount_days": 0,
        "defense_days": 0,
        "watch_days": 0,
        "supply_days": 0,
    }


def _course_action_breakdown(actions: list[dict]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for item in actions:
        course_name = item.get("course_name")
        if not course_name:
            continue
        info = grouped.setdefault(
            course_name,
            {
                "discount_days_set": set(),
                "defense_days_set": set(),
                "watch_days_set": set(),
                "supply_days_set": set(),
            },
        )
        play_date = item.get("play_date")
        action = item.get("action")
        if action in {"추가할인검토", "티수조정검토"}:
            info["discount_days_set"].add(play_date)
        elif action == "가격유지":
            info["defense_days_set"].add(play_date)
        elif action in {"관망", "추가관찰"}:
            info["watch_days_set"].add(play_date)
        elif action == "공급증가주의":
            info["supply_days_set"].add(play_date)

    result = {}
    for course_name, info in grouped.items():
        result[course_name] = {
            "discount_days": len({day for day in info["discount_days_set"] if day}),
            "defense_days": len({day for day in info["defense_days_set"] if day}),
            "watch_days": len({day for day in info["watch_days_set"] if day}),
            "supply_days": len({day for day in info["supply_days_set"] if day}),
        }
    return result


def _classify_course_actions(actions: list[dict], courses: dict) -> dict[str, int]:
    breakdown = _course_action_breakdown(actions)
    counts = {
        "discount_priority_courses": 0,
        "defense_priority_courses": 0,
        "mixed_response_courses": 0,
    }
    for course_name in set(courses) | set(breakdown):
        status = _determine_course_status(breakdown.get(course_name, _empty_course_action_breakdown()))
        if status["code"] == "discount":
            counts["discount_priority_courses"] += 1
        elif status["code"] == "defense":
            counts["defense_priority_courses"] += 1
        elif status["code"] == "mixed":
            counts["mixed_response_courses"] += 1
    return counts


def _determine_course_status(action_counts: dict) -> dict:
    discount_days = action_counts.get("discount_days", 0)
    defense_days = action_counts.get("defense_days", 0)
    if discount_days and defense_days:
        return {"code": "mixed", "label": "혼합 대응"}
    if discount_days:
        return {"code": "discount", "label": "할인 검토 우선"}
    if defense_days:
        return {"code": "defense", "label": "가격 방어 우선"}
    if action_counts.get("supply_days", 0):
        return {"code": "supply", "label": "공급 변화 관찰"}
    return {"code": "watch", "label": "추가 관찰"}


def _price_metric(
    baseline_value: int | None,
    current_value: int | None,
    *,
    down_meaning: str,
    up_meaning: str,
) -> dict:
    meaning_steady = "가격 수준 유지"
    if baseline_value is None and current_value is None:
        return _missing_metric("가격 기준 데이터 부족")
    if baseline_value is None:
        return _new_metric(current_value, meaning="당일 최초 기준")
    if current_value is None:
        return _missing_metric("현재 가격 데이터 없음")

    delta = current_value - baseline_value
    pct = round((delta / baseline_value) * 100, 1) if baseline_value else None
    if delta < 0:
        meaning = down_meaning
    elif delta > 0:
        meaning = up_meaning
    else:
        meaning = meaning_steady
    return {
        "baseline": baseline_value,
        "current": current_value,
        "baseline_text": _format_price(baseline_value),
        "current_text": _format_price(current_value),
        "arrow_text": f"{_format_price(baseline_value)} → {_format_price(current_value)}",
        "delta_text": _format_price_delta(delta, pct),
        "meaning": meaning,
        "is_missing": False,
    }


def _ratio_metric(
    baseline_numerator: int | None,
    baseline_denominator: int | None,
    current_numerator: int | None,
    current_denominator: int | None,
    *,
    meaning_up: str,
    meaning_down: str,
) -> dict:
    if not baseline_denominator and not current_denominator:
        return _missing_metric("비중 기준 데이터 부족")
    if not baseline_denominator:
        return _new_metric(
            current_numerator,
            meaning="당일 최초 기준",
            arrow_text=f"{_format_fraction(None, None)} → {_format_fraction(current_numerator, current_denominator)}",
        )

    baseline_ratio = _safe_ratio(baseline_numerator or 0, baseline_denominator or 0)
    current_ratio = _safe_ratio(current_numerator or 0, current_denominator or 0)
    delta_count = (current_numerator or 0) - (baseline_numerator or 0)
    delta_pp = round((current_ratio - baseline_ratio) * 100, 1)
    if delta_pp > 0:
        meaning = meaning_up
    elif delta_pp < 0:
        meaning = meaning_down
    else:
        meaning = "비중 유지"
    return {
        "baseline": baseline_ratio,
        "current": current_ratio,
        "baseline_text": _format_fraction(baseline_numerator, baseline_denominator),
        "current_text": _format_fraction(current_numerator, current_denominator),
        "arrow_text": f"{_format_fraction(baseline_numerator, baseline_denominator)} → {_format_fraction(current_numerator, current_denominator)}",
        "delta_text": _format_count_and_ratio_delta(delta_count, delta_pp, ratio_unit="%p"),
        "meaning": meaning,
        "is_missing": False,
    }


def _count_metric(baseline_value: int | None, current_value: int | None, *, meaning_up: str, meaning_down: str) -> dict:
    if baseline_value is None and current_value is None:
        return _missing_metric("기준 데이터 부족")
    if baseline_value is None:
        return _new_metric(current_value, meaning="당일 최초 기준", arrow_text=f"- → {current_value or 0}일")

    current_value = current_value or 0
    baseline_value = baseline_value or 0
    delta = current_value - baseline_value
    pct = round((delta / baseline_value) * 100, 1) if baseline_value else None
    if delta > 0:
        meaning = meaning_up
    elif delta < 0:
        meaning = meaning_down
    else:
        meaning = "대상 구간 유지"
    return {
        "baseline": baseline_value,
        "current": current_value,
        "baseline_text": f"{baseline_value}일",
        "current_text": f"{current_value}일",
        "arrow_text": f"{baseline_value}일 → {current_value}일",
        "delta_text": _format_count_delta(delta, pct),
        "meaning": meaning,
        "is_missing": False,
    }


def _movement_metric(
    baseline_value: int | None,
    current_value: int | None,
    *,
    unit: str,
    meaning_up: str,
    meaning_down: str,
) -> dict:
    if baseline_value is None:
        baseline_value = 0
    current_value = current_value or 0
    delta = current_value - baseline_value
    if delta > 0:
        meaning = meaning_up
    elif delta < 0:
        meaning = meaning_down
    else:
        meaning = "변동 없음"
    return {
        "baseline": baseline_value,
        "current": current_value,
        "arrow_text": f"{baseline_value}{unit} → {current_value}{unit}",
        "delta_text": f"{delta:+d}{unit}",
        "meaning": meaning,
    }


def _missing_metric(reason: str) -> dict:
    return {
        "baseline": None,
        "current": None,
        "baseline_text": "-",
        "current_text": "-",
        "arrow_text": "비교값 없음",
        "delta_text": reason,
        "meaning": "판단 보류",
        "is_missing": True,
    }


def _new_metric(current_value: int | None, *, meaning: str, arrow_text: str | None = None) -> dict:
    current_text = _format_price(current_value) if isinstance(current_value, int) else str(current_value or "-")
    return {
        "baseline": None,
        "current": current_value,
        "baseline_text": "-",
        "current_text": current_text,
        "arrow_text": arrow_text or f"- → {current_text}",
        "delta_text": "신규 관측",
        "meaning": meaning,
        "is_missing": False,
    }


def _format_price(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}원"


def _format_price_delta(delta: int, pct: float | None) -> str:
    if delta == 0:
        return "변화 없음"
    direction = "상승" if delta > 0 else "하락"
    pct_text = f"({pct:+.1f}%)" if pct is not None else ""
    return f"{abs(delta):,}원 {direction}{pct_text}"


def _format_count_delta(delta: int, pct: float | None) -> str:
    if delta == 0:
        return "변화 없음"
    pct_text = f"({pct:+.1f}%)" if pct is not None else ""
    return f"{abs(delta)}일 {'증가' if delta > 0 else '감소'}{pct_text}"


def _format_count_and_ratio_delta(delta_count: int, delta_ratio: float, *, ratio_unit: str) -> str:
    if delta_count == 0 and delta_ratio == 0:
        return "변화 없음"

    ratio_text = f"{delta_ratio:+.1f}{ratio_unit}"
    if delta_count == 0:
        return ratio_text

    count_text = f"할인 슬롯 {abs(delta_count)}개 {'증가' if delta_count > 0 else '감소'}"
    return f"{ratio_text} ({count_text})"


def _format_fraction(numerator: int | None, denominator: int | None) -> str:
    if denominator in (None, 0):
        return "-"
    return f"{numerator or 0}개/{denominator}개"


def _build_course_interpretation(status: dict, action_counts: dict) -> str:
    if status["code"] == "discount":
        return "할인 검토 신호가 가격 방어 신호보다 우세함"
    if status["code"] == "defense":
        return "할인 없이도 방어 가능한 날짜가 우세함"
    if status["code"] == "mixed":
        return "할인과 방어 신호가 함께 있어 날짜별 분리 대응이 필요함"
    if action_counts.get("supply_days", 0):
        return "회원제 오픈 등 공급 변화에 대한 관찰이 필요함"
    return "즉시 조정보다는 추가 관찰이 우선임"


def _build_course_recommendation(status: dict, action_counts: dict) -> str:
    if status["code"] == "discount":
        return "할인 날짜와 할인 폭을 우선 재점검"
    if status["code"] == "defense":
        return "가격 유지 중심으로 운영"
    if status["code"] == "mixed":
        return "날짜별로 할인과 방어 전략을 분리 적용"
    if action_counts.get("supply_days", 0):
        return "공급 증가 영향을 추가 관찰"
    return "추가 데이터 축적 후 재평가"


def _extract_profile_confidence(profile: dict | None) -> str:
    if not profile:
        return "낮음"
    amplification = profile.get("discount_amplification") or {}
    confidence = amplification.get("confidence")
    mapping = {"high": "높음", "medium": "중간", "low": "낮음"}
    return mapping.get(confidence, "중간" if amplification.get("sample_size", 0) >= 2 else "낮음")


def _merge_risks(base_risks: list[dict], extra_risks: list[dict]) -> list[dict]:
    merged = list(base_risks)
    existing = {(item.get("risk_type"), item.get("message")) for item in merged}
    for item in extra_risks:
        key = (item.get("risk_type"), item.get("message"))
        if key in existing:
            continue
        merged.append(item)
        existing.add(key)
    return merged


def _build_recommendations(actions: list[dict]) -> list[dict]:
    recommendations = []
    for item in actions[:5]:
        recommendations.append(
            {
                "type": "operation",
                "course_name": item.get("course_name"),
                "recommendation": item.get("action"),
                "basis": item.get("reason"),
            }
        )
    return recommendations


async def _build_period_payload(report_type: str, report_date: str, start_date: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        metrics = await _load_period_metrics(db, start_date, report_date)
        member_opens = await _load_member_opens(db, start_date, report_date)
        price_changes = await _load_price_changes(db, start_date, report_date)
        price_responses = await _load_price_responses(db, start_date, report_date)
    strategy_profile = await build_strategy_profiles(start_date, report_date)

    observed_days = len({row["report_date"] for row in metrics})
    courses = {row["course_name"] for row in metrics}
    total_slots = sum(row["observed_open_slots"] or 0 for row in metrics)
    promo_slots = sum(row["promo_slot_count"] or 0 for row in metrics)

    repeat_weak_slots = _build_repeated_weak_slots(metrics)
    discount_efficiency = _build_discount_efficiency(price_responses)
    competitive_position = _build_competitive_position(metrics)
    indices = _build_indices(metrics, price_responses, member_opens)
    structural_weakness_map = _build_structural_weakness_map(repeat_weak_slots)
    subcourse_dispersion = []
    actions = _build_period_actions(report_type, repeat_weak_slots, discount_efficiency, indices, member_opens)
    risks = _build_period_risks(report_type, observed_days, price_changes, price_responses)
    recommendations = _build_recommendations(actions)
    course_focus = _build_period_course_focus(metrics, repeat_weak_slots, indices, member_opens, strategy_profile.get("profiles", []))
    top_summary_section = _build_top_summary_section(report_type, summary_seed={
        "observed_days": observed_days,
        "total_slots": total_slots,
        "promo_slots": promo_slots,
        "courses": len(courses),
    }, actions=actions, indices=indices, course_focus=course_focus)
    weekly_change_section = _build_weekly_change_section(price_changes, price_responses, discount_efficiency)
    current_structure_section = _build_current_structure_section(indices, repeat_weak_slots, competitive_position)
    berhill_focus_section = _build_berhill_focus_section(metrics, indices, competitive_position, repeat_weak_slots, actions)
    action_section = _build_action_section(actions)
    data_limitations_section = _build_data_limitations_section(report_type, observed_days, price_changes, price_responses)

    evidence = {
        "repeated_weak_slots": repeat_weak_slots,
        "discount_efficiency": discount_efficiency,
        "competitive_position": competitive_position,
        "member_supply_changes": member_opens,
        "indices": indices,
        "structural_weakness_map": structural_weakness_map,
        "subcourse_dispersion": subcourse_dispersion,
        "strategy_profiles": strategy_profile.get("profiles", []),
        "metric_glossary": strategy_profile.get("glossary", []),
        "annual_price_policy_review": [],
        "discount_failure_analysis": [],
        "seasonal_elasticity": [],
        "supply_strategy_review": [],
        "next_year_strategy_inputs": [],
    }

    summary = _build_period_summary(
        report_type=report_type,
        observed_days=observed_days,
        total_slots=total_slots,
        promo_slots=promo_slots,
        courses=len(courses),
        repeat_weak_slots=repeat_weak_slots,
        discount_efficiency=discount_efficiency,
        indices=indices,
    )

    return {
        "report_type": report_type,
        "report_date": report_date,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_window": {
            "start_date": start_date,
            "end_date": report_date,
            "observed_days": observed_days,
            "is_partial_window": _is_partial_window(report_type, observed_days),
        },
        "data_quality": {
            "coverage_score": _coverage_score(report_type, observed_days),
            "missing_days": max(0, _expected_days(report_type) - observed_days),
            "missing_courses": [],
            "confidence_note": _period_confidence_note(report_type, observed_days, price_changes, price_responses),
        },
        "summary": summary,
        "actions": actions,
        "evidence": evidence,
        "top_summary_section": top_summary_section,
        "weekly_change_section": weekly_change_section,
        "current_structure_section": current_structure_section,
        "berhill_focus_section": berhill_focus_section,
        "action_section": action_section,
        "data_limitations_section": data_limitations_section,
        "risks": risks,
        "recommendations": recommendations,
        "course_focus": course_focus,
        "llm_constraints": [
            "수치를 변경하지 말 것",
            "action/severity/priority_score를 바꾸지 말 것",
            "payload에 없는 사실을 추가하지 말 것",
            "과장 표현을 쓰지 말 것",
            "데이터 부족 시 판단 보류를 명시할 것",
        ],
    }


async def _load_period_metrics(db: aiosqlite.Connection, start_date: str, end_date: str):
    async with db.execute(
        """
        SELECT *
        FROM daily_course_metrics
        WHERE report_date BETWEEN ? AND ?
          AND (membership_type IS NULL OR membership_type = '대중제')
        ORDER BY report_date, course_name, play_date, part_type
        """,
        (start_date, end_date),
    ) as cur:
        return await cur.fetchall()


async def _load_member_opens(db: aiosqlite.Connection, start_date: str, end_date: str):
    async with db.execute(
        """
        SELECT course_name, play_date, detected_at, member_slot_count, min_price_krw, max_price_krw, promo_flag
        FROM member_open_events
        WHERE detected_at BETWEEN ? AND ?
        ORDER BY detected_at, course_name, play_date
        """,
        (start_date, end_date),
    ) as cur:
        return [dict(row) for row in await cur.fetchall()]


async def _load_price_changes(db: aiosqlite.Connection, start_date: str, end_date: str):
    async with db.execute(
        """
        SELECT detected_at, course_name, play_date, tee_time, course_sub,
               event_type, delta_price_krw, delta_pct
        FROM price_change_events
        WHERE detected_at BETWEEN ? AND ?
        ORDER BY detected_at, course_name
        """,
        (start_date, end_date),
    ) as cur:
        return [dict(row) for row in await cur.fetchall()]


async def _load_price_responses(db: aiosqlite.Connection, start_date: str, end_date: str):
    async with db.execute(
        """
        SELECT event_date, course_name, play_date, part_type, event_type,
               baseline_open_slots, open_slots_d1, open_slots_d3, open_slots_d7,
               drop_rate_d1, drop_rate_d3, drop_rate_d7,
               response_grade, response_score, confidence_grade
        FROM discount_response_metrics
        WHERE event_date BETWEEN ? AND ?
        ORDER BY event_date, course_name
        """,
        (start_date, end_date),
    ) as cur:
        return [dict(row) for row in await cur.fetchall()]


def _build_repeated_weak_slots(metrics: list) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for row in metrics:
        key = (row["course_name"], row["weekday_type"], row["part_type"])
        info = grouped.setdefault(
            key,
            {"days_observed": set(), "weak_days": set(), "open_slots": 0, "promo_slots": 0, "row_count": 0},
        )
        report_day = row["report_date"]
        info["days_observed"].add(report_day)
        open_slots = row["observed_open_slots"] or 0
        promo_slots = row["promo_slot_count"] or 0
        info["open_slots"] += open_slots
        info["promo_slots"] += promo_slots
        info["row_count"] += 1
        if open_slots >= 6 or _safe_ratio(promo_slots, open_slots) >= 0.5:
            info["weak_days"].add(report_day)

    results = []
    for (course_name, weekday_type, part_type), info in grouped.items():
        observed_days = len(info["days_observed"])
        weak_days = len(info["weak_days"])
        if observed_days < 2:
            continue
        score = _safe_ratio(weak_days, observed_days)
        if score < 0.5:
            continue
        results.append(
            {
                "course_name": course_name,
                "weekday_type": weekday_type,
                "part_type": part_type,
                "course_sub": None,
                "days_observed": observed_days,
                "weak_days": weak_days,
                "repeated_weakness_score": round(score, 4),
                "avg_open_slots": round(info["open_slots"] / info["row_count"], 1),
                "avg_promo_ratio": round(_safe_ratio(info["promo_slots"], info["open_slots"]), 4),
            }
        )
    return sorted(results, key=lambda item: (-item["repeated_weakness_score"], -item["avg_open_slots"], item["course_name"]))


def _build_discount_efficiency(price_responses: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    weights = {"강함": 1.0, "보통": 0.6, "약함": 0.3, "없음": 0.0, "판단보류": 0.0}
    for row in price_responses:
        info = grouped.setdefault(row["course_name"], {"total": 0, "weighted_sum": 0.0, "strong": 0, "weak_or_none": 0})
        grade = row.get("response_grade") or "판단보류"
        info["total"] += 1
        info["weighted_sum"] += weights.get(grade, 0.0)
        if grade == "강함":
            info["strong"] += 1
        if grade in {"약함", "없음", "판단보류"}:
            info["weak_or_none"] += 1
    results = []
    for course_name, info in grouped.items():
        total = info["total"]
        results.append(
            {
                "course_name": course_name,
                "discount_efficiency_index": round(info["weighted_sum"] / total, 4) if total else 0.0,
                "total_events": total,
                "strong_events": info["strong"],
                "weak_or_none_events": info["weak_or_none"],
            }
        )
    return sorted(results, key=lambda item: (-item["discount_efficiency_index"], item["course_name"]))


def _build_competitive_position(metrics: list) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for row in metrics:
        key = (row["course_name"], row["part_type"])
        info = grouped.setdefault(key, {"price_sum": 0.0, "count": 0, "open_sum": 0})
        info["price_sum"] += row["avg_price_krw"] or 0
        info["open_sum"] += row["observed_open_slots"] or 0
        info["count"] += 1
    rows = []
    for (course_name, part_type), info in grouped.items():
        count = info["count"] or 1
        avg_price = info["price_sum"] / count
        avg_open = info["open_sum"] / count
        rows.append(
            {
                "course_name": course_name,
                "segment": part_type,
                "avg_price": round(avg_price, 1),
                "avg_open_slots": round(avg_open, 1),
            }
        )
    for segment in {item["segment"] for item in rows}:
        seg_rows = [item for item in rows if item["segment"] == segment]
        sorted_price = sorted(seg_rows, key=lambda item: (-item["avg_price"], item["course_name"]))
        sorted_defense = sorted(seg_rows, key=lambda item: (item["avg_open_slots"], item["course_name"]))
        for rank, item in enumerate(sorted_price, start=1):
            item["avg_price_rank"] = rank
        for rank, item in enumerate(sorted_defense, start=1):
            item["defense_rank"] = rank
            item["discount_dependency_rank"] = len(seg_rows) - rank + 1
            item["position_label"] = "고가 방어형" if item["avg_price_rank"] <= 2 and item["defense_rank"] <= 2 else "혼합형"
    return sorted(rows, key=lambda item: (item["segment"], item["course_name"]))


def _build_indices(metrics: list, price_responses: list[dict], member_opens: list[dict]) -> dict:
    by_course: dict[str, dict] = {}
    for row in metrics:
        info = by_course.setdefault(
            row["course_name"],
            {"total": 0, "defense_hits": 0, "promo_total": 0, "high_price_total": 0, "high_price_hits": 0, "avg_prices": [], "open_slots": []},
        )
        info["total"] += 1
        open_slots = row["observed_open_slots"] or 0
        promo_slots = row["promo_slot_count"] or 0
        info["promo_total"] += promo_slots
        info["open_slots"].append(open_slots)
        if row["discount_event_flag"] == 0 and open_slots <= 3:
            info["defense_hits"] += 1
        avg_price = row["avg_price_krw"] or 0
        info["avg_prices"].append(avg_price)
    for course_name, info in by_course.items():
        avg_of_avg = sum(info["avg_prices"]) / len(info["avg_prices"]) if info["avg_prices"] else 0
        for avg_price, open_slots in zip(info["avg_prices"], info["open_slots"]):
            if avg_price >= avg_of_avg * 1.1:
                info["high_price_total"] += 1
                if open_slots <= 4:
                    info["high_price_hits"] += 1

    response_group = {item["course_name"]: item for item in _build_discount_efficiency(price_responses)}
    member_counts: dict[str, int] = {}
    for item in member_opens:
        member_counts[item["course_name"]] = member_counts.get(item["course_name"], 0) + 1

    def make_rows(value_fn, label_fn):
        rows = []
        for course_name, info in by_course.items():
            value = value_fn(course_name, info)
            rows.append({"course_name": course_name, "value": round(value, 4), "grade": _grade_index(value), "label": label_fn(value)})
        return sorted(rows, key=lambda item: (-item["value"], item["course_name"]))

    return {
        "price_defense_index": make_rows(
            lambda _cn, info: _safe_ratio(info["defense_hits"], info["total"]),
            lambda value: "가격 방어 우수" if value >= 0.75 else "가격 방어 보통" if value >= 0.5 else "가격 방어 약함",
        ),
        "discount_dependency_index": make_rows(
            lambda _cn, info: _safe_ratio(info["promo_total"], sum(info["open_slots"])),
            lambda value: "할인 의존 높음" if value >= 0.5 else "할인 의존 보통" if value >= 0.2 else "할인 의존 낮음",
        ),
        "false_discount_rate": make_rows(
            lambda cn, _info: _safe_ratio(
                response_group.get(cn, {}).get("weak_or_none_events", 0),
                response_group.get(cn, {}).get("total_events", 0),
            ),
            lambda value: "허수 할인 높음" if value >= 0.6 else "허수 할인 보통" if value >= 0.3 else "허수 할인 낮음",
        ),
        "premium_acceptance_score": make_rows(
            lambda _cn, info: _safe_ratio(info["high_price_hits"], info["high_price_total"]),
            lambda value: "프리미엄 허용 높음" if value >= 0.6 else "프리미엄 허용 보통" if value >= 0.3 else "프리미엄 허용 낮음",
        ),
        "supply_shock_score": make_rows(
            lambda cn, _info: min(1.0, member_counts.get(cn, 0) / 3),
            lambda value: "공급 충격 높음" if value >= 0.66 else "공급 충격 보통" if value >= 0.33 else "공급 충격 낮음",
        ),
    }


def _build_structural_weakness_map(repeated_weak_slots: list[dict]) -> list[dict]:
    return [
        {
            "course_name": item["course_name"],
            "segment": f"{item['weekday_type']} {item['part_type']}",
            "score": item["repeated_weakness_score"],
            "avg_open_slots": item["avg_open_slots"],
        }
        for item in repeated_weak_slots[:10]
    ]


def _build_period_actions(report_type: str, repeated_weak_slots: list[dict], discount_efficiency: list[dict], indices: dict, member_opens: list[dict]) -> list[dict]:
    efficiency_map = {item["course_name"]: item for item in discount_efficiency}
    false_discount_map = {item["course_name"]: item for item in indices.get("false_discount_rate", [])}
    actions = []
    for item in repeated_weak_slots[:5]:
        score = int(50 + item["repeated_weakness_score"] * 40)
        efficiency = efficiency_map.get(item["course_name"], {})
        false_discount = false_discount_map.get(item["course_name"], {})
        weak_response = efficiency.get("weak_or_none_events", 0) >= max(1, efficiency.get("strong_events", 0))
        action_name = "티수조정검토" if report_type in {"monthly", "yearly"} else "추가할인검토"
        standard_action = "할인 효과 재검토" if weak_response and false_discount.get("value", 0) >= 0.5 else "소폭 할인 실험"
        primary_axis = "discount_label_issue" if standard_action == "할인 효과 재검토" else "part_structure_issue"
        secondary_axis = "price_issue"
        actions.append({
            "priority_rank": 0,
            "priority_score": score,
            "severity": "high" if score >= 75 else "medium",
            "action": action_name,
            "standard_action": standard_action,
            "primary_cause_axis": primary_axis,
            "secondary_cause_axis": secondary_axis,
            "report_group": "discount_recheck_segments" if standard_action == "할인 효과 재검토" else "discount_test_segments",
            "course_name": item["course_name"],
            "play_date": None,
            "part_type": item["part_type"],
            "course_sub": item.get("course_sub"),
            "membership_type": None,
            "reason": "반복 약세 구간 관측",
            "source_signal": "repeated_weak_slots",
            "evidence": {
                "weekday_type": item["weekday_type"],
                "repeated_weakness_score": item["repeated_weakness_score"],
                "avg_open_slots": item["avg_open_slots"],
            },
        })
    for item in member_opens[:3]:
        actions.append({
            "priority_rank": 0,
            "priority_score": 70,
            "severity": "medium",
            "action": "공급증가주의",
            "standard_action": "공급 공개/배정 점검",
            "primary_cause_axis": "supply_issue",
            "secondary_cause_axis": None,
            "report_group": "supply_check_segments",
            "course_name": item["course_name"],
            "play_date": item["play_date"],
            "part_type": None,
            "course_sub": None,
            "membership_type": "회원제",
            "reason": "회원제 오픈 누적 관측",
            "source_signal": "member_supply_changes",
            "evidence": {
                "member_slot_count": item["member_slot_count"],
                "promo_flag": item["promo_flag"],
            },
        })
    pdi = indices.get("price_defense_index", [])
    if pdi:
        top = pdi[0]
        if top["value"] >= 0.5:
            actions.append({
                "priority_rank": 0,
                "priority_score": 64,
                "severity": "medium",
                "action": "가격유지",
                "standard_action": "가격 유지",
                "primary_cause_axis": "price_issue",
                "secondary_cause_axis": None,
                "report_group": "hold_segments",
                "course_name": top["course_name"],
                "play_date": None,
                "part_type": None,
                "course_sub": None,
                "membership_type": None,
                "reason": top["label"],
                "source_signal": "price_defense_index",
                "evidence": {"value": top["value"]},
            })
    fdr = indices.get("false_discount_rate", [])
    if fdr:
        candidate = fdr[0]
        if candidate["value"] >= 0.6:
            actions.append({
                "priority_rank": 0,
                "priority_score": 62,
                "severity": "medium",
                "action": "할인표기재검토",
                "standard_action": "프로모션 메시지 정합화",
                "primary_cause_axis": "discount_label_issue",
                "secondary_cause_axis": "price_issue",
                "report_group": "promo_alignment_segments",
                "course_name": candidate["course_name"],
                "play_date": None,
                "part_type": None,
                "course_sub": None,
                "membership_type": None,
                "reason": candidate["label"],
                "source_signal": "false_discount_rate",
                "evidence": {"value": candidate["value"]},
            })
    ranked = sorted(actions, key=lambda item: (-item["priority_score"], item.get("course_name") or ""))
    for idx, item in enumerate(ranked, start=1):
        item["priority_rank"] = idx
    return ranked


def _build_top_summary_section(report_type: str, summary_seed: dict, actions: list[dict], indices: dict, course_focus: list[dict]) -> dict:
    key_actions = [
        {
            "course_name": item.get("course_name"),
            "part_type": item.get("part_type"),
            "action": item.get("standard_action") or item.get("action"),
            "reason": item.get("reason"),
        }
        for item in actions[:5]
    ]
    berhill_focus = next((item for item in course_focus if item.get("course_name") == "베르힐"), None)
    defense_rows = indices.get("price_defense_index", [])
    top_defense = defense_rows[0]["course_name"] if defense_rows else None
    conclusion = (
        f"{report_type} 기준 {summary_seed['courses']}개 코스를 관측했고 "
        f"{summary_seed['promo_slots']}개 할인 슬롯과 {summary_seed['total_slots']}개 전체 슬롯을 기반으로 판단했다."
    )
    return {
        "one_line_conclusion": conclusion,
        "berhill_headline": berhill_focus["headline"] if berhill_focus else "베르힐 데이터 추가 관찰 필요",
        "priority_actions": key_actions,
        "top_price_defense_course": top_defense,
    }


def _build_weekly_change_section(price_changes: list[dict], price_responses: list[dict], discount_efficiency: list[dict]) -> dict:
    by_course: dict[str, dict] = {}
    for item in price_changes:
        info = by_course.setdefault(
            item["course_name"],
            {"changes": 0, "net_delta": 0, "cuts": 0, "raises": 0, "event_types": set()},
        )
        info["changes"] += 1
        info["net_delta"] += item.get("delta_price_krw") or 0
        info["event_types"].add(item.get("event_type"))
        if (item.get("delta_price_krw") or 0) < 0:
            info["cuts"] += 1
        elif (item.get("delta_price_krw") or 0) > 0:
            info["raises"] += 1
    price_change_summary = [
        {
            "course_name": course_name,
            "change_count": info["changes"],
            "net_delta_krw": info["net_delta"],
            "cuts": info["cuts"],
            "raises": info["raises"],
            "event_types": sorted(info["event_types"]),
        }
        for course_name, info in sorted(by_course.items())
    ]
    response_after_change = []
    weak_after_discount = []
    for item in price_responses:
        sample = {
            "course_name": item.get("course_name"),
            "play_date": item.get("play_date"),
            "part_type": item.get("part_type"),
            "baseline_open_slots": item.get("baseline_open_slots"),
            "open_slots_d1": item.get("open_slots_d1"),
            "open_slots_d3": item.get("open_slots_d3"),
            "drop_rate_d3": item.get("drop_rate_d3"),
            "response_grade": item.get("response_grade"),
            "confidence_grade": item.get("confidence_grade"),
        }
        if item.get("response_grade") in {"강함", "보통"}:
            response_after_change.append(sample)
        elif item.get("response_grade") in {"약함", "없음", "판단보류"}:
            weak_after_discount.append(sample)
    return {
        "price_change_summary": price_change_summary[:10],
        "discount_intervention_summary": discount_efficiency[:8],
        "response_after_change_summary": response_after_change[:8],
        "weak_response_summary": weak_after_discount[:8],
    }


def _build_current_structure_section(indices: dict, repeated_weak_slots: list[dict], competitive_position: list[dict]) -> dict:
    course_type_map = []
    defense_map = {item["course_name"]: item for item in indices.get("price_defense_index", [])}
    dependency_map = {item["course_name"]: item for item in indices.get("discount_dependency_index", [])}
    false_discount_map = {item["course_name"]: item for item in indices.get("false_discount_rate", [])}
    all_courses = sorted(set(defense_map) | set(dependency_map) | set(false_discount_map))
    for course_name in all_courses:
        defense = defense_map.get(course_name, {}).get("value", 0)
        dependency = dependency_map.get(course_name, {}).get("value", 0)
        false_discount = false_discount_map.get(course_name, {}).get("value", 0)
        if defense >= 0.6 and dependency < 0.2:
            label = "가격 유지형"
        elif dependency >= 0.5 and false_discount < 0.5:
            label = "할인 의존형"
        elif false_discount >= 0.5:
            label = "할인 실효 낮음형"
        else:
            label = "할인 개입형"
        course_type_map.append({"course_name": course_name, "type_label": label})
    return {
        "course_type_map": course_type_map,
        "price_defense_snapshot": indices.get("price_defense_index", []),
        "discount_dependency_snapshot": indices.get("discount_dependency_index", []),
        "competitive_position_snapshot": competitive_position[:10],
        "structural_weakness_snapshot": repeated_weak_slots[:10],
    }


def _build_berhill_focus_section(metrics: list, indices: dict, competitive_position: list[dict], repeated_weak_slots: list[dict], actions: list[dict]) -> dict:
    berhill_metrics = [row for row in metrics if row["course_name"] == "베르힐"]
    part1 = [row for row in berhill_metrics if row["part_type"] == "1부"]
    part2 = [row for row in berhill_metrics if row["part_type"] == "2부"]
    berhill_positions = [row for row in competitive_position if row["course_name"] == "베르힐"]
    berhill_weakness = [row for row in repeated_weak_slots if row["course_name"] == "베르힐"]
    berhill_actions = [row for row in actions if row.get("course_name") == "베르힐"]
    return {
        "price_trend": {
            "avg_price_krw": round(sum((row["avg_price_krw"] or 0) for row in berhill_metrics) / len(berhill_metrics), 1) if berhill_metrics else None,
            "observed_days": len({row["report_date"] for row in berhill_metrics}),
            "promo_ratio": round(
                _safe_ratio(
                    sum((row["promo_slot_count"] or 0) for row in berhill_metrics),
                    sum((row["observed_open_slots"] or 0) for row in berhill_metrics),
                ),
                4,
            ) if berhill_metrics else 0.0,
        },
        "part1_flow": {
            "avg_open_slots": round(sum((row["observed_open_slots"] or 0) for row in part1) / len(part1), 1) if part1 else None,
            "observed_days": len({row["report_date"] for row in part1}),
        },
        "part2_flow": {
            "avg_open_slots": round(sum((row["observed_open_slots"] or 0) for row in part2) / len(part2), 1) if part2 else None,
            "observed_days": len({row["report_date"] for row in part2}),
        },
        "competitive_position": berhill_positions,
        "price_hold_segments": [item for item in berhill_actions if item.get("report_group") == "hold_segments"],
        "discount_test_segments": [item for item in berhill_actions if item.get("report_group") == "discount_test_segments"],
        "discount_recheck_segments": [item for item in berhill_actions if item.get("report_group") == "discount_recheck_segments"],
        "structural_weakness": berhill_weakness,
        "price_defense_snapshot": next((item for item in indices.get("price_defense_index", []) if item["course_name"] == "베르힐"), None),
    }


def _build_action_section(actions: list[dict]) -> dict:
    grouped = {
        "hold_segments": [],
        "discount_test_segments": [],
        "discount_recheck_segments": [],
        "supply_check_segments": [],
        "promo_alignment_segments": [],
        "observation_segments": [],
    }
    for item in actions:
        key = item.get("report_group") or "observation_segments"
        grouped.setdefault(key, []).append(item)
    return grouped


def _build_data_limitations_section(report_type: str, observed_days: int, price_changes: list[dict], price_responses: list[dict]) -> dict:
    return {
        "observation_window_limit": {
            "expected_days": _expected_days(report_type),
            "observed_days": observed_days,
            "is_partial_window": observed_days < _expected_days(report_type),
        },
        "matching_limit": {
            "price_change_events": len(price_changes),
            "slot_identity_matching": "slot_identity_key 우선, legacy slot_group_key 보조",
        },
        "response_data_limit": {
            "price_response_events": len(price_responses),
            "note": "가격 변화 전후 반응은 누적 관측이 쌓일수록 신뢰도 상승",
        },
    }


def _build_period_summary(report_type: str, observed_days: int, total_slots: int, promo_slots: int, courses: int, repeat_weak_slots: list[dict], discount_efficiency: list[dict], indices: dict) -> dict:
    base = {
        "observed_days": observed_days,
        "courses_analyzed": courses,
        "total_slots": total_slots,
        "promo_slots": promo_slots,
        "promo_ratio": _safe_ratio(promo_slots, total_slots),
    }
    if report_type == "weekly":
        base.update({
            "repeat_weak_slots": len(repeat_weak_slots),
            "repeat_discount_slots": len(repeat_weak_slots),
            "effective_discounts": sum(item["strong_events"] for item in discount_efficiency),
            "ineffective_discounts": sum(item["weak_or_none_events"] for item in discount_efficiency),
        })
    elif report_type == "monthly":
        pdi = indices.get("price_defense_index", [])
        pas = indices.get("premium_acceptance_score", [])
        base.update({
            "market_type": "혼합",
            "high_risk_structural_slots": len(repeat_weak_slots),
            "premium_windows": sum(1 for item in pas if item["value"] >= 0.6),
            "top_price_defense_course": pdi[0]["course_name"] if pdi else None,
        })
    else:
        pas = indices.get("premium_acceptance_score", [])
        base.update({
            "observed_months": max(1, observed_days // 30) if observed_days else 0,
            "dominant_market_pattern": "할인 의존 혼합형" if base["promo_ratio"] >= 0.2 else "가격 방어형",
            "structural_weak_zones": len(repeat_weak_slots),
            "premium_zones": sum(1 for item in pas if item["value"] >= 0.6),
        })
    return base


def _build_period_risks(report_type: str, observed_days: int, price_changes: list[dict], price_responses: list[dict]) -> list[dict]:
    risks = []
    expected = _expected_days(report_type)
    if observed_days < expected:
        risks.append({
            "risk_type": "partial_window",
            "severity": "high" if report_type != "weekly" else "medium",
            "message": f"{report_type} 보고서는 관측일 {observed_days}일로 부분 데이터 상태",
        })
    if not price_changes:
        risks.append({
            "risk_type": "missing_price_changes",
            "severity": "medium",
            "message": "가격 변동 누적이 없어 변화 해석이 제한적",
        })
    if not price_responses:
        risks.append({
            "risk_type": "missing_price_responses",
            "severity": "medium",
            "message": "할인 반응 누적이 없어 할인 효율 해석이 제한적",
        })
    return risks


def _build_period_course_focus(metrics: list, repeated_weak_slots: list[dict], indices: dict, member_opens: list[dict], strategy_profiles: list[dict]) -> list[dict]:
    per_course: dict[str, dict] = {}
    weakness = {item["course_name"] for item in repeated_weak_slots}
    member_courses = {item["course_name"] for item in member_opens}
    pdi_map = {item["course_name"]: item for item in indices.get("price_defense_index", [])}
    ddi_map = {item["course_name"]: item for item in indices.get("discount_dependency_index", [])}
    profile_map = {item["course_name"]: item for item in strategy_profiles}
    for row in metrics:
        info = per_course.setdefault(row["course_name"], {"slots": 0, "promo": 0, "min_price": None})
        info["slots"] += row["observed_open_slots"] or 0
        info["promo"] += row["promo_slot_count"] or 0
        min_price = row["min_price_krw"]
        if min_price is not None and (info["min_price"] is None or min_price < info["min_price"]):
            info["min_price"] = min_price
    focus = []
    for course_name, info in sorted(per_course.items()):
        headline = "누적 특이 신호 제한적"
        signals = []
        if course_name in weakness:
            headline = "반복 약세 구간 존재"
            signals.append("weakness")
        elif pdi_map.get(course_name, {}).get("value", 0) >= 0.75:
            headline = "가격 방어 강점 관측"
            signals.append("defense")
        if ddi_map.get(course_name, {}).get("value", 0) >= 0.5:
            signals.append("discount_dependency")
            headline = "할인 의존도 높음"
        if course_name in member_courses:
            signals.append("member_open")
            headline = "회원제 공급 변화 누적"
        focus.append({
            "course_name": course_name,
            "headline": headline,
            "signals": signals,
            "strategy_profile": profile_map.get(course_name),
            "key_metrics": {
                "total_slots": info["slots"],
                "promo_ratio": _safe_ratio(info["promo"], info["slots"]),
                "min_price_krw": info["min_price"],
            },
        })
    return focus


def _grade_index(value: float) -> str:
    if value >= 0.75:
        return "strong"
    if value >= 0.5:
        return "medium"
    return "weak"


def _expected_days(report_type: str) -> int:
    return {"weekly": 7, "monthly": 30, "yearly": 365}.get(report_type, 1)


def _coverage_score(report_type: str, observed_days: int) -> float:
    return round(min(1.0, observed_days / _expected_days(report_type)), 4)


def _is_partial_window(report_type: str, observed_days: int) -> bool:
    return observed_days < _expected_days(report_type)


def _period_confidence_note(report_type: str, observed_days: int, price_changes: list[dict], price_responses: list[dict]) -> str:
    if observed_days <= 1:
        return f"{report_type} 보고서는 누적 관측 부족"
    if not price_changes:
        return "가격 변동 누적이 부족해 구조 해석 제한"
    if not price_responses:
        return "할인 반응 누적이 부족해 효율 해석 제한"
    return "누적 데이터 기반 해석 가능"
