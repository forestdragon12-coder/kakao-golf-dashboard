"""
카카오골프 대시보드 데이터 생성기
golf.db → dashboard_data.json
매일 스크래퍼 완료 후 실행
"""
import sqlite3
import json
import statistics
from datetime import datetime, date
from collections import defaultdict

DB_PATH = "data/golf.db"
OUT_PATH = "dashboard_data.json"

MEMBER_COURSES = {
    "골드레이크": {
        "대중제": ["밸리(대중제)", "힐(대중제)"],
        "회원제": ["골드(회원제)", "레이크(회원제)"],
    },
    "해피니스": {
        "대중제": ["하트(대중제)", "힐링(대중제)", "히든(대중제)"],
        "회원제": ["해피(회원제)", "휴먼(회원제)"],
    },
}

# 서브코스 표시용 약칭 (너무 길면 UI 깨짐)
SUB_DISPLAY = {
    "밸리(대중제)": "밸리",
    "힐(대중제)":   "힐",
    "골드(회원제)": "골드",
    "레이크(회원제)":"레이크",
    "하트(대중제)":  "하트",
    "힐링(대중제)":  "힐링",
    "히든(대중제)":  "히든",
    "해피(회원제)":  "해피",
    "휴먼(회원제)":  "휴먼",
}

def get_sub_label(course_sub, membership_type):
    if course_sub in SUB_DISPLAY:
        return SUB_DISPLAY[course_sub]
    return course_sub

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def q(db, sql, params=()):
    cur = db.cursor()
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]

def scalar(db, sql, params=()):
    cur = db.cursor()
    cur.execute(sql, params)
    r = cur.fetchone()
    return r[0] if r else None

# ─────────────────────────────────────────────
# 메타데이터
# ─────────────────────────────────────────────
def get_metadata(db):
    dates = [r["collected_date"] for r in q(db,
        "SELECT DISTINCT collected_date FROM tee_time_snapshots ORDER BY collected_date")]
    latest = dates[-1] if dates else None
    prev   = dates[-2] if len(dates) >= 2 else None

    courses = [r["course_name"] for r in q(db,
        "SELECT DISTINCT course_name FROM tee_time_snapshots ORDER BY course_name")]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "latest_date": latest,
        "prev_date": prev,
        "all_dates": dates,
        "courses": courses,
        "member_courses": list(MEMBER_COURSES.keys()),
    }

# ─────────────────────────────────────────────
# V5 WRAPPER: get_tab1_all() — generates tab1 for all date pairs
# ─────────────────────────────────────────────
def get_tab1_all(db, dates):
    """V5: Generate tab1 for each consecutive date pair, keyed by date."""
    result = {}
    for i in range(len(dates)):
        latest = dates[i]
        prev = dates[i - 1] if i > 0 else None
        result[latest] = get_tab1(db, latest, prev)
    return result

# ─────────────────────────────────────────────
# TAB 1 — 오늘의 브리핑
# ─────────────────────────────────────────────
def get_tab1(db, latest, prev):
    # ── KPI: 골프장별 오늘/어제 슬롯 수 ──
    today_slots = q(db, """
        SELECT course_name,
               COUNT(*) as slots,
               ROUND(AVG(price_krw)) as avg_price,
               SUM(promo_flag) as promo_slots,
               SUM(CASE WHEN membership_type='회원제' THEN 1 ELSE 0 END) as member_slots,
               SUM(CASE WHEN membership_type='대중제' OR membership_type IS NULL THEN 1 ELSE 0 END) as public_slots
        FROM tee_time_snapshots
        WHERE collected_date = ?
        GROUP BY course_name ORDER BY course_name
    """, (latest,))

    prev_slots = {}
    if prev:
        for r in q(db, """
            SELECT course_name, COUNT(*) as slots, ROUND(AVG(price_krw)) as avg_price
            FROM tee_time_snapshots WHERE collected_date = ?
            GROUP BY course_name
        """, (prev,)):
            prev_slots[r["course_name"]] = r

    # ── 가격 변경 이벤트 (오늘 감지분) ──
    price_changes = q(db, """
        SELECT course_name, play_date, tee_time, course_sub, membership_type,
               old_price_krw, new_price_krw, delta_price_krw, delta_pct,
               event_type, promo_text_after, detected_at
        FROM price_change_events
        WHERE detected_at = ?
        ORDER BY event_type, course_name, play_date, tee_time
    """, (latest,))

    # event_type별 분류
    changes_by_type = defaultdict(list)
    for c in price_changes:
        changes_by_type[c["event_type"]].append(c)

    # 인상 이벤트에 경쟁사 동기 정보 추가
    for ev in changes_by_type.get("인상", []):
        competitor_changes = [c for c in price_changes
                              if c["course_name"] != ev["course_name"]
                              and c["event_type"] == "인상"]
        ev["competitor_same_day_raises"] = len(competitor_changes)
        ev["note"] = _infer_raise_note(ev, competitor_changes)

    # ── prev 데이터 품질 검증 ──
    # 밀도 검사: prev가 시간대당 1개만 수집됐으면 timeslot 기반 비교 전환
    consumption_data_note = None
    prev_density_mode = None  # "normal" or "sparse"
    if prev:
        density_check = q(db, """
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT play_date || '|' || tee_time || '|' || course_name) as unique_timeslots
            FROM tee_time_snapshots WHERE collected_date=?
        """, (prev,))
        if density_check:
            total_prev = density_check[0]["total"]
            unique_ts  = density_check[0]["unique_timeslots"]
            density = total_prev / unique_ts if unique_ts > 0 else 0
            if density < 1.15:
                # 시간대당 평균 1.15개 미만 → sparse (시간대당 1개만 수집된 배치)
                prev_density_mode = "sparse"
                consumption_data_note = (
                    f"ℹ️ {prev} 수집분은 시간대당 1개 슬롯만 수집되어 "
                    "고유 시간대 기준으로 비교합니다."
                )
            else:
                prev_density_mode = "normal"

    # ── 소진 현황 ──
    # sparse 모드: 고유 시간대(play_date+tee_time) 기준 비교
    # normal 모드: slot_group_key 기준 비교
    consumption = []
    if prev and prev_density_mode:
        for course in [r["course_name"] for r in today_slots]:
            # 겹치는 play_date 범위에서만 비교 (공정한 비교)
            shared_dates = q(db, """
                SELECT DISTINCT a.play_date FROM tee_time_snapshots a
                WHERE a.collected_date=? AND a.course_name=?
                AND EXISTS (SELECT 1 FROM tee_time_snapshots b
                    WHERE b.collected_date=? AND b.course_name=? AND b.play_date=a.play_date)
            """, (prev, course, latest, course))
            shared_date_set = set(r["play_date"] for r in shared_dates)

            if prev_density_mode == "sparse":
                # timeslot 기반 비교
                prev_ts = set((r["play_date"], r["tee_time"]) for r in q(db,
                    "SELECT DISTINCT play_date, tee_time FROM tee_time_snapshots WHERE collected_date=? AND course_name=?",
                    (prev, course)) if r["play_date"] in shared_date_set)
                today_ts = set((r["play_date"], r["tee_time"]) for r in q(db,
                    "SELECT DISTINCT play_date, tee_time FROM tee_time_snapshots WHERE collected_date=? AND course_name=?",
                    (latest, course)) if r["play_date"] in shared_date_set)

                consumed = len(prev_ts - today_ts)
                new_open = len(today_ts - prev_ts)
                stayed   = len(prev_ts & today_ts)
                prev_count = len(prev_ts)
                today_count = len(today_ts)
            else:
                # slot_group_key 기반 비교 (정상 모드)
                if shared_date_set:
                    sd_list = tuple(shared_date_set)
                    sd_ph = ",".join("?" * len(sd_list))
                    today_keys = set(r["slot_group_key"] for r in q(db,
                        f"SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=? AND course_name=? AND play_date IN ({sd_ph})",
                        (latest, course) + sd_list))
                    prev_keys = set(r["slot_group_key"] for r in q(db,
                        f"SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=? AND course_name=? AND play_date IN ({sd_ph})",
                        (prev, course) + sd_list))
                else:
                    today_keys = set()
                    prev_keys = set()

                consumed = len(prev_keys - today_keys)
                new_open = len(today_keys - prev_keys)
                stayed   = len(prev_keys & today_keys)
                prev_count = len(prev_keys)
                today_count = len(today_keys)

            member_new = 0
            if course in MEMBER_COURSES and prev and prev_density_mode == "normal" and shared_date_set:
                member_sub = MEMBER_COURSES[course]["회원제"]
                ms_ph = ",".join("?" * len(member_sub))
                member_new = len([r for r in q(db,
                    f"SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=? AND course_name=? AND course_sub IN ({ms_ph})",
                    (latest, course) + tuple(member_sub))
                    if r["slot_group_key"] not in prev_keys])

            consumption.append({
                "course_name": course,
                "prev_slots": prev_count,
                "today_slots": today_count,
                "consumed": consumed,
                "new_open": new_open - member_new,
                "member_open": member_new,
                "stayed": stayed,
                "consume_rate": round(consumed / prev_count * 100, 1) if prev_count else None,
                "data_quality": "ok",
                "compare_mode": "timeslot" if prev_density_mode == "sparse" else "slot_key",
            })
    else:
        note_msg = consumption_data_note or "전일 비교 데이터 없음"
        for r in today_slots:
            consumption.append({
                "course_name": r["course_name"],
                "prev_slots": None, "today_slots": r["slots"],
                "consumed": None, "new_open": None,
                "member_open": None, "stayed": None, "consume_rate": None,
                "data_quality": "unavailable",
            })
    # consumption 배열에 품질 경고 메타데이터 추가
    if consumption:
        if consumption_data_note:
            consumption[0]["data_note"] = consumption_data_note

    # ── 경보 ──
    alerts = []
    for r in today_slots:
        cn = r["course_name"]
        pv = prev_slots.get(cn)
        if pv and pv["slots"] > 0:
            ratio = r["slots"] / pv["slots"]
            if ratio < 0.30:
                alerts.append({
                    "level": "error",
                    "type": "scraper_failure",
                    "course": cn,
                    "msg": f"스크래퍼 장애 의심 — 전일 대비 {int(ratio*100)}% 수준"
                })
            elif ratio < 0.50:
                alerts.append({
                    "level": "warning",
                    "type": "supply_drop",
                    "course": cn,
                    "msg": f"공급 급감 — 전일 대비 {int(ratio*100)}% 수준"
                })

    # 대량 인하 감지
    for course, evs in changes_by_type.items():
        if course == "인하":
            course_count = defaultdict(int)
            for ev in evs:
                course_count[ev["course_name"]] += 1
            for cn, cnt in course_count.items():
                if cnt >= 5:
                    alerts.append({
                        "level": "warning",
                        "type": "mass_discount",
                        "course": cn,
                        "msg": f"대량 인하 감지 — {cnt}건"
                    })

    for ev in changes_by_type.get("인상", []):
        alerts.append({
            "level": "info",
            "type": "price_raise",
            "course": ev["course_name"],
            "msg": f"가격 인상 — {ev['course_sub']} {ev['tee_time']} {ev['old_price_krw']:,}→{ev['new_price_krw']:,}원"
        })

    member_opens = q(db,
        "SELECT * FROM member_open_events WHERE detected_at = ? ORDER BY course_name",
        (latest,))
    for mo in member_opens:
        alerts.append({
            "level": "info",
            "type": "member_open",
            "course": mo["course_name"],
            "msg": f"회원제 오픈 — {mo['play_date']} {mo['member_slot_count']}슬롯"
        })

    # ── 향후 7일 경기일 캘린더 ──
    calendar = q(db, """
        SELECT play_date, weekday_type,
               COUNT(*) as slots,
               ROUND(AVG(price_krw)) as avg_price,
               SUM(promo_flag) as promo_slots,
               MIN(d_day) as d_day
        FROM tee_time_snapshots
        WHERE collected_date = ? AND d_day <= 7
        GROUP BY play_date, weekday_type
        ORDER BY play_date
    """, (latest,))

    total_today = sum(r["slots"] for r in today_slots)
    total_prev  = sum(r["slots"] for r in prev_slots.values())
    total_changes = len(price_changes)
    total_promo = sum(r["promo_slots"] for r in today_slots)

    # 소진 요약 집계 (consumption 기반 — 공정한 비교)
    cons_total_consumed = sum(c.get("consumed") or 0 for c in consumption)
    cons_total_new_open = sum(c.get("new_open") or 0 for c in consumption)
    cons_total_prev = sum(c.get("prev_slots") or 0 for c in consumption)
    cons_total_today = sum(c.get("today_slots") or 0 for c in consumption)
    cons_rate = round(cons_total_consumed / cons_total_prev * 100, 1) if cons_total_prev > 0 else None
    cons_compare_mode = consumption[0].get("compare_mode") if consumption else None

    return {
        "kpi": {
            "total_slots_today": total_today,
            "total_slots_prev": total_prev,
            "slot_delta": total_today - total_prev if total_prev else None,
            "total_price_changes": total_changes,
            "changes_by_type": {k: len(v) for k, v in changes_by_type.items()},
            "total_promo_slots": int(total_promo),
            "promo_ratio": round(total_promo / total_today * 100, 1) if total_today else 0,
            "consume_rate": cons_rate,
            "consumed_count": cons_total_consumed,
            "new_open_count": cons_total_new_open,
            "compare_prev_slots": cons_total_prev,
            "compare_today_slots": cons_total_today,
            "compare_mode": cons_compare_mode,
        },
        "course_kpi": today_slots,
        "prev_course_kpi": prev_slots,
        "price_changes": dict(changes_by_type),
        "consumption": consumption,
        "alerts": sorted(alerts, key=lambda x: {"error": 0, "warning": 1, "info": 2}[x["level"]]),
        "calendar": calendar,
    }

def _infer_raise_note(ev, competitor_raises):
    if competitor_raises:
        return f"경쟁사 {len(competitor_raises)}곳도 동일 시점 인상 — 시장 전체 움직임 가능"
    d = ev.get("delta_pct", 0)
    if d and d > 10:
        return "큰 폭 인상 — 원인 미상, 운영진 확인 필요"
    return "경쟁사 변동 없음 — 독자 인상"

# ─────────────────────────────────────────────
# TAB 2 — 슬롯 생애주기 (2일 데이터 기반)
# ─────────────────────────────────────────────
def get_tab2(db, latest, prev):
    """2일 데이터로 슬롯 생애주기 집계"""
    # 오늘 슬롯 전체
    today_slots = q(db, """
        SELECT course_name, course_sub, membership_type, play_date, tee_time,
               price_krw, promo_flag, d_day, slot_group_key, weekday_type, part_type
        FROM tee_time_snapshots
        WHERE collected_date = ?
        ORDER BY course_name, play_date, tee_time
    """, (latest,))

    consumed_slots = []
    if prev:
        prev_keys = set(r["slot_group_key"] for r in q(db,
            "SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=?", (prev,)))
        today_keys = set(r["slot_group_key"] for r in q(db,
            "SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=?", (latest,)))

        # 오늘 슬롯 상태 분류
        for s in today_slots:
            s["status"] = "stayed" if s["slot_group_key"] in prev_keys else "new_open"

        # 소진된 슬롯 (어제 있었는데 오늘 없음)
        consumed_rows = q(db, """
            SELECT course_name, course_sub, membership_type, play_date, tee_time,
                   price_krw, promo_flag, d_day, slot_group_key, weekday_type, part_type
            FROM tee_time_snapshots
            WHERE collected_date = ?
            ORDER BY course_name, play_date, tee_time
        """, (prev,))
        consumed_slots = [r for r in consumed_rows if r["slot_group_key"] not in today_keys]
        for c in consumed_slots:
            c["status"] = "consumed"
    else:
        for s in today_slots:
            s["status"] = "first_seen"

    # 골프장별 생애주기 집계
    lifecycle_summary = defaultdict(lambda: {
        "active": 0, "consumed": 0, "new_open": 0, "stayed": 0,
        "total": 0, "avg_price": 0, "prices": []
    })

    for s in today_slots:
        cn = s["course_name"]
        lifecycle_summary[cn]["total"] += 1
        lifecycle_summary[cn]["prices"].append(s["price_krw"])
        if s["status"] == "stayed":
            lifecycle_summary[cn]["stayed"] += 1
        else:
            lifecycle_summary[cn]["new_open"] += 1

    for s in consumed_slots:
        cn = s["course_name"]
        lifecycle_summary[cn]["consumed"] += 1
        lifecycle_summary[cn]["prices"].append(s["price_krw"])

    summary_list = []
    for cn, stats in lifecycle_summary.items():
        total_observed = stats["total"] + stats["consumed"]
        stats["avg_price"] = round(statistics.mean(stats["prices"])) if stats["prices"] else 0
        del stats["prices"]
        stats["consume_rate"] = round(stats["consumed"] / total_observed * 100, 1) if total_observed > 0 else 0
        summary_list.append({"course_name": cn, **stats})
    summary_list.sort(key=lambda x: x["course_name"])

    # 경기일별 집계 (향후 7일)
    play_date_summary = q(db, """
        SELECT play_date, weekday_type,
               course_name,
               COUNT(*) as active_slots,
               ROUND(AVG(price_krw)) as avg_price,
               SUM(promo_flag) as promo_count,
               MIN(d_day) as d_day
        FROM tee_time_snapshots
        WHERE collected_date = ? AND d_day <= 14
        GROUP BY play_date, weekday_type, course_name
        ORDER BY play_date, course_name
    """, (latest,))

    return {
        "lifecycle_summary": summary_list,
        "play_date_summary": play_date_summary,
        "data_days": 2 if prev else 1,
        "latest_date": latest,
        "prev_date": prev,
    }

# ─────────────────────────────────────────────
# V5 WRAPPER: get_tab3_all() — generates tab3 for all date pairs
# ─────────────────────────────────────────────
def get_tab3_all(db, dates):
    """V5: Generate tab3 for each consecutive date pair, keyed by date."""
    result = {}
    for i in range(len(dates)):
        latest = dates[i]
        prev = dates[i - 1] if i > 0 else None
        result[latest] = get_tab3(db, latest, prev)
    return result

# ─────────────────────────────────────────────
# TAB 3 — 소진 패턴 매트릭스
# ─────────────────────────────────────────────
def get_tab3(db, latest, prev):
    """요일 × 시간대 소진 패턴 히트맵"""
    heatmap = []
    course_patterns = []

    if prev:
        prev_keys_full = q(db, """
            SELECT slot_group_key, weekday_type, part_type, course_name, price_krw, promo_flag
            FROM tee_time_snapshots WHERE collected_date=?
        """, (prev,))
        today_keys = set(r["slot_group_key"] for r in q(db,
            "SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=?", (latest,)))

        # 요일 × 파트별 소진 집계
        grid = defaultdict(lambda: {"total": 0, "consumed": 0, "promo_consumed": 0})
        for s in prev_keys_full:
            key = (s["weekday_type"], s["part_type"])
            grid[key]["total"] += 1
            if s["slot_group_key"] not in today_keys:
                grid[key]["consumed"] += 1
                if s["promo_flag"]:
                    grid[key]["promo_consumed"] += 1

        for (weekday, part), stats in grid.items():
            rate = round(stats["consumed"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
            heatmap.append({
                "weekday": weekday,
                "part": part,
                "total": stats["total"],
                "consumed": stats["consumed"],
                "consume_rate": rate,
                "promo_consumed": stats["promo_consumed"],
            })

        # 골프장별 소진 패턴
        course_grid = defaultdict(lambda: defaultdict(lambda: {"total": 0, "consumed": 0}))
        for s in prev_keys_full:
            key = (s["weekday_type"], s["part_type"])
            course_grid[s["course_name"]][key]["total"] += 1
            if s["slot_group_key"] not in today_keys:
                course_grid[s["course_name"]][key]["consumed"] += 1

        for cn, patterns in course_grid.items():
            total_all = sum(p["total"] for p in patterns.values())
            consumed_all = sum(p["consumed"] for p in patterns.values())
            course_patterns.append({
                "course_name": cn,
                "total": total_all,
                "consumed": consumed_all,
                "consume_rate": round(consumed_all / total_all * 100, 1) if total_all > 0 else 0,
                "breakdown": [{"weekday": k[0], "part": k[1], **v} for k, v in patterns.items()],
            })
        course_patterns.sort(key=lambda x: -x["consume_rate"])

    # 현재 잔여 슬롯 파트별 분포 (오늘)
    today_distribution = q(db, """
        SELECT weekday_type, part_type, COUNT(*) as slots,
               ROUND(AVG(price_krw)) as avg_price,
               SUM(promo_flag) as promo_slots
        FROM tee_time_snapshots
        WHERE collected_date = ?
        GROUP BY weekday_type, part_type
        ORDER BY weekday_type, part_type
    """, (latest,))

    return {
        "heatmap": heatmap,
        "course_patterns": course_patterns,
        "today_distribution": today_distribution,
        "data_days": 2 if prev else 1,
    }

# ─────────────────────────────────────────────
# V5: get_tab4() — already date-keyed in all_events (no change needed)
# Returns all price events; client filters by collected_date
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# TAB 4 — 가격 흐름 분석
# ─────────────────────────────────────────────
def get_tab4(db, latest):
    # D-day별 골프장별 평균가
    dday_trend = q(db, """
        SELECT course_name, d_day, weekday_type,
               ROUND(AVG(price_krw)) as avg_price,
               MIN(price_krw) as min_price,
               MAX(price_krw) as max_price,
               COUNT(*) as slot_count,
               SUM(promo_flag) as promo_count
        FROM tee_time_snapshots
        WHERE collected_date = ?
          AND (membership_type = '대중제' OR membership_type IS NULL)
          AND course_sub NOT LIKE '멤버십%'
        GROUP BY course_name, d_day, weekday_type
        ORDER BY course_name, d_day
    """, (latest,))

    # 산개도 데이터 (가격 변동 포함)
    scatter_raw = q(db, """
        SELECT course_name, price_krw, d_day, promo_flag,
               membership_type, part_type, weekday_type,
               tee_time, play_date, course_sub,
               previous_price_krw, price_changed_flag
        FROM tee_time_snapshots
        WHERE collected_date = ?
          AND (membership_type = '대중제' OR membership_type IS NULL)
          AND course_sub NOT LIKE '멤버십%'
        ORDER BY course_name, d_day
    """, (latest,))

    # 가격대 히스토그램
    histogram = defaultdict(lambda: {"total": 0, "promo": 0, "non_promo": 0})
    for r in scatter_raw:
        bucket = (r["price_krw"] // 10000) * 10000
        histogram[bucket]["total"] += 1
        if r["promo_flag"]:
            histogram[bucket]["promo"] += 1
        else:
            histogram[bucket]["non_promo"] += 1

    hist_list = [{"price_bucket": k, **v}
                 for k, v in sorted(histogram.items())]

    # 가격 변경 이벤트
    price_events = q(db, """
        SELECT course_name, play_date, tee_time, course_sub,
               old_price_krw, new_price_krw, delta_price_krw, delta_pct,
               event_type, detected_at
        FROM price_change_events
        ORDER BY detected_at, course_name
    """)

    # ── price_change_events → scatter 매핑 ──
    # tee_time_snapshots의 price_changed_flag가 누락된 경우 보정
    # key: (course_name, play_date, tee_time) → (old_price, new_price, event_type)
    _evt_map = {}
    for ev in price_events:
        ek = (ev["course_name"], ev.get("play_date"), ev.get("tee_time"))
        # 같은 슬롯에 여러 이벤트면 마지막(최신) 것 사용
        _evt_map[ek] = ev

    _patched = 0
    for r in scatter_raw:
        rk = (r["course_name"], r.get("play_date"), r.get("tee_time"))
        if rk in _evt_map and not r.get("price_changed_flag"):
            ev = _evt_map[rk]
            # 현재 가격이 이벤트의 new_price와 일치하면 매핑
            if ev.get("new_price_krw") and abs(r["price_krw"] - ev["new_price_krw"]) < 1000:
                r["price_changed_flag"] = 1
                r["previous_price_krw"] = ev["old_price_krw"]
                _patched += 1
    import logging as _lg
    _lg.getLogger(__name__).info(f"scatter price_changed_flag 보정: {_patched}건")

    # 골프장별 균등 샘플링 (최대 3000건, 모든 골프장 포함)
    # ★ 가격 변동 슬롯은 무조건 포함 (혜성 효과 보장)
    from collections import defaultdict as _dd
    _by_course = _dd(list)
    _changed_all = []
    for r in scatter_raw:
        if r.get("price_changed_flag"):
            _changed_all.append(r)
        else:
            _by_course[r["course_name"]].append(r)
    _n_courses = len(_by_course) or 1
    _remaining = 3000 - len(_changed_all)
    _per_course = max(1, _remaining // _n_courses) if _remaining > 0 else 0
    _sampled = list(_changed_all)  # 변동 슬롯 전부 포함
    for _c, _rows in _by_course.items():
        if _per_course <= 0:
            break
        if len(_rows) <= _per_course:
            _sampled.extend(_rows)
        else:
            _step = len(_rows) / _per_course
            _sampled.extend(_rows[int(i * _step)] for i in range(_per_course))
    _lg.getLogger(__name__).info(
        f"scatter 샘플링: 변동 {len(_changed_all)}건 우선 포함, "
        f"일반 {len(_sampled)-len(_changed_all)}건, 총 {len(_sampled)}건"
    )
    # d_day 기준 정렬
    _sampled.sort(key=lambda r: (r["course_name"], r["d_day"]))

    # ── 소진 판정: price_change_events 중 현재 스냅샷에 없는 것 ──
    # 판정 기준:
    #   d-day ≤ 0 (오늘 이전 경기) → 만료 (시간 지남, 소진 아님) → 제외
    #   d-day ≥ 1 + 스냅샷에 없음 → 소진 (판매 완료) → 포함
    from datetime import datetime as _dt
    _current_keys = set(
        (r["course_name"], r.get("play_date"), r.get("tee_time"))
        for r in scatter_raw
    )
    _ghost_events = []
    _expired_count = 0
    for ev in price_events:
        ek = (ev["course_name"], ev.get("play_date"), ev.get("tee_time"))
        if ek not in _current_keys and ev.get("event_type") in ("인하", "인상"):
            try:
                pd = _dt.strptime(ev["play_date"], "%Y-%m-%d").date()
                ld = _dt.strptime(latest, "%Y-%m-%d").date()
                d_day = (pd - ld).days
            except Exception:
                d_day = 0
            # d-day=0 이하는 만료 (시간대별 만료 구분 불가하므로 일괄 제외)
            if d_day <= 0:
                _expired_count += 1
                continue
            _ghost_events.append({
                "course_name": ev["course_name"],
                "price_krw": ev.get("new_price_krw", 0),
                "d_day": d_day,
                "promo_flag": 0,
                "tee_time": ev.get("tee_time"),
                "play_date": ev.get("play_date"),
                "course_sub": ev.get("course_sub"),
                "previous_price_krw": ev.get("old_price_krw"),
                "price_changed_flag": 1,
                "ghost": True,  # 소진됨 (d-day≥1인데 스냅샷에 없음)
            })
    _lg.getLogger(__name__).info(
        f"소진 고스트: {len(_ghost_events)}건 (만료 제외: {_expired_count}건)"
    )

    return {
        "dday_trend": dday_trend,
        "scatter": _sampled,
        "ghost_events": _ghost_events,
        "histogram": hist_list,
        "price_events": price_events,
    }

# ─────────────────────────────────────────────
# V5: get_tab5a() — already returns all_events (no change needed)
# Client filters by detected_at / collected_date
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# TAB 5A — 할인 반응 분석
# ─────────────────────────────────────────────
def get_tab5a(db, latest, prev):
    """할인 이벤트 분석 — 2일 데이터 기반 (Lift 계산 제한적)"""
    # 할인 이벤트 (인하 + 특가부착)
    discount_events = q(db, """
        SELECT course_name, play_date, tee_time, course_sub, membership_type,
               old_price_krw, new_price_krw, delta_price_krw, delta_pct,
               event_type, promo_text_after, detected_at
        FROM price_change_events
        WHERE event_type IN ('인하', '특가부착')
        ORDER BY course_name, delta_price_krw
    """)

    # ── 소진 상태 판정 ──
    # 현재 스냅샷 키 집합
    from datetime import datetime as _dt5
    _snap_keys = set()
    for r in q(db, """
        SELECT course_name, play_date, tee_time
        FROM tee_time_snapshots WHERE collected_date = ?
    """, (latest,)):
        _snap_keys.add((r["course_name"], r["play_date"], r["tee_time"]))

    for ev in discount_events:
        ev["discount_pct"] = abs(ev.get("delta_pct") or 0)
        ev["discount_amt"] = abs(ev.get("delta_price_krw") or 0)
        # d-day 계산
        try:
            pd = _dt5.strptime(ev["play_date"], "%Y-%m-%d").date()
            ld = _dt5.strptime(latest, "%Y-%m-%d").date()
            ev["d_day"] = (pd - ld).days
        except Exception:
            ev["d_day"] = 0
        # 상태 판정
        ek = (ev["course_name"], ev.get("play_date"), ev.get("tee_time"))
        if ev["d_day"] <= 0:
            ev["outcome"] = "expired"    # 만료 (결과 불명)
        elif ek in _snap_keys:
            ev["outcome"] = "waiting"    # 대기중 (아직 안 팔림)
        else:
            ev["outcome"] = "consumed"   # 소진 (인하 후 판매 완료)

    # ── 인하 효과 요약 ──
    _consumed = [e for e in discount_events if e["outcome"] == "consumed"]
    _waiting = [e for e in discount_events if e["outcome"] == "waiting"]
    _expired = [e for e in discount_events if e["outcome"] == "expired"]
    _actionable = len(_consumed) + len(_waiting)  # 만료 제외
    effectiveness = {
        "total_events": len(discount_events),
        "consumed": len(_consumed),
        "waiting": len(_waiting),
        "expired": len(_expired),
        "consumption_rate": round(len(_consumed) / _actionable * 100, 1) if _actionable > 0 else None,
    }

    # ── 골프장별 할인 집계 (소진율 포함) ──
    course_discount = defaultdict(lambda: {
        "event_count": 0, "avg_discount_pct": 0, "total_discount_amt": 0,
        "max_discount_pct": 0, "pcts": [],
        "consumed": 0, "waiting": 0, "expired": 0,
    })
    for ev in discount_events:
        cn = ev["course_name"]
        course_discount[cn]["event_count"] += 1
        course_discount[cn]["total_discount_amt"] += ev["discount_amt"]
        course_discount[cn]["pcts"].append(ev["discount_pct"])
        course_discount[cn][ev["outcome"]] += 1
        if ev["discount_pct"] > course_discount[cn]["max_discount_pct"]:
            course_discount[cn]["max_discount_pct"] = ev["discount_pct"]

    summary = []
    for cn, stats in course_discount.items():
        stats["avg_discount_pct"] = round(statistics.mean(stats["pcts"]), 1) if stats["pcts"] else 0
        _act = stats["consumed"] + stats["waiting"]
        stats["consumption_rate"] = round(stats["consumed"] / _act * 100, 1) if _act > 0 else None
        del stats["pcts"]
        summary.append({"course_name": cn, **stats})
    summary.sort(key=lambda x: -x["event_count"])

    # 현재 할인 슬롯 분포 (promo_flag=1)
    promo_distribution = q(db, """
        SELECT course_name, weekday_type, part_type,
               COUNT(*) as promo_slots,
               ROUND(AVG(price_krw)) as avg_promo_price,
               MIN(price_krw) as min_price
        FROM tee_time_snapshots
        WHERE collected_date = ? AND promo_flag = 1
          AND (membership_type = '대중제' OR membership_type IS NULL)
        GROUP BY course_name, weekday_type, part_type
        ORDER BY course_name, weekday_type, part_type
    """, (latest,))

    # D-day별 할인 vs 비할인 평균가 비교
    dday_comparison = q(db, """
        SELECT d_day,
               AVG(CASE WHEN promo_flag=1 THEN price_krw END) as avg_promo,
               AVG(CASE WHEN promo_flag=0 THEN price_krw END) as avg_non_promo,
               COUNT(CASE WHEN promo_flag=1 THEN 1 END) as promo_count,
               COUNT(CASE WHEN promo_flag=0 THEN 1 END) as non_promo_count
        FROM tee_time_snapshots
        WHERE collected_date = ?
          AND (membership_type = '대중제' OR membership_type IS NULL)
        GROUP BY d_day
        ORDER BY d_day
    """, (latest,))

    for r in dday_comparison:
        if r["avg_promo"] and r["avg_non_promo"]:
            r["discount_depth"] = round((1 - r["avg_promo"] / r["avg_non_promo"]) * 100, 1)
        else:
            r["discount_depth"] = None

    return {
        "discount_events": discount_events,
        "course_summary": summary,
        "effectiveness": effectiveness,
        "promo_distribution": promo_distribution,
        "dday_comparison": dday_comparison,
    }

# ─────────────────────────────────────────────
# V5 WRAPPER: get_tab5b_all() — generates tab5b for all dates
# ─────────────────────────────────────────────
def get_tab5b_all(db, dates):
    """V5: Generate tab5b for each date, keyed by date."""
    result = {}
    for date in dates:
        result[date] = get_tab5b(db, date)
    return result

# ─────────────────────────────────────────────
# TAB 5B — 수익 구조 분석
# ─────────────────────────────────────────────
def get_tab5b(db, latest):
    """Yield 분석 — 세그먼트 기대가 대비 실제 가격"""
    # 공개제 슬롯만 분석
    all_slots = q(db, """
        SELECT course_name, course_sub, weekday_type, part_type, membership_type,
               price_krw, promo_flag, d_day, play_date
        FROM tee_time_snapshots
        WHERE collected_date = ?
          AND (membership_type = '대중제' OR membership_type IS NULL)
          AND course_sub NOT LIKE '멤버십%'
        ORDER BY course_name
    """, (latest,))

    # 세그먼트별 비할인 중앙값 (기대가격)
    seg_prices = defaultdict(list)
    for s in all_slots:
        if not s["promo_flag"]:
            key = (s["course_name"], s["weekday_type"], s["part_type"])
            seg_prices[key].append(s["price_krw"])

    baselines = {}
    for key, prices in seg_prices.items():
        baselines[key] = statistics.median(prices) if prices else None

    # Yield 계산
    yield_slots = []
    for s in all_slots:
        key = (s["course_name"], s["weekday_type"], s["part_type"])
        baseline = baselines.get(key)
        # 폴백: 골프장 전체 비할인 중앙값
        if baseline is None:
            cn_prices = [x["price_krw"] for x in all_slots
                         if x["course_name"] == s["course_name"] and not x["promo_flag"]]
            baseline = statistics.median(cn_prices) if cn_prices else None

        if baseline and baseline > 0:
            yield_val = round(s["price_krw"] / baseline, 3)
            yield_slots.append({
                "course_name": s["course_name"],
                "weekday_type": s["weekday_type"],
                "part_type": s["part_type"],
                "price_krw": s["price_krw"],
                "promo_flag": s["promo_flag"],
                "yield": yield_val,
                "baseline": baseline,
                "d_day": s["d_day"],
            })

    # 골프장별 Yield 요약
    course_yield = defaultdict(lambda: {"weekday": [], "weekend": []})
    for yd in yield_slots:
        cn = yd["course_name"]
        if yd["weekday_type"] in ("토요일", "일요일", "금요일"):
            course_yield[cn]["weekend"].append(yd["yield"])
        else:
            course_yield[cn]["weekday"].append(yd["yield"])

    yield_summary = []
    for cn, data in course_yield.items():
        wday_yields = data["weekday"]
        wend_yields = data["weekend"]
        yield_summary.append({
            "course_name": cn,
            "weekday_avg_yield": round(statistics.mean(wday_yields), 3) if wday_yields else None,
            "weekend_avg_yield": round(statistics.mean(wend_yields), 3) if wend_yields else None,
            "weekday_count": len(wday_yields),
            "weekend_count": len(wend_yields),
            "promo_ratio_weekday": round(
                sum(1 for y in yield_slots if y["course_name"] == cn
                    and y["weekday_type"] not in ("토요일", "일요일", "금요일") and y["promo_flag"])
                / max(1, sum(1 for y in yield_slots if y["course_name"] == cn
                    and y["weekday_type"] not in ("토요일", "일요일", "금요일"))) * 100, 1),
        })
    yield_summary.sort(key=lambda x: x["course_name"])

    # 가격대별 할인/비할인 분포 (히스토그램)
    yield_histogram = defaultdict(lambda: {"total": 0, "promo": 0, "non_promo": 0})
    for yd in yield_slots:
        bucket = round(yd["yield"] * 10) / 10  # 0.1 단위
        yield_histogram[bucket]["total"] += 1
        if yd["promo_flag"]:
            yield_histogram[bucket]["promo"] += 1
        else:
            yield_histogram[bucket]["non_promo"] += 1

    hist_list = [{"yield_bucket": k, **v} for k, v in sorted(yield_histogram.items())]

    return {
        "yield_slots": yield_slots[:1500],
        "course_summary": yield_summary,
        "yield_histogram": hist_list,
    }

# ─────────────────────────────────────────────
# V5 WRAPPER: get_tab6_all() — generates tab6 for all date pairs
# ─────────────────────────────────────────────
def get_tab6_all(db, dates):
    """V5: Generate tab6 for each consecutive date pair, keyed by date."""
    result = {}
    for i in range(len(dates)):
        latest = dates[i]
        prev = dates[i - 1] if i > 0 else None
        result[latest] = get_tab6(db, latest, prev)
    return result

# ─────────────────────────────────────────────
# TAB 6 — 코스 × 서브코스 현황
# ─────────────────────────────────────────────
def get_tab6(db, latest, prev):
    rows = q(db, """
        SELECT course_name, course_sub, membership_type,
               COUNT(*) as slots,
               ROUND(AVG(price_krw)) as avg_price,
               MIN(price_krw) as min_price,
               MAX(price_krw) as max_price,
               SUM(promo_flag) as promo_slots,
               SUM(CASE WHEN part_type='1부' THEN 1 ELSE 0 END) as part1,
               SUM(CASE WHEN part_type='2부' THEN 1 ELSE 0 END) as part2,
               SUM(CASE WHEN weekday_type='토요일' OR weekday_type='일요일' THEN 1 ELSE 0 END) as weekend_slots,
               SUM(CASE WHEN weekday_type='평일' THEN 1 ELSE 0 END) as weekday_slots
        FROM tee_time_snapshots
        WHERE collected_date = ?
          AND course_sub NOT LIKE '멤버십%'
        GROUP BY course_name, course_sub, membership_type
        ORDER BY course_name, membership_type, course_sub
    """, (latest,))

    prev_map = {}
    if prev:
        for r in q(db, """
            SELECT course_name, course_sub, membership_type, COUNT(*) as slots,
                   ROUND(AVG(price_krw)) as avg_price
            FROM tee_time_snapshots
            WHERE collected_date = ? AND course_sub NOT LIKE '멤버십%'
            GROUP BY course_name, course_sub, membership_type
        """, (prev,)):
            key = (r["course_name"], r["course_sub"], r["membership_type"])
            prev_map[key] = r

    for r in rows:
        key = (r["course_name"], r["course_sub"], r["membership_type"])
        pv = prev_map.get(key)
        r["prev_slots"] = pv["slots"] if pv else None
        r["slot_delta"] = r["slots"] - pv["slots"] if pv else None
        r["prev_avg_price"] = pv["avg_price"] if pv else None
        r["price_delta"] = round(r["avg_price"] - pv["avg_price"]) if pv else None

        cn = r["course_name"]
        cs = r["course_sub"]
        if cn in MEMBER_COURSES:
            if cs in MEMBER_COURSES[cn]["회원제"]:
                r["member_label"] = "회원제"
            elif cs in MEMBER_COURSES[cn]["대중제"]:
                r["member_label"] = "대중제"
            else:
                r["member_label"] = "기타"
        else:
            r["member_label"] = None

        r["promo_ratio"] = round(r["promo_slots"] / r["slots"] * 100, 1) if r["slots"] else 0
        r["sub_display"] = get_sub_label(cs, r["membership_type"])

    course_summary = defaultdict(lambda: {
        "total_slots": 0, "total_promo": 0,
        "prices": [], "subcourses": [],
        "member_slots": 0, "public_slots": 0,
    })
    for r in rows:
        cn = r["course_name"]
        course_summary[cn]["total_slots"] += r["slots"]
        course_summary[cn]["total_promo"] += r["promo_slots"]
        course_summary[cn]["prices"].extend([r["min_price"]] * r["slots"])
        course_summary[cn]["subcourses"].append(r["sub_display"])
        if r["member_label"] == "회원제":
            course_summary[cn]["member_slots"] += r["slots"]
        else:
            course_summary[cn]["public_slots"] += r["slots"]

    member_opens = {}
    for mo in q(db, "SELECT * FROM member_open_events ORDER BY detected_at DESC"):
        key = (mo["course_name"], mo["play_date"])
        if key not in member_opens:
            member_opens[key] = mo

    return {
        "subcourse_rows": rows,
        "course_summary": dict(course_summary),
        "member_opens_latest": [dict(v) for v in list(member_opens.values())[:20]],
    }

# ─────────────────────────────────────────────
# V5 WRAPPER: get_tab7_all() — generates tab7 for all date pairs
# ─────────────────────────────────────────────
def get_tab7_all(db, dates):
    """V5: Generate tab7 for each consecutive date pair, keyed by date."""
    result = {}
    for i in range(len(dates)):
        latest = dates[i]
        prev = dates[i - 1] if i > 0 else None
        result[latest] = get_tab7(db, latest, prev)
    return result

# ─────────────────────────────────────────────
# TAB 7 — AI 진단
# ─────────────────────────────────────────────
def get_tab7(db, latest, prev):
    """룰 엔진 기반 AI 진단"""
    courses = [r["course_name"] for r in q(db,
        "SELECT DISTINCT course_name FROM tee_time_snapshots WHERE collected_date=? ORDER BY course_name",
        (latest,))]

    # 전일 대비 소진 데이터
    today_keys_all = set(r["slot_group_key"] for r in q(db,
        "SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=?", (latest,)))
    prev_keys_all = set(r["slot_group_key"] for r in q(db,
        "SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=?", (prev,))) if prev else set()

    all_diagnostics = []

    for course in courses:
        findings = []

        # ── 오늘 슬롯 정보 ──
        today_course = q(db, """
            SELECT slot_group_key, price_krw, promo_flag, d_day, weekday_type,
                   part_type, course_sub, membership_type
            FROM tee_time_snapshots
            WHERE collected_date=? AND course_name=?
        """, (latest, course))

        public_slots = [s for s in today_course
                        if s["membership_type"] in ("대중제", None, "단일")]

        # ── Rule A: 비할인 슬롯이 D-7 이하 많이 남아있음 (가격 유지 여력) ──
        non_promo_low_dday = [s for s in public_slots if not s["promo_flag"] and s["d_day"] <= 7]
        if len(non_promo_low_dday) >= 5:
            avg_price = round(statistics.mean(s["price_krw"] for s in non_promo_low_dday))
            findings.append({
                "rule": "A",
                "severity": "info",
                "title": "가격 유지 여력",
                "desc": f"D-7 이내 비할인 잔여 {len(non_promo_low_dday)}슬롯 (평균 {avg_price//10000:.1f}만원) — 할인 압박 낮음",
                "action": "현 가격 유지, D-3 시점 재검토 권장",
                "metric": len(non_promo_low_dday),
            })

        # ── Rule B: 동일 세그먼트 전량 특가 (할인 의존) ──
        promo_segs = q(db, """
            SELECT course_sub, weekday_type, part_type,
                   COUNT(*) as total, SUM(promo_flag) as promos
            FROM tee_time_snapshots
            WHERE collected_date=? AND course_name=?
              AND (membership_type='대중제' OR membership_type IS NULL)
            GROUP BY course_sub, weekday_type, part_type
            HAVING total >= 3 AND promos = total
        """, (latest, course))

        for ps in promo_segs:
            findings.append({
                "rule": "B",
                "severity": "warning",
                "title": "할인 의존 세그먼트",
                "desc": f"{ps['course_sub']} {ps['weekday_type']} {ps['part_type']} — {ps['total']}슬롯 전량 특가 적용 중",
                "action": "할인 축소 테스트 권장 (1~2슬롯 정가 복귀 후 반응 관찰)",
                "metric": ps["total"],
            })

        # ── Rule E: 고가 비할인 소진 감지 (프리미엄 구간) ──
        if prev:
            prev_course_keys = set(r["slot_group_key"] for r in q(db,
                "SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=? AND course_name=?",
                (prev, course)))
            today_course_keys = set(s["slot_group_key"] for s in today_course)
            consumed_keys = prev_course_keys - today_course_keys

            if consumed_keys:
                # 전일 소진된 비할인 슬롯 (subquery 방식)
                non_promo_consumed = q(db, """
                    SELECT s.price_krw, s.d_day, s.promo_flag
                    FROM tee_time_snapshots s
                    WHERE s.collected_date=? AND s.course_name=?
                      AND s.slot_group_key NOT IN (
                        SELECT slot_group_key FROM tee_time_snapshots WHERE collected_date=?
                      ) AND s.promo_flag=0
                """, (prev, course, latest))

                if len(non_promo_consumed) >= 3:
                    avg_consumed_price = round(statistics.mean(r["price_krw"] for r in non_promo_consumed))
                    all_non_promo = [s for s in public_slots if not s["promo_flag"]]
                    if all_non_promo:
                        avg_active_price = round(statistics.mean(s["price_krw"] for s in all_non_promo))
                        if avg_consumed_price >= avg_active_price * 0.95:  # 소진된 가격이 잔여 평균과 비슷하거나 높음
                            findings.append({
                                "rule": "E",
                                "severity": "info",
                                "title": "프리미엄 구간 소진",
                                "desc": f"비할인 슬롯 {len(non_promo_consumed)}건 소진 (평균 {avg_consumed_price//10000:.1f}만원) — 가격 인상 여력 검토 가능",
                                "action": "D-10 이상 구간 소폭 인상 테스트 검토",
                                "metric": avg_consumed_price,
                            })

        # ── Rule H: 회원제 오픈 감지 ──
        if course in MEMBER_COURSES:
            member_opens = q(db, """
                SELECT * FROM member_open_events
                WHERE course_name=? AND detected_at=?
            """, (course, latest))
            for mo in member_opens:
                findings.append({
                    "rule": "H",
                    "severity": "info",
                    "title": "회원제 오픈 감지",
                    "desc": f"경기일 {mo['play_date']} — {mo['member_slot_count']}슬롯 회원제 노출 시작",
                    "action": "회원제 예약 반응 추적, 대중제 가격 모니터링",
                    "metric": mo["member_slot_count"],
                })

        # ── 이상 없음 ──
        if not findings:
            findings.append({
                "rule": "OK",
                "severity": "ok",
                "title": "특이사항 없음",
                "desc": "현재 수집 데이터 기준 주요 이상 감지되지 않음",
                "action": "정상 모니터링 유지",
                "metric": None,
            })

        severity_order = {"error": 3, "warning": 2, "info": 1, "ok": 0}
        max_sev = max(severity_order.get(f["severity"], 0) for f in findings)

        all_diagnostics.append({
            "course_name": course,
            "findings": findings,
            "severity_max": max_sev,
            "finding_count": len([f for f in findings if f["rule"] != "OK"]),
        })

    # 심각도 순 정렬
    all_diagnostics.sort(key=lambda x: -x["severity_max"])

    return {
        "diagnostics": all_diagnostics,
        "data_days": 2 if prev else 1,
        "rules_applicable": ["A", "B", "E", "H"],
        "rules_pending": ["C", "D", "F", "G", "I", "J"],
        "data_note": "현재 2일 데이터 기준. C/D/F/G/I/J 룰은 30일+ 축적 후 활성화",
    }

# ─────────────────────────────────────────────
# V5: get_tab8_by_date() — returns slots for one collected_date only
# ─────────────────────────────────────────────
def get_tab8_by_date(db, date):
    """V5: Get tab8 slots for a single collected_date."""
    rows = q(db, """
        SELECT course_name, course_sub, membership_type,
               play_date, tee_time, price_krw,
               promo_flag, promo_text, pax_condition,
               price_type, part_type, weekday_type,
               d_day, season
        FROM tee_time_snapshots
        WHERE collected_date = ?
        ORDER BY course_name, play_date, tee_time
    """, (date,))

    for r in rows:
        if r["membership_type"] is None:
            r["membership_type"] = "단일"
        r["sub_display"] = get_sub_label(r["course_sub"], r["membership_type"])

    return rows

# ─────────────────────────────────────────────
# TAB 8 — 티타임 상세
# ─────────────────────────────────────────────
def get_tab8(db, latest):
    rows = q(db, """
        SELECT course_name, course_sub, membership_type,
               play_date, tee_time, price_krw,
               promo_flag, promo_text, pax_condition,
               price_type, part_type, weekday_type,
               d_day, season
        FROM tee_time_snapshots
        WHERE collected_date = ?
        ORDER BY course_name, play_date, tee_time
    """, (latest,))

    for r in rows:
        if r["membership_type"] is None:
            r["membership_type"] = "단일"
        r["sub_display"] = get_sub_label(r["course_sub"], r["membership_type"])

    return {"slots": rows}

# ─────────────────────────────────────────────
# V5: build_v5_data() — full date-keyed structure
# ─────────────────────────────────────────────
def build_v5_data(db):
    """Build complete V5 structure with all dates keyed."""
    meta = get_metadata(db)
    dates = meta["all_dates"]
    latest = meta["latest_date"]
    prev = meta["prev_date"]

    v5_data = {
        "metadata": meta,
        "tab1": get_tab1_all(db, dates),
        "tab3": get_tab3_all(db, dates),
        "tab4": get_tab4(db, latest),  # single call (all events with dates)
        "tab5a": get_tab5a(db, latest, prev),  # all events with dates
        "tab5b": get_tab5b_all(db, dates),
        "tab6": get_tab6_all(db, dates),
        "tab7": get_tab7_all(db, dates),
        # tab8: excluded (separate JSON files per date)
    }
    return v5_data

# ─────────────────────────────────────────────
# 메인 (V5 구조)
# ─────────────────────────────────────────────
def main():
    db = conn()
    meta = get_metadata(db)
    latest = meta["latest_date"]
    prev   = meta["prev_date"]
    dates = meta["all_dates"]

    print(f"[generate_dashboard_data V5] {meta['generated_at']}")
    print(f"  수집 일자: {dates} ({len(dates)}개)")
    print(f"  최신: {latest} | 전일: {prev}")
    print(f"  골프장: {len(meta['courses'])}개")

    # Build V5 structure
    v5_data = build_v5_data(db)

    # Also build v4 compatible structure (latest+prev only) for backward compat
    data = {
        "metadata": meta,
        "tab1": get_tab1(db, latest, prev),
        "tab2": get_tab2(db, latest, prev),
        "tab3": get_tab3(db, latest, prev),
        "tab4": get_tab4(db, latest),
        "tab5a": get_tab5a(db, latest, prev),
        "tab5b": get_tab5b(db, latest),
        "tab6": get_tab6(db, latest, prev),
        "tab7": get_tab7(db, latest, prev),
        "tab8": get_tab8(db, latest),
    }

    # Write V5 data
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(v5_data, f, ensure_ascii=False, indent=2, default=str)

    # Write V4 compat data to alternate file (optional)
    v4_path = OUT_PATH.replace(".json", "_v4.json")
    with open(v4_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # Log statistics
    latest_tab8 = get_tab8(db, latest)
    total_slots = len(latest_tab8["slots"])
    price_changes = sum(v5_data["tab1"][latest]["kpi"]["changes_by_type"].values())
    print(f"  최신 날짜 슬롯: {total_slots}건 | 가격변경: {price_changes}건")
    print(f"  → {OUT_PATH} 저장 완료 (V5 date-keyed)")
    print(f"  → {v4_path} 저장 완료 (V4 backward compat)")

    db.close()

if __name__ == "__main__":
    main()

# ─────────────────────────────────────────────
# JSX 임베드용 경량 데이터 생성
# ─────────────────────────────────────────────
def make_embed_data(data):
    """JSX 인라인 임베드를 위한 경량 데이터 (tab8 제외 — 별도 파일)
    V5 호환: data는 build_v5_data()에서 생성된 date-keyed 구조
    """
    import random

    # V5: data has date-keyed structure
    if "tab1" in data and isinstance(data["tab1"], dict):
        # Check if it's V5 (keyed by date) or V4 (single object)
        first_key = next(iter(data["tab1"].keys())) if data["tab1"] else None
        is_v5 = first_key and "-" in str(first_key)  # date format check

        if is_v5:
            # V5 date-keyed structure
            latest_date = data["metadata"]["latest_date"]
            embed = {
                "metadata": data["metadata"],
                "tab1": data["tab1"],  # keyed by date
                "tab3": data["tab3"],  # keyed by date
                "tab4": {
                    "dday_trend": data["tab4"]["dday_trend"],
                    "histogram": data["tab4"]["histogram"],
                    "price_events": data["tab4"]["price_events"],
                    "scatter": _sample_scatter(data["tab4"]["scatter"], 600),
                    "ghost_events": data["tab4"].get("ghost_events", []),
                },
                "tab5a": data["tab5a"],  # all events with dates
                "tab5b": data["tab5b"],  # keyed by date
                "tab6": data["tab6"],  # keyed by date
                "tab7": data["tab7"],  # keyed by date
                # tab8: excluded (separate JSON files per date)
            }
            return embed

    # Fallback for V4 single-date structure
    embed = {
        "metadata": data["metadata"],
        "tab1": data["tab1"],
        "tab3": data["tab3"] if "tab3" in data else {},
        "tab4": {
            "dday_trend": data["tab4"]["dday_trend"],
            "histogram": data["tab4"]["histogram"],
            "price_events": data["tab4"]["price_events"],
            "scatter": _sample_scatter(data["tab4"]["scatter"], 600),
            "ghost_events": data["tab4"].get("ghost_events", []),
        },
        "tab5a": data["tab5a"] if "tab5a" in data else {},
        "tab5b": {
            "yield_slots": data["tab5b"]["yield_slots"][:500],
            "course_summary": data["tab5b"]["course_summary"],
            "yield_histogram": data["tab5b"]["yield_histogram"],
        } if "tab5b" in data else {},
        "tab6": data["tab6"] if "tab6" in data else {},
        "tab7": data["tab7"] if "tab7" in data else {},
    }
    return embed

def _sample_scatter(scatter, target_n):
    """변동 슬롯 100% 보존 + 나머지 균등 샘플링"""
    from collections import defaultdict
    import random
    # 1) 변동 슬롯 무조건 포함
    changed = [r for r in scatter if r.get("price_changed_flag")]
    normal = [r for r in scatter if not r.get("price_changed_flag")]
    remaining = max(0, target_n - len(changed))
    # 2) 일반 슬롯: 골프장별 균등 샘플링
    by_course = defaultdict(list)
    for r in normal:
        by_course[r["course_name"]].append(r)
    n_courses = len(by_course) or 1
    per_course = max(1, remaining // n_courses)
    result = list(changed)
    for course, rows in by_course.items():
        sampled = random.sample(rows, min(per_course, len(rows)))
        result.extend(sampled)
    return result
