"""
집계/룰 엔진 결과를 운영 브리핑 문장으로 변환한다.
현재는 텔레그램 1회 발송용 텍스트를 우선 생성한다.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from analytics.report_payload_builder import build_daily_report_payload

_ENV_LOADED = False


def _load_local_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    _ENV_LOADED = True


def generate_daily_brief(
    total_rows: int,
    change_summary: dict | None,
    agg_summary: dict | None,
    rule_summary: dict | None,
    report_date: str | None = None,
) -> str:
    if report_date is None:
        report_date = date.today().isoformat()

    payload = build_daily_report_payload(
        report_date=report_date,
        total_rows=total_rows,
        change_summary=change_summary,
        agg_summary=agg_summary,
        rule_summary=rule_summary,
    )
    return render_daily_text_report(payload)


def render_daily_text_report(payload: dict) -> str:
    report_date = payload.get("report_date") or date.today().isoformat()
    summary = payload.get("summary", {})
    evidence = payload.get("evidence", {})
    actions = payload.get("actions", [])
    risks = payload.get("risks", [])
    course_focus = payload.get("course_focus", [])
    course_comparisons = evidence.get("course_comparisons") or []
    lines: list[str] = [f"[카카오골프 일간 브리핑] {report_date}"]
    lines.append("1. 오늘의 한 줄 결론")
    lines.extend(_render_daily_one_line_conclusion(summary, evidence, course_comparisons))
    lines.append("2. 오늘의 가격 변화")
    lines.extend(_render_daily_price_changes(evidence, actions))
    lines.append("3. 오늘의 판매 흐름 변화")
    lines.extend(_render_daily_sales_flow(evidence, course_comparisons))
    lines.append("4. 베르힐CC 오늘 포인트")
    lines.extend(_render_daily_berhill_point(course_focus, course_comparisons, actions, evidence))
    lines.append("5. 오늘의 핵심 액션")
    lines.extend(_render_daily_core_actions(actions))
    lines.append("6. 내일 확인 포인트")
    lines.extend(_render_daily_tomorrow_checks(risks, evidence, course_comparisons))
    lines.append("[보고서 종료]")
    return "\n".join(lines)


def _render_daily_one_line_conclusion(summary: dict, evidence: dict, course_comparisons: list[dict]) -> list[str]:
    management_snapshot = summary.get("management_snapshot") or {}
    promo_metric = management_snapshot.get("promo_ratio") or {}
    avg_price_metric = management_snapshot.get("avg_price") or {}
    change_total = ((evidence.get("price_change_watch") or {}).get("total") or 0)

    first = "오늘은 큰 가격 변화가 확인되지 않았다."
    if change_total > 0:
        first = f"오늘은 가격 조정 {change_total}건이 발생했고, 코스별 반응 차이를 바로 확인해야 하는 날이다."
    if (promo_metric.get("current") or 0) > (promo_metric.get("baseline") or 0) and (avg_price_metric.get("current") or 0) < (avg_price_metric.get("baseline") or 0):
        first = "오늘은 할인 노출이 넓어지고 평균가가 내려가, 추가 할인보다 선별 대응이 중요한 날이다."

    key_courses = _list_courses_from_comparisons(course_comparisons, {"discount", "defense", "mixed"})
    second = f"핵심 관찰 코스는 {key_courses}이다." if key_courses else "핵심 관찰 코스는 오늘 기준 추가 확인이 필요하다."
    return [f"- {first}", f"- {second}"]


def _render_daily_price_changes(evidence: dict, actions: list[dict]) -> list[str]:
    price_watch = evidence.get("price_change_watch") or {}
    by_course = price_watch.get("by_course") or {}
    changed_courses = _format_course_names(sorted(by_course))
    by_type = price_watch.get("by_type") or {}
    promo_courses = _format_course_names(_collect_courses_by_action(actions, {"추가할인검토", "티수조정검토"}))
    lines = []

    if changed_courses:
        lines.append(f"- 가격이 바뀐 골프장: {changed_courses}.")
    else:
        lines.append("- 가격이 바뀐 골프장은 오늘 기준 확인 안 됨.")

    if (by_type.get("특가부착", 0) or 0) > 0 or promo_courses:
        lines.append(f"- 새 특가 또는 추가할인 검토가 걸린 곳: {promo_courses or '오늘 기준 확인 안 됨'}.")
    else:
        lines.append("- 새 특가 또는 추가할인 검토 구간은 오늘 기준 뚜렷하지 않다.")

    biggest_cut = price_watch.get("largest_cut")
    if biggest_cut:
        lines.append(
            f"- 최대 인하 구간은 {biggest_cut.get('course_name')} {biggest_cut.get('play_date')} {biggest_cut.get('tee_time')}이며 {biggest_cut.get('delta_price_krw', 0):+,}원 조정됐다."
        )
    return lines


def _render_daily_sales_flow(evidence: dict, course_comparisons: list[dict]) -> list[str]:
    discount_response = evidence.get("discount_response") or {}
    samples = discount_response.get("samples") or []
    faster = [item for item in samples if item.get("response_grade") in {"강함", "보통"}]
    weaker = [item for item in samples if item.get("response_grade") in {"약함", "없음"}]
    defense_courses = _list_courses_from_comparisons(course_comparisons, {"defense"})

    lines = []
    lines.append(
        f"- 가격 변화 후 판매 흐름이 빨라진 구간: {_format_response_targets(faster) or '오늘 기준 확인 안 됨'}."
    )
    lines.append(
        f"- 할인했는데도 반응이 약한 구간: {_format_response_targets(weaker) or '오늘 기준 확인 안 됨'}."
    )
    lines.append(
        f"- 할인 없이도 잘 팔리는 구간: {defense_courses or '오늘 기준 확인 안 됨'}."
    )
    return lines


def _render_daily_berhill_point(
    course_focus: list[dict],
    course_comparisons: list[dict],
    actions: list[dict],
    evidence: dict,
) -> list[str]:
    berhill_focus = next((item for item in course_focus if item.get("course_name") == "베르힐"), None)
    berhill_compare = next((item for item in course_comparisons if item.get("course_name") == "베르힐"), None)
    berhill_actions = [item for item in actions if item.get("course_name") == "베르힐"]
    lines = []

    if berhill_compare:
        lines.append(
            f"- 베르힐CC는 현재 '{(berhill_compare.get('status') or {}).get('label', '추가 관찰')}' 흐름으로 분류된다."
        )
        lines.append(
            f"- 평균가는 {berhill_compare['avg_price_metric']['arrow_text']}이고, 오늘 판단은 {berhill_compare.get('today_action', '오늘 기준 확인 안 됨')} 쪽에 가깝다."
        )
    elif berhill_focus:
        lines.append(f"- 베르힐CC는 {berhill_focus.get('headline', '오늘 기준 확인 안 됨')} 흐름이다.")
    else:
        lines.append("- 베르힐CC는 오늘 기준 별도 포인트를 확정하기 어렵다.")

    if berhill_actions:
        first = berhill_actions[0]
        where = " / ".join(filter(None, [first.get("play_date"), first.get("part_type")]))
        lines.append(f"- 즉시 확인 구간은 {where or '오늘 구간'}이며, 현재 조치는 {first.get('action', '오늘 기준 확인 안 됨')}이다.")
    else:
        lines.append("- 베르힐CC는 내일도 가격 유지 여력과 약세 시간대가 함께 있는지 다시 확인해야 한다.")
    return lines


def _render_daily_core_actions(actions: list[dict]) -> list[str]:
    if not actions:
        return ["- 오늘 바로 실행할 액션은 오늘 기준 확인 안 됨."]

    lines = []
    seen = set()
    for item in actions:
        key = (item.get("course_name"), item.get("play_date"), item.get("part_type"), item.get("action"))
        if key in seen:
            continue
        seen.add(key)
        where = " / ".join(filter(None, [item.get("course_name"), item.get("play_date"), item.get("part_type")]))
        lines.append(f"- {where}: {item.get('action')} 검토. 이유는 {item.get('reason', '오늘 기준 확인 안 됨')}이다.")
        if len(lines) >= 3:
            break
    return lines


def _render_daily_tomorrow_checks(risks: list[dict], evidence: dict, course_comparisons: list[dict]) -> list[str]:
    lines = []
    weaker = [
        item for item in ((evidence.get("discount_response") or {}).get("samples") or [])
        if item.get("response_grade") in {"약함", "없음"}
    ]
    if weaker:
        lines.append(f"- 할인 반응이 약했던 구간은 {_format_response_targets(weaker)} 중심으로 다시 본다.")

    mixed_courses = _list_courses_from_comparisons(course_comparisons, {"mixed"})
    if mixed_courses:
        lines.append(f"- 날짜를 나눠 다시 볼 코스는 {mixed_courses}이다.")

    for item in risks[:2]:
        message = item.get("message")
        if message:
            lines.append(f"- {message}.")

    return lines or ["- 내일은 오늘 가격을 바꾼 코스의 반응이 실제 판매 속도로 이어졌는지 다시 확인한다."]


def _collect_courses_by_action(actions: list[dict], action_names: set[str]) -> list[str]:
    courses = []
    seen = set()
    for item in actions:
        if item.get("action") not in action_names:
            continue
        course_name = item.get("course_name")
        if not course_name or course_name in seen:
            continue
        seen.add(course_name)
        courses.append(course_name)
    return courses


def _list_courses_from_comparisons(course_comparisons: list[dict], status_codes: set[str]) -> str:
    names = [
        item.get("course_name")
        for item in course_comparisons
        if (item.get("status") or {}).get("code") in status_codes and item.get("course_name")
    ]
    return _format_course_names(names)


def _format_course_names(names: list[str]) -> str:
    unique = []
    seen = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        unique.append(name)
    if not unique:
        return ""
    if len(unique) <= 3:
        return ", ".join(unique)
    return f"{', '.join(unique[:3])} 외 {len(unique) - 3}곳"


def _format_response_targets(items: list[dict]) -> str:
    chunks = []
    seen = set()
    for item in items:
        course_name = item.get("course_name")
        play_date = item.get("play_date")
        part_type = item.get("part_type")
        chunk = " / ".join(filter(None, [course_name, play_date, part_type]))
        if not chunk or chunk in seen:
            continue
        seen.add(chunk)
        chunks.append(chunk)
        if len(chunks) >= 3:
            break
    if not chunks:
        return ""
    return ", ".join(chunks)


def render_weekly_text_report(payload: dict) -> str:
    report_date = payload.get("report_date") or date.today().isoformat()
    summary = payload.get("summary", {})
    actions = payload.get("actions", [])
    evidence = payload.get("evidence", {})
    risks = payload.get("risks", [])
    course_focus = payload.get("course_focus", [])

    lines = [f"[카카오골프 주간 전략 보고서] {report_date}"]
    lines.append("1. 주간 총평")
    lines.extend(_render_weekly_overview(summary, evidence, course_focus))
    lines.append("2. 가격 변화 요약")
    lines.extend(_render_weekly_price_changes(evidence, actions))
    lines.append("3. 판매 흐름 요약")
    lines.extend(_render_weekly_sales_flow(evidence))
    lines.append("4. 베르힐CC 집중 분석")
    lines.extend(_render_weekly_berhill(evidence, actions, course_focus))
    lines.append("5. 경쟁 골프장 비교")
    lines.extend(_render_weekly_competition(evidence, course_focus))
    lines.append("6. 핵심 운영 액션")
    lines.extend(_render_weekly_actions(actions, evidence))
    lines.append("7. 다음 주 확인 포인트")
    lines.extend(_render_weekly_next_checks(risks, evidence, actions))
    lines.append("[보고서 종료]")
    return "\n".join(lines)


def _render_weekly_overview(summary: dict, evidence: dict, course_focus: list[dict]) -> list[str]:
    lines = []
    total_slots = summary.get("total_slots", 0)
    promo_ratio = _format_ratio(summary.get("promo_ratio", 0.0))
    lines.append(
        f"- 이번 주는 총 {total_slots:,}슬롯을 기준으로 할인 노출이 {promo_ratio} 수준이었고, 가격 변화는 코스별로 다르게 움직였다."
    )
    weak_courses = _format_course_names(sorted({item.get('course_name') for item in (evidence.get('repeated_weak_slots') or []) if item.get('course_name')}))
    if weak_courses:
        lines.append(f"- 반복 약세 구간이 잡힌 코스는 {weak_courses}이며, 가격 변화가 판매 흐름으로 바로 이어졌는지 더 분리해 봐야 한다.")
    defense = _top_index_course(evidence, "price_defense_index")
    if defense:
        lines.append(f"- 비할인 상태에서도 상대적으로 버틴 코스는 {defense} 쪽이고, 주간 운영은 가격 유지와 할인 개입을 코스별로 나눠 보는 것이 맞다.")
    else:
        lines.append("- 이번 주는 가격 유지와 할인 개입이 혼재돼, 판매 흐름을 코스별로 다시 나눠 읽는 것이 우선이다.")
    return lines[:4]


def _render_weekly_price_changes(evidence: dict, actions: list[dict]) -> list[str]:
    competitive = evidence.get("competitive_position") or []
    repeated = evidence.get("repeated_weak_slots") or []
    defense_course = _top_index_course(evidence, "price_defense_index")
    dependency_course = _top_index_course(evidence, "discount_dependency_index")
    lines = []

    if defense_course:
        lines.append(f"- 가격 유지 골프장: {defense_course}는 비할인 상태 기본 판매력이 상대적으로 높은 편으로 읽힌다.")
    else:
        lines.append("- 가격 유지 골프장: 이번 주 기준 추가 관찰 필요.")

    discount_courses = _format_course_names(_collect_courses_by_action(actions, {"추가할인검토", "티수조정검토"}))
    lines.append(f"- 가격 인하 또는 할인 개입 골프장: {discount_courses or '이번 주 기준 추가 관찰 필요'}.")

    repeat_courses = _format_course_names([item.get("course_name") for item in repeated])
    lines.append(f"- 반복 할인 또는 반복 약세 구간: {repeat_courses or '이번 주 기준 추가 관찰 필요'}.")

    fast_discount = dependency_course or "이번 주 기준 추가 관찰 필요"
    lines.append(f"- 할인 개입이 빨랐던 골프장: {fast_discount}.")

    berl_comp = [item for item in competitive if item.get("course_name") == "베르힐"]
    if berl_comp:
        price_bits = ", ".join(
            f"{item.get('segment')} 평균가 {item.get('avg_price'):.0f}원"
            for item in berl_comp[:2]
        )
        lines.append(f"- 베르힐은 {price_bits} 수준에서 가격을 지키는 편이나, 판매 흐름은 구간별 재점검이 필요하다.")
    return lines[:5]


def _render_weekly_sales_flow(evidence: dict) -> list[str]:
    efficiency = evidence.get("discount_efficiency") or []
    strong = [item for item in efficiency if (item.get("strong_events") or 0) > 0]
    weak = [item for item in efficiency if (item.get("weak_or_none_events") or 0) > 0]
    defense = _top_index_course(evidence, "price_defense_index")
    supply = _top_index_course(evidence, "supply_shock_score")

    return [
        f"- 할인 후 판매 반응이 나타난 구간: {_format_course_names([item.get('course_name') for item in strong]) or '이번 주 기준 추가 관찰 필요'}.",
        f"- 할인했지만 반응이 약한 구간: {_format_course_names([item.get('course_name') for item in weak]) or '이번 주 기준 추가 관찰 필요'}.",
        f"- 비할인 상태에서도 잘 팔리는 구간: {defense or '이번 주 기준 추가 관찰 필요'}.",
        f"- 늦게까지 남는 시간대 또는 공급 증가 구간: {supply or '이번 주 기준 추가 관찰 필요'} 중심으로 다시 본다.",
    ]


def _render_weekly_berhill(evidence: dict, actions: list[dict], course_focus: list[dict]) -> list[str]:
    lines = []
    competitive = [item for item in (evidence.get("competitive_position") or []) if item.get("course_name") == "베르힐"]
    repeated = [item for item in (evidence.get("repeated_weak_slots") or []) if item.get("course_name") == "베르힐"]
    berl_actions = [item for item in actions if item.get("course_name") == "베르힐"]
    berl_focus = next((item for item in course_focus if item.get("course_name") == "베르힐"), None)

    price_parts = ", ".join(
        f"{item.get('segment')} 평균가 {item.get('avg_price'):.0f}원"
        for item in competitive[:2]
    ) or "이번 주 기준 추가 관찰 필요"
    lines.append(f"- 가격 변화 추이: {price_parts}.")

    part1 = [item for item in repeated if item.get("part_type") == "1부"]
    if part1:
        lines.append(f"- 1부 판매 흐름: {part1[0].get('weekday_type')} 기준 반복 약세 점수 {_format_ratio(part1[0].get('repeated_weakness_score', 0.0))}로 이번 주 재점검이 필요하다.")
    else:
        lines.append("- 1부 판매 흐름: 이번 주 기준 추가 관찰 필요.")

    part2 = [item for item in repeated if item.get("part_type") == "2부"]
    if part2:
        lines.append(f"- 2부 판매 흐름: {part2[0].get('weekday_type')} 기준 반복 약세 점수 {_format_ratio(part2[0].get('repeated_weakness_score', 0.0))}로 할인 검토 또는 티수 재점검이 필요하다.")
    else:
        lines.append("- 2부 판매 흐름: 이번 주 기준 추가 관찰 필요.")

    position = ", ".join(
        f"{item.get('segment')} 가격순위 {item.get('avg_price_rank')}위 / 방어순위 {item.get('defense_rank')}위"
        for item in competitive[:2]
    ) or "이번 주 기준 추가 관찰 필요"
    lines.append(f"- 경쟁 대비 위치: {position}.")

    if berl_actions:
        action_text = ", ".join(
            f"{item.get('part_type') or item.get('play_date') or '-'} {item.get('action')}"
            for item in berl_actions[:2]
        )
        lines.append(f"- 운영 해석: 베르힐은 {berl_focus.get('headline') if berl_focus else '주간 관찰 코스'}로 보이며, 이번 주 액션은 {action_text} 중심으로 본다.")
    else:
        lines.append(f"- 운영 해석: 베르힐은 {berl_focus.get('headline') if berl_focus else '주간 관찰 코스'}로 보이며, 이번 주는 가격 유지와 2부 재점검을 같이 본다.")
    return lines


def _render_weekly_competition(evidence: dict, course_focus: list[dict]) -> list[str]:
    indices = evidence.get("indices") or {}
    defense_map = {item["course_name"]: item for item in indices.get("price_defense_index", [])}
    dependency_map = {item["course_name"]: item for item in indices.get("discount_dependency_index", [])}
    false_map = {item["course_name"]: item for item in indices.get("false_discount_rate", [])}

    lines = []
    for item in course_focus[:8]:
        course = item.get("course_name")
        defense = defense_map.get(course, {})
        dependency = dependency_map.get(course, {})
        false_discount = false_map.get(course, {})
        label = "가격 유지형"
        if false_discount.get("value", 0) >= 0.6:
            label = "할인 실효 낮음형"
        elif dependency.get("value", 0) >= 0.5:
            label = "할인 의존형"
        elif item.get("signals") and ("weakness" in item.get("signals") or "member_open" in item.get("signals")):
            label = "할인 개입형"
        lines.append(
            f"- {course}: {label}. {defense.get('label', '이번 주 기준 추가 관찰 필요')} / {dependency.get('label', '이번 주 기준 추가 관찰 필요')} 흐름을 함께 보고 이번 주 운영 해석을 붙인다."
        )
    return lines or ["- 경쟁 골프장 비교는 이번 주 기준 추가 관찰 필요."]


def _render_weekly_actions(actions: list[dict], evidence: dict) -> list[str]:
    categories = {
        "가격 유지 가능 구간": [],
        "할인 검토 구간": [],
        "할인 효과 재점검 구간": [],
    }
    indices = evidence.get("indices") or {}
    false_map = {item["course_name"]: item for item in indices.get("false_discount_rate", [])}
    defense_items = indices.get("price_defense_index") or []

    for item in actions:
        action = item.get("action")
        course = item.get("course_name")
        if action == "가격유지":
            categories["가격 유지 가능 구간"].append(item)
        elif false_map.get(course, {}).get("value", 0) >= 0.6:
            categories["할인 효과 재점검 구간"].append(item)
        else:
            categories["할인 검토 구간"].append(item)

    if not categories["가격 유지 가능 구간"] and defense_items:
        top = defense_items[0]
        categories["가격 유지 가능 구간"].append(
            {
                "course_name": top.get("course_name"),
                "part_type": "-",
                "action": "가격유지",
                "reason": top.get("label") or "이번 주 기준 추가 관찰 필요",
            }
        )

    lines = []
    for title, items in categories.items():
        lines.append(f"- {title}")
        if not items:
            lines.append(f"- 이번 주 기준 추가 관찰 필요 / - / 유지 / 근거 부족")
            continue
        seen = set()
        for item in items:
            key = (item.get("course_name"), item.get("part_type"), item.get("play_date"), item.get("action"))
            if key in seen:
                continue
            seen.add(key)
            part = item.get("part_type") or item.get("play_date") or "-"
            lines.append(
                f"- {item.get('course_name')} / {part} / {item.get('action')} / {item.get('reason', '이번 주 기준 추가 관찰 필요')}"
            )
            if len(seen) >= 4:
                break
    return lines


def _render_weekly_next_checks(risks: list[dict], evidence: dict, actions: list[dict]) -> list[str]:
    lines = []
    weak_courses = _format_course_names([item.get("course_name") for item in (evidence.get("repeated_weak_slots") or [])])
    if weak_courses:
        lines.append(f"- 반복 약세 구간이 이어지는지 볼 코스: {weak_courses}.")
    supply_courses = _format_course_names([item.get("course_name") for item in (evidence.get("member_supply_changes") or [])])
    if supply_courses:
        lines.append(f"- 공급 변화가 가격 흐름을 흔드는지 볼 코스: {supply_courses}.")
    action_courses = _format_course_names([item.get("course_name") for item in actions if item.get("action") in {'추가할인검토', '티수조정검토'}])
    if action_courses:
        lines.append(f"- 할인 검토 후 실제 판매 반응이 붙는지 다시 볼 코스: {action_courses}.")
    for item in risks[:2]:
        message = item.get("message")
        if message:
            lines.append(f"- {message}.")
    return lines[:5] or ["- 다음 주에는 가격 변화와 판매 반응이 함께 움직이는지 다시 확인한다."]


def _top_index_course(evidence: dict, key: str) -> str:
    items = ((evidence.get("indices") or {}).get(key) or [])
    if not items:
        return ""
    return items[0].get("course_name") or ""


def render_monthly_text_report(payload: dict) -> str:
    return _render_period_report(
        payload,
        title="월간 운영 인사이트 보고서",
        section_titles=[
            "1. 월간 개요",
            "2. 핵심 액션",
            "3. 전략 프로필",
            "4. 핵심 지표",
            "5. 리스크",
            "6. 골프장 포인트",
        ],
    )


def render_yearly_text_report(payload: dict) -> str:
    return _render_period_report(
        payload,
        title="연간 운영 전략 보고서",
        section_titles=[
            "1. 연간 총평",
            "2. 핵심 액션",
            "3. 전략 프로필",
            "4. 핵심 지표",
            "5. 리스크",
            "6. 골프장 포인트",
        ],
    )


def _render_summary(summary: dict) -> list[str]:
    lines = [
        f"- 수집 티타임: {summary.get('total_rows', 0):,}개",
        f"- 골프장 수: {summary.get('total_courses', 0)}개 / 잔여 슬롯: {summary.get('total_slots', 0):,}개",
        f"- 특가 슬롯: {summary.get('promo_slots', 0):,}개 ({_format_ratio(summary.get('promo_ratio', 0.0))})",
        f"- 가격 변동: {summary.get('price_change_events', 0)}건 / 할인 반응 추적: {summary.get('price_response_events', 0)}건",
    ]
    top_signals = summary.get("top_signals") or []
    if top_signals:
        lines.append(f"- 핵심 신호: {', '.join(top_signals[:3])}")
    return lines


def _render_management_snapshot(summary: dict, management_snapshot: dict) -> list[str]:
    lines = [
        f"- 수집 티타임: {summary.get('total_rows', 0):,}개",
        f"- 골프장 수: {summary.get('total_courses', 0)}개 / 잔여 슬롯: {summary.get('total_slots', 0):,}개",
    ]
    if management_snapshot:
        lines.append(f"- 즉시 할인 검토 코스: {_render_snapshot_metric(management_snapshot.get('discount_priority_courses'))}")
        lines.append(f"- 가격 방어 우선 코스: {_render_snapshot_metric(management_snapshot.get('defense_priority_courses'))}")
        lines.append(f"- 혼합 대응 코스: {_render_snapshot_metric(management_snapshot.get('mixed_response_courses'))}")
        lines.append(f"- 전체 특가 비중: {_render_snapshot_metric(management_snapshot.get('promo_ratio'))}")
        lines.append(f"- 평균 노출가: {_render_snapshot_metric(management_snapshot.get('avg_price'))}")
        return lines
    lines.extend(_render_summary(summary)[2:])
    return lines


def _render_actions(actions: list[dict]) -> list[str]:
    if not actions:
        return ["- 즉시 액션 없음"]

    lines = []
    seen: set[tuple[str | None, str | None, str | None, str | None]] = set()
    for item in actions:
        key = (
            item.get("course_name"),
            item.get("play_date"),
            item.get("part_type"),
            item.get("action"),
        )
        if key in seen:
            continue
        seen.add(key)
        where = " / ".join(filter(None, [item.get("course_name"), item.get("play_date"), item.get("part_type")]))
        severity = _translate_severity_label(item.get("severity"))
        lines.append(
            f"- 우선순위 {severity} | {where} | {item.get('action')} | {item.get('reason')}"
        )
        if len(lines) >= _detail_limit("daily", brief=3, standard=5, detailed=7):
            break
    return lines


def _render_price_change(price_change_watch: dict) -> list[str]:
    total = price_change_watch.get("total", 0)
    by_type = price_change_watch.get("by_type") or {"인하": 0, "인상": 0, "특가부착": 0, "특가해제": 0}
    lines = [
        f"- 총 {total}건 (인하 {by_type.get('인하', 0)}, 인상 {by_type.get('인상', 0)}, "
        f"특가부착 {by_type.get('특가부착', 0)}, 특가해제 {by_type.get('특가해제', 0)})"
    ]
    biggest_cut = price_change_watch.get("largest_cut")
    if biggest_cut:
        lines.append(
            f"- 최대 인하: {biggest_cut['course_name']} {biggest_cut['play_date']} "
            f"{biggest_cut['tee_time']} {biggest_cut['delta_price_krw']:+,}원"
        )
    return lines


def _render_discount_response(discount_response: dict) -> list[str]:
    return [
        f"- 강함 {discount_response.get('strong_count', 0)}건 / "
        f"약함 {discount_response.get('weak_count', 0)}건 / "
        f"없음 {discount_response.get('none_count', 0)}건 / "
        f"보류 {discount_response.get('hold_count', 0)}건"
    ]


def _render_risks(risks: list[dict], *, report_type: str = "daily") -> list[str]:
    if not risks:
        return ["- 특별한 리스크 없음"]
    limit = _detail_limit(report_type, brief=3, standard=5, detailed=7)
    return [f"- {item.get('message', '-')}" for item in risks[:limit]]


def _render_course_focus(course_focus: list[dict], *, report_type: str = "daily") -> list[str]:
    if not course_focus:
        return ["- 골프장 포인트 없음"]

    lines = []
    limit = _detail_limit(report_type, brief=3, standard=5, detailed=7)
    for item in course_focus[:limit]:
        key_metrics = item.get("key_metrics") or {}
        min_price = key_metrics.get("min_price_krw")
        min_price_text = f"{min_price:,}원" if min_price is not None else "-"
        lines.append(
            f"- {item.get('course_name')}: {item.get('headline')} "
            f"(잔여 {key_metrics.get('total_slots', 0)}, 특가비중 {_format_ratio(key_metrics.get('promo_ratio', 0.0))}, 최저 {min_price_text})"
        )
    return lines


def _render_course_comparisons(course_comparisons: list[dict], *, include_status_codes: set[str], report_type: str = "daily") -> list[str]:
    filtered = [item for item in course_comparisons if (item.get("status") or {}).get("code") in include_status_codes]
    if not filtered:
        return ["- 해당 대상 없음"]

    lines = []
    limit = _detail_limit(report_type, brief=2, standard=5, detailed=7)
    for item in filtered[:limit]:
        lines.append(
            f"- {item.get('course_name')} | {item['status']['label']} | "
            f"평균가 {item['avg_price_metric']['arrow_text']} | {item['avg_price_metric']['delta_text']} | {item['avg_price_metric']['meaning']}"
        )
        lines.append(
            f"  최저가 {item['min_price_metric']['arrow_text']} | {item['min_price_metric']['delta_text']} | {item['min_price_metric']['meaning']}"
        )
        lines.append(
            f"  특가 {item['promo_metric']['arrow_text']} | {item['promo_metric']['delta_text']} | {item['promo_metric']['meaning']}"
        )
        lines.append(
            f"  할인대상 {item['discount_days_metric']['arrow_text']} | {item['discount_days_metric']['delta_text']} | {item['discount_days_metric']['meaning']}"
        )
        lines.append(
            f"  가격유지 {item['defense_days_metric']['arrow_text']} | {item['defense_days_metric']['delta_text']} | {item['defense_days_metric']['meaning']}"
        )
        lines.append(
            f"  해석: {item.get('interpretation')} | 조치: {item.get('today_action')} | 신뢰수준: {item.get('confidence')}"
        )
    return lines


def _render_discount_targets(course_comparisons: list[dict], *, report_type: str) -> list[str]:
    primary = [
        item for item in course_comparisons
        if (item.get("status") or {}).get("code") == "discount"
    ]
    secondary = [
        item for item in course_comparisons
        if (item.get("status") or {}).get("code") == "mixed"
        and ((item.get("discount_days_metric") or {}).get("current") or 0) > 0
    ]
    targets = primary or secondary
    if not targets:
        return ["- 해당 대상 없음"]

    lines = []
    limit = _detail_limit(report_type, brief=2, standard=4, detailed=6)
    for item in targets[:limit]:
        label = (item.get("status") or {}).get("label") or "추가 관찰"
        if (item.get("status") or {}).get("code") == "mixed":
            label = "혼합 대응이지만 할인 검토 필요"
        lines.append(
            f"- {item.get('course_name')} | {label} | 할인대상 {item['discount_days_metric']['arrow_text']} | "
            f"{item['discount_days_metric']['delta_text']} | {item['discount_days_metric']['meaning']}"
        )
        lines.append(
            f"  평균가 {item['avg_price_metric']['arrow_text']} | {item['avg_price_metric']['delta_text']} | {item['avg_price_metric']['meaning']}"
        )
        lines.append(
            f"  특가 {item['promo_metric']['arrow_text']} | {item['promo_metric']['delta_text']} | {item['promo_metric']['meaning']}"
        )
        lines.append(
            f"  조치: {item.get('today_action')} | 신뢰수준: {item.get('confidence')}"
        )
    return lines


def _render_composite_issues(issues: list[dict], *, report_type: str = "daily") -> list[str]:
    if not issues:
        return ["- 상위 복합 이슈 없음"]
    lines = []
    limit = _detail_limit(report_type, brief=2, standard=5, detailed=6)
    for item in issues[:limit]:
        lines.append(
            f"- {item.get('issue')}: 현재 {item.get('current_level')} / 변화 {item.get('change')} / "
            f"영향 {item.get('impact')} / 권고 {item.get('recommendation')}"
        )
    return lines


def _render_strategy_profiles(profiles: list[dict], *, report_type: str = "daily") -> list[str]:
    if not profiles:
        return ["- 전략 프로필 데이터 부족"]
    lines = []
    limit = _detail_limit(report_type, brief=3, standard=5, detailed=7)
    for item in profiles[:limit]:
        base = item.get("base_tier") or {}
        dep = item.get("discount_dependency") or {}
        amp = item.get("discount_amplification") or {}
        base_grade = base.get("grade")
        if not base_grade or base_grade == "N/A":
            base_grade = "판단보류"
        lines.append(
            f"- {item.get('course_name')}: 기본 체급 {base_grade} / "
            f"할인 의존도 {dep.get('label', '-')} ({_format_ratio(dep.get('value', 0.0))}) / "
            f"할인 증폭력 {amp.get('label', '-')}"
        )
    return lines


def _render_metric_glossary(glossary: list[dict], *, report_type: str = "daily") -> list[str]:
    if not glossary:
        return ["- 이번 보고서에서 새로 해설할 핵심 용어 없음"]
    lines = []
    limit = _detail_limit(report_type, brief=3, standard=4, detailed=6)
    for item in glossary[:limit]:
        lines.append(
            f"- {item.get('metric')}: {item.get('description')} {item.get('interpretation')}"
        )
    return lines


def _format_ratio(value: float) -> str:
    return f"{float(value) * 100:.0f}%"


def _render_snapshot_metric(metric: dict | None) -> str:
    if not metric:
        return "비교값 없음"
    arrow = metric.get("arrow_text")
    delta = metric.get("delta_text")
    meaning = metric.get("meaning")
    return f"{arrow} | {delta} | {meaning}"


def _render_period_report(payload: dict, *, title: str, section_titles: list[str]) -> str:
    summary = payload.get("summary", {})
    actions = payload.get("actions", [])
    evidence = payload.get("evidence", {})
    risks = payload.get("risks", [])
    course_focus = payload.get("course_focus", [])
    report_date = payload.get("report_date") or date.today().isoformat()
    report_type = payload.get("report_type") or "weekly"

    lines = [f"[카카오골프 {title}] {report_date}"]
    lines.append("0. 용어 해설")
    lines.extend(_render_metric_glossary(evidence.get("metric_glossary", []), report_type=report_type))
    lines.append(section_titles[0])
    lines.extend(_render_period_summary(summary))
    lines.append(section_titles[1])
    lines.extend(_render_period_actions(actions, report_type=report_type))
    lines.append(section_titles[2])
    lines.extend(_render_strategy_profiles(evidence.get("strategy_profiles", []), report_type=report_type))
    lines.append(section_titles[3])
    lines.extend(_render_key_indices(evidence))
    lines.append(section_titles[4])
    lines.extend(_render_risks(risks, report_type=report_type))
    lines.append(section_titles[5])
    lines.extend(_render_course_focus(course_focus, report_type=report_type))
    return "\n".join(lines)


def _render_period_actions(actions: list[dict], *, report_type: str) -> list[str]:
    if not actions:
        return ["- 즉시 액션 없음"]

    lines = []
    seen: set[tuple[str | None, str | None, str | None, str | None]] = set()
    limit = _detail_limit(report_type, brief=3, standard=5, detailed=8)
    for item in actions:
        key = (
            item.get("course_name"),
            item.get("play_date"),
            item.get("part_type"),
            item.get("action"),
        )
        if key in seen:
            continue
        seen.add(key)
        where = " / ".join(filter(None, [item.get("course_name"), item.get("play_date"), item.get("part_type")]))
        confidence = item.get("confidence") or item.get("severity") or "medium"
        lines.append(
            f"- {where} | {item.get('action')} | 근거: {item.get('reason', '-')} | 우선순위: {item.get('priority_score', '-')}"
        )
        lines.append(f"  신뢰수준: {confidence}")
        if len(seen) >= limit:
            break
    return lines


def _get_report_detail_level(report_type: str) -> str:
    _load_local_env()
    level = (
        os.getenv(f"REPORT_LLM_DETAIL_LEVEL_{report_type.upper()}")
        or os.getenv("REPORT_LLM_DETAIL_LEVEL")
        or "detailed"
    ).strip().lower()
    if level not in {"brief", "standard", "detailed"}:
        return "detailed"
    return level


def _detail_limit(report_type: str, *, brief: int, standard: int, detailed: int) -> int:
    level = _get_report_detail_level(report_type)
    if level == "brief":
        return brief
    if level == "standard":
        return standard
    return detailed


def _translate_severity_label(value: str | None) -> str:
    mapping = {
        "high": "높음",
        "medium": "중간",
        "low": "낮음",
    }
    return mapping.get((value or "").lower(), "중간")


def _render_period_summary(summary: dict) -> list[str]:
    lines = []
    if "observed_days" in summary:
        lines.append(f"- 관측일수: {summary.get('observed_days', 0)}일")
    if "courses_analyzed" in summary:
        lines.append(f"- 분석 골프장: {summary.get('courses_analyzed', 0)}개")
    if "total_slots" in summary:
        lines.append(f"- 누적 잔여 슬롯: {summary.get('total_slots', 0):,}개")
    if "promo_ratio" in summary:
        lines.append(f"- 누적 특가 비중: {_format_ratio(summary.get('promo_ratio', 0.0))}")
    metric_labels = {
        "repeat_weak_slots": "반복 약세 구간",
        "high_risk_structural_slots": "구조적 고위험 구간",
        "structural_weak_zones": "구조적 약세 구간",
        "premium_windows": "프리미엄 가능 구간",
        "premium_zones": "프리미엄 가능 구간",
    }
    for key, label in metric_labels.items():
        if key in summary:
            lines.append(f"- {label}: {summary.get(key)}개")
    if "dominant_market_pattern" in summary:
        lines.append(f"- 시장 패턴: {summary.get('dominant_market_pattern')}")
    return lines or ["- 요약 데이터 없음"]


def _render_structural_points(evidence: dict) -> list[str]:
    repeated = evidence.get("repeated_weak_slots") or []
    structural = evidence.get("structural_weakness_map") or []
    if repeated:
        lines = []
        for item in repeated[:5]:
            lines.append(
                f"- {item['course_name']} / {item['weekday_type']} / {item['part_type']} "
                f"(반복약세 {_format_ratio(item['repeated_weakness_score'])}, 평균잔여 {item['avg_open_slots']})"
            )
        return lines
    if structural:
        return [
            f"- {item['course_name']} / {item['segment']} (점수 {_format_ratio(item['score'])}, 평균잔여 {item['avg_open_slots']})"
            for item in structural[:5]
        ]
    return ["- 구조적 신호 데이터 부족"]


def _render_key_indices(evidence: dict) -> list[str]:
    indices = evidence.get("indices") or {}
    if not indices:
        efficiency = evidence.get("discount_efficiency") or []
        if efficiency:
            return [
                f"- {item['course_name']}: 할인효율 {item['discount_efficiency_index']:.2f} / 이벤트 {item['total_events']}건"
                for item in efficiency[:5]
            ]
        return ["- 지표 데이터 부족"]

    lines = []
    index_labels = {
        "price_defense_index": "가격 방어력 지수",
        "discount_dependency_index": "할인 의존도 지수",
        "false_discount_rate": "허수 할인 비율",
        "premium_acceptance_score": "고가 수용도",
        "supply_shock_score": "공급 충격 지수",
    }
    for key, label in index_labels.items():
        items = indices.get(key) or []
        if not items:
            continue
        top = items[0]
        lines.append(f"- {label}: {top['course_name']} {top['value']:.2f} ({top['label']})")
    return lines or ["- 지표 데이터 부족"]
