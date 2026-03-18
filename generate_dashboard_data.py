"""
카카오골프 대시보드 데이터 생성기
golf.db → dashboard_data.json
매일 스크래퍼 완료 후 실행
"""
import sqlite3
import json
import os
import statistics
from datetime import datetime, date
from collections import defaultdict
from config.courses import COURSE_HOLES, COURSE_PROFILES, get_hole_units, MONTHLY_MAX_TEAMS_PER_9H, GROUP_RATIO, GROUP_DISCOUNT, get_daily_max_teams

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
    # 신규 컬럼 마이그레이션 (weather_cause)
    try:
        c.execute("ALTER TABLE unsold_slots ADD COLUMN weather_cause TEXT")
        c.commit()
    except Exception:
        pass  # 이미 존재
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
        "SELECT DISTINCT collected_date FROM latest_daily_snapshots ORDER BY collected_date")]
    latest = dates[-1] if dates else None
    prev   = dates[-2] if len(dates) >= 2 else None

    courses = [r["course_name"] for r in q(db,
        "SELECT DISTINCT course_name FROM latest_daily_snapshots ORDER BY course_name")]

    # 최종 수집 시간: crawl_runs에서 가장 최근 완료 시간
    last_crawl = q(db, """
        SELECT id, started_at, finished_at, status, total_rows
        FROM crawl_runs
        WHERE finished_at IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
    """)
    last_crawl_info = None
    if last_crawl:
        lc = last_crawl[0]
        today_update_count = scalar(db, """
            SELECT COUNT(*)
            FROM crawl_runs
            WHERE status = 'success'
              AND finished_at IS NOT NULL
              AND substr(finished_at, 1, 10) = substr(?, 1, 10)
              AND id <= ?
        """, (lc["finished_at"], lc["id"])) if lc["finished_at"] else None
        last_crawl_info = {
            "started_at": lc["started_at"],
            "finished_at": lc["finished_at"],
            "status": lc["status"],
            "total_rows": lc["total_rows"],
            "today_update_count": today_update_count,
        }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "latest_date": latest,
        "prev_date": prev,
        "all_dates": dates,
        "courses": courses,
        "member_courses": list(MEMBER_COURSES.keys()),
        "last_crawl": last_crawl_info,
    }

# ─────────────────────────────────────────────
# 현장결제 예상 매출 (시간대별 가격 추정)
# ─────────────────────────────────────────────
def _estimate_revenue_by_time(db, course_name, latest, cart_fee, daily_max, unsold_count):
    """시간대별 현장결제 예상 매출.
    우선순위: ① 동시간대 남은티 확정 → ② 같은요일 다른날짜 평균 → ③ 근접시간 보간
    """
    # 1. 가장 가까운 play_date (D-day ≤ 1) 찾기
    nearest = scalar(db, """
        SELECT play_date FROM latest_daily_snapshots
        WHERE collected_date = ? AND course_name = ? AND d_day <= 1
        ORDER BY d_day LIMIT 1
    """, (latest, course_name))
    if not nearest:
        nearest = scalar(db, """
            SELECT play_date FROM latest_daily_snapshots
            WHERE collected_date = ? AND course_name = ?
            ORDER BY d_day LIMIT 1
        """, (latest, course_name))
    if not nearest:
        return _empty_revenue(daily_max, cart_fee, unsold_count)

    # 2. 해당 play_date 잔여 슬롯
    remaining = q(db, """
        SELECT tee_time, course_sub, price_krw, part_type, weekday_type, promo_flag
        FROM latest_daily_snapshots
        WHERE collected_date = ? AND course_name = ? AND play_date = ?
        ORDER BY tee_time
    """, (latest, course_name, nearest))
    if not remaining:
        return _empty_revenue(daily_max, cart_fee, unsold_count)

    weekday_type = remaining[0]["weekday_type"]
    remaining_count = len(remaining)

    # 3. 동시간대 남은티 가격 맵 (① 확정)
    time_confirmed = {}
    for r in remaining:
        t = r["tee_time"]
        if t not in time_confirmed:
            time_confirmed[t] = []
        time_confirmed[t].append(r["price_krw"])
    for t in time_confirmed:
        time_confirmed[t] = round(sum(time_confirmed[t]) / len(time_confirmed[t]))

    # 4. 같은요일 다른 play_date 가격 맵 (② 추정)
    weekday_prices = {}
    for r in q(db, """
        SELECT tee_time, price_krw FROM latest_daily_snapshots
        WHERE collected_date = ? AND course_name = ? AND weekday_type = ?
        ORDER BY tee_time
    """, (latest, course_name, weekday_type)):
        t = r["tee_time"]
        if t not in weekday_prices:
            weekday_prices[t] = []
        weekday_prices[t].append(r["price_krw"])

    # 모든 관측 시간대 (가격 커버리지)
    all_known = {}
    for t, prices in weekday_prices.items():
        all_known[t] = round(sum(prices) / len(prices))
    all_known.update(time_confirmed)  # 확정이 우선

    def _estimate_price(target_time):
        """① 동시간대 남은티 → ② 같은요일 평균 → ③ 근접시간"""
        if target_time in time_confirmed:
            return time_confirmed[target_time], "confirmed"
        if target_time in weekday_prices:
            p = weekday_prices[target_time]
            return round(sum(p) / len(p)), "weekday_avg"
        # 근접시간 보간
        t_min = int(target_time[:2]) * 60 + int(target_time[3:])
        best_p, best_diff = None, 9999
        for ct, cp in all_known.items():
            ct_min = int(ct[:2]) * 60 + int(ct[3:])
            diff = abs(ct_min - t_min)
            if diff < best_diff:
                best_diff = diff
                best_p = cp
        return best_p or 0, "interpolated"

    # 5. 시간대별 최대팀수 비율 (최초 스냅샷 기준)
    first_cd = scalar(db, """
        SELECT MIN(collected_date) FROM latest_daily_snapshots
        WHERE course_name = ? AND play_date = ?
    """, (course_name, nearest))
    part_slots_first = {}
    if first_cd:
        for r in q(db, """
            SELECT part_type, COUNT(*) as cnt FROM latest_daily_snapshots
            WHERE collected_date = ? AND course_name = ? AND play_date = ?
            GROUP BY part_type
        """, (first_cd, course_name, nearest)):
            part_slots_first[r["part_type"]] = r["cnt"]
    total_first = sum(part_slots_first.values()) if part_slots_first else 1
    part_ratio = {pt: cnt / total_first for pt, cnt in part_slots_first.items()} if part_slots_first else {"1부": 0.55, "2부": 0.30, "오후": 0.15}

    # 잔여 시간대별
    remain_by_part = {}
    for r in remaining:
        pt = r["part_type"]
        remain_by_part[pt] = remain_by_part.get(pt, 0) + 1

    # 6. 시간대별 가격 추정 + 매출 계산
    all_observed_times = sorted(set(weekday_prices.keys()))

    by_part = {}
    for pt in ["1부", "2부", "오후"]:
        ratio = part_ratio.get(pt, 0)
        max_pt = round(daily_max * ratio)
        rem_pt = remain_by_part.get(pt, 0)
        booked_pt = max(0, max_pt - rem_pt)

        # 이 시간대의 가격 수집
        pt_prices = []
        confirmed_cnt = 0
        estimated_cnt = 0
        for t in all_observed_times:
            h = int(t[:2])
            t_part = "1부" if h < 11 else ("2부" if h < 14 else "오후")
            if t_part != pt:
                continue
            price, source = _estimate_price(t)
            if price:
                pt_prices.append(price)
                if source == "confirmed":
                    confirmed_cnt += 1
                else:
                    estimated_cnt += 1

        avg_green = round(sum(pt_prices) / len(pt_prices)) if pt_prices else 0
        revenue = booked_pt * (avg_green * 4 + cart_fee) if booked_pt > 0 else 0

        # 할인/정상 분리
        pt_remaining = [r for r in remaining if r["part_type"] == pt]
        promo_count = sum(1 for r in pt_remaining if r["promo_flag"])

        by_part[pt] = {
            "max_teams": max_pt,
            "remaining": rem_pt,
            "booked": booked_pt,
            "avg_green_fee": avg_green,
            "revenue": revenue,
            "confirmed_prices": confirmed_cnt,
            "estimated_prices": estimated_cnt,
            "promo_remaining": promo_count,
            "regular_remaining": len(pt_remaining) - promo_count,
        }

    total_revenue = sum(d["revenue"] for d in by_part.values())
    total_booked = sum(d["booked"] for d in by_part.values())

    # 미판매 손실
    unsold_prices = [r["price_krw"] for r in remaining]
    avg_unsold = round(sum(unsold_prices) / len(unsold_prices)) if unsold_prices else 0
    unsold_loss_val = unsold_count * (avg_unsold * 4 + cart_fee) if unsold_count else 0

    # 전체 평균 (하위호환)
    all_prices = [r["price_krw"] for r in remaining]
    avg_price = round(sum(all_prices) / len(all_prices)) if all_prices else 0

    return {
        "method": "현장결제_예상액",
        "play_date": nearest,
        "weekday_type": weekday_type,
        "total_revenue": total_revenue,
        "by_part": by_part,
        "daily_max": daily_max,
        "remaining_slots": remaining_count,
        "reserved_teams": total_booked,
        "booked_teams": total_booked,
        "cart_fee_team": cart_fee,
        "avg_price": avg_price,
        "unsold_loss": unsold_loss_val,
        "unsold_teams": unsold_count,
    }


def _empty_revenue(daily_max, cart_fee, unsold_count):
    """데이터 없을 때 빈 revenue 객체."""
    return {
        "method": "현장결제_예상액",
        "play_date": None,
        "weekday_type": None,
        "total_revenue": 0,
        "by_part": {},
        "daily_max": daily_max,
        "remaining_slots": 0,
        "reserved_teams": 0,
        "booked_teams": 0,
        "cart_fee_team": cart_fee,
        "avg_price": 0,
        "unsold_loss": 0,
        "unsold_teams": unsold_count,
    }


# ─────────────────────────────────────────────
# 판매력 판정 + 정규화 + D-day 분포
# ─────────────────────────────────────────────
def _judge_sales_power(consume_rate, slots_per_unit):
    """판매력 4단계 판정.
    consume_rate: 소진율(%), slots_per_unit: 잔여/9홀
    """
    if consume_rate is None:
        return None
    high_rate = consume_rate >= 7.0     # 소진율 기준선
    low_stock = slots_per_unit < 200    # 잔여 밀도 기준선
    if high_rate and low_stock:
        return {"grade": "완판임박", "icon": "🔥", "level": 4}
    elif high_rate and not low_stock:
        return {"grade": "판매호조", "icon": "📈", "level": 3}
    elif not high_rate and not low_stock:
        return {"grade": "판매관망", "icon": "🟡", "level": 2}
    else:
        return {"grade": "수요부진", "icon": "⚠️", "level": 1}


def _get_dday_distribution(db, collected_date, course_name, membership_filter=None):
    """D-day 구간별 잔여 슬롯 분포 조회."""
    base_sql = """
        SELECT
            CASE WHEN d_day <= 7 THEN 'D1-7'
                 WHEN d_day <= 14 THEN 'D8-14'
                 ELSE 'D15+' END as bucket,
            COUNT(*) as cnt,
            ROUND(AVG(price_krw)) as avg_price,
            SUM(promo_flag) as promo_count
        FROM latest_daily_snapshots
        WHERE collected_date = ? AND course_name = ?
    """
    params = [collected_date, course_name]
    if membership_filter:
        base_sql += " AND membership_type = ?"
        params.append(membership_filter)
    base_sql += " GROUP BY bucket ORDER BY bucket"
    rows = q(db, base_sql, tuple(params))
    # 빈 구간 채우기
    result = {}
    for b in ["D1-7", "D8-14", "D15+"]:
        result[b] = {"slots": 0, "avg_price": None, "promo_count": 0}
    for r in rows:
        result[r["bucket"]] = {
            "slots": r["cnt"],
            "avg_price": int(r["avg_price"]) if r["avg_price"] else None,
            "promo_count": int(r["promo_count"] or 0),
        }
    return result


def _get_price_range_by_part(db, collected_date, course_name, membership_filter=None):
    """파트·요일별 가격대 (min~max + 특가비율)."""
    base_sql = """
        SELECT weekday_type, part_type,
               MIN(price_krw) as min_price, MAX(price_krw) as max_price,
               COUNT(*) as cnt,
               SUM(promo_flag) as promo_count
        FROM latest_daily_snapshots
        WHERE collected_date = ? AND course_name = ?
          AND price_krw IS NOT NULL
    """
    params = [collected_date, course_name]
    if membership_filter:
        base_sql += " AND membership_type = ?"
        params.append(membership_filter)
    base_sql += " GROUP BY weekday_type, part_type ORDER BY weekday_type, part_type"
    rows = q(db, base_sql, tuple(params))
    result = []
    for r in rows:
        result.append({
            "weekday_type": r["weekday_type"],
            "part_type": r["part_type"],
            "min_price": r["min_price"],
            "max_price": r["max_price"],
            "slots": r["cnt"],
            "promo_ratio": round(r["promo_count"] / r["cnt"] * 100, 1) if r["cnt"] else 0,
        })
    return result


def _get_weather_causes(db, latest):
    """기상 예보 변화에 따른 원인 태깅.
    Returns: dict {play_date: "우천예보" | "맑음전환" | None}
    """
    causes = {}
    try:
        # 최근 5일간 forecast_changed 이력 조회
        rows = q(db, """
            SELECT play_date, forecast_changed, rain_prob
            FROM weather_forecasts
            WHERE forecast_date <= ? AND forecast_date >= date(?, '-5 days')
              AND play_date > ?
            ORDER BY play_date, forecast_date DESC
        """, (latest, latest, latest))
        seen = set()
        for r in rows:
            pd = r["play_date"]
            if pd in seen:
                continue
            seen.add(pd)
            if r["forecast_changed"] == "악화" or (r["rain_prob"] and r["rain_prob"] >= 60):
                causes[pd] = "우천예보"
            elif r["forecast_changed"] == "호전":
                causes[pd] = "맑음전환"
            else:
                causes[pd] = None
    except Exception:
        pass
    return causes


def _enrich_consumption(db, consumption, latest, prev):
    """consumption 배열에 정규화·판매력·D-day 분포·대중/회원 분리 추가."""
    enriched = []
    for c in consumption:
        cn = c["course_name"]
        units = get_hole_units(cn)
        today = c.get("today_slots") or 0
        slots_per_unit = round(today / units) if units else today
        consume_rate = c.get("consume_rate")

        c["hole_units"] = units
        c["slots_per_unit"] = slots_per_unit
        c["sales_power"] = _judge_sales_power(consume_rate, slots_per_unit)
        c["dday_dist"] = _get_dday_distribution(db, latest, cn)
        c["price_range"] = _get_price_range_by_part(db, latest, cn)

        # 골프장 프로필 정보
        profile = COURSE_PROFILES.get(cn, {})
        c["profile"] = {
            "type": profile.get("type"),
            "holes": profile.get("holes"),
            "member_count": profile.get("member_count"),
            "note": profile.get("note", ""),
        }

        # 수요 밀도 & 소진 속도
        c["demand_density"] = _calc_demand_density(db, latest, cn)
        c["consumption_velocity"] = _calc_consumption_velocity(db, latest, cn)

        # 구장별 기상
        course_weather = q(db, """
            SELECT temperature, rainfall, humidity, wind_speed, precip_type, sky_condition
            FROM weather_observations WHERE collected_date=? AND course_name=? LIMIT 1
        """, (latest, cn))
        course_forecast = q(db, """
            SELECT play_date, rain_prob, temperature_high, precip_type, sky_condition, forecast_changed
            FROM weather_forecasts WHERE forecast_date=? AND course_name=?
            AND play_date > ? ORDER BY play_date LIMIT 3
        """, (latest, cn, latest))

        sky_icons = {1: "\u2600\ufe0f", 3: "\u26c5", 4: "\u2601\ufe0f"}
        precip_icons = {0: "", 1: "\U0001F327\ufe0f", 2: "\U0001F328\ufe0f", 3: "\u2744\ufe0f"}

        obs = dict(course_weather[0]) if course_weather else None
        fc_list = []
        for f in course_forecast:
            icon = precip_icons.get(f["precip_type"], "") if f["precip_type"] and f["precip_type"] > 0 else sky_icons.get(f["sky_condition"], "")
            fc_list.append({
                "play_date": f["play_date"],
                "rain_prob": f["rain_prob"],
                "temp_high": f["temperature_high"],
                "icon": icon,
                "changed": f["forecast_changed"],
            })
        c["weather"] = {"observation": obs, "forecasts": fc_list}

        # ── 현장결제 예상 매출 (시간대별 가격 추정) ──
        cart_fee = profile.get("cart_fee_team", 100000)

        from datetime import datetime
        try:
            current_month = datetime.strptime(latest, "%Y-%m-%d").month
        except Exception:
            current_month = 3

        daily_max = get_daily_max_teams(cn, current_month)
        unsold_count = c.get("unsold") or 0

        c["revenue"] = _estimate_revenue_by_time(db, cn, latest, cart_fee, daily_max, unsold_count)

        # 특가 분류
        promo_stats = q(db, """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN promo_flag=1 THEN 1 ELSE 0 END) as promo
            FROM latest_daily_snapshots
            WHERE collected_date=? AND course_name=?
            AND course_sub NOT LIKE '멤버십%'
        """, (latest, cn))
        if promo_stats and promo_stats[0]["total"] > 0:
            promo_pct = round(promo_stats[0]["promo"] / promo_stats[0]["total"] * 100, 1)
            if promo_pct >= 80:
                promo_grade = "마케팅"  # 상시 할인 구조 → 특가 표기 무시
            elif promo_pct >= 20:
                promo_grade = "실질"    # 진짜 할인
            elif promo_pct > 0:
                promo_grade = "소폭"    # 가끔 할인
            else:
                promo_grade = "정가"    # 할인 없음
            c["promo_analysis"] = {
                "promo_pct": promo_pct,
                "grade": promo_grade,
            }
        else:
            c["promo_analysis"] = {"promo_pct": 0, "grade": "정가"}

        # 대중/회원 분리 (골드레이크, 해피니스)
        if cn in MEMBER_COURSES:
            tiers = {}
            for mt in ["대중제", "회원제"]:
                mt_units = get_hole_units(cn, mt)
                sub_list = MEMBER_COURSES[cn][mt]
                sub_ph = ",".join("?" * len(sub_list))
                mt_today = scalar(db,
                    "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND membership_type=?",
                    (latest, cn, mt)) or 0
                mt_prev = 0
                mt_consumed = None
                mt_consume_rate = None
                mt_cancel = None
                if prev:
                    mt_prev = scalar(db,
                        "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND membership_type=?",
                        (prev, cn, mt)) or 0
                    prev_mk = set(r["slot_group_key"] for r in q(db,
                        f"SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND course_sub IN ({sub_ph})",
                        (prev, cn) + tuple(sub_list)))
                    today_mk = set(r["slot_group_key"] for r in q(db,
                        f"SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND course_sub IN ({sub_ph})",
                        (latest, cn) + tuple(sub_list)))
                    mt_consumed = len(prev_mk - today_mk)
                    mt_cancel = len(today_mk - prev_mk)
                    mt_consume_rate = round(mt_consumed / len(prev_mk) * 100, 1) if prev_mk else None

                mt_slots_per_unit = round(mt_today / mt_units) if mt_units else mt_today
                # 서브코스별 슬롯 수
                sub_slots = q(db,
                    f"SELECT course_sub, COUNT(*) as cnt FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND course_sub IN ({sub_ph}) GROUP BY course_sub",
                    (latest, cn) + tuple(sub_list))
                tiers[mt] = {
                    "slots": mt_today,
                    "prev_slots": mt_prev,
                    "slot_delta": mt_today - mt_prev if prev else None,
                    "hole_units": mt_units,
                    "slots_per_unit": mt_slots_per_unit,
                    "consumed": mt_consumed,
                    "cancel_reopen": mt_cancel,
                    "consume_rate": mt_consume_rate,
                    "sales_power": _judge_sales_power(mt_consume_rate, mt_slots_per_unit),
                    "dday_dist": _get_dday_distribution(db, latest, cn, mt),
                    "price_range": _get_price_range_by_part(db, latest, cn, mt),
                    "sub_courses": sub_list,
                    "sub_slot_counts": {r["course_sub"]: r["cnt"] for r in sub_slots},
                }

            c["membership_tiers"] = tiers

        enriched.append(c)

    # weather_note 추가 (consumption 전체에 기상 원인 태깅)
    weather_causes = _get_weather_causes(db, latest)
    if weather_causes:
        for c in enriched:
            # play_date별 weather_note 매핑 — consumption은 코스 단위이므로 해당 코스의 play_date 범위 확인
            weather_notes = []
            play_dates_for_course = q(db, """
                SELECT DISTINCT play_date FROM latest_daily_snapshots
                WHERE collected_date=? AND course_name=? AND d_day <= 7
            """, (latest, c["course_name"]))
            for pd_row in play_dates_for_course:
                pd = pd_row["play_date"]
                cause = weather_causes.get(pd)
                if cause:
                    weather_notes.append({"play_date": pd, "cause": cause})
            c["weather_note"] = weather_notes[0]["cause"] if weather_notes else None
            c["weather_notes"] = weather_notes

    return enriched


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
        FROM latest_daily_snapshots
        WHERE collected_date = ?
        GROUP BY course_name ORDER BY course_name
    """, (latest,))

    prev_slots = {}
    if prev:
        for r in q(db, """
            SELECT course_name, COUNT(*) as slots, ROUND(AVG(price_krw)) as avg_price
            FROM latest_daily_snapshots WHERE collected_date = ?
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
            FROM latest_daily_snapshots WHERE collected_date=?
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

    # ── 슬롯 변동 현황 (재설계) ──
    # 신규오픈: play_date가 오늘 처음 수집 범위에 들어온 슬롯 (최초 관측)
    # 추가오픈: 이미 수집 중인 play_date에서 처음 보이는 새 슬롯
    # 티취소(재오픈): 이전에 존재→사라짐→다시 나타난 슬롯
    # 소진: 어제 있었는데 오늘 없는 슬롯
    # 증감: 오늘 전체 - 어제 전체

    # 신규오픈 판정: 이전 수집에 없던 play_date가 오늘 처음 나타남
    if prev:
        prev_play_dates = set(r["play_date"] for r in q(db,
            "SELECT DISTINCT play_date FROM latest_daily_snapshots WHERE collected_date=?", (prev,)))
        today_play_dates = set(r["play_date"] for r in q(db,
            "SELECT DISTINCT play_date FROM latest_daily_snapshots WHERE collected_date=?", (latest,)))
        new_open_play_dates = today_play_dates - prev_play_dates
    else:
        new_open_play_dates = set()

    consumption = []
    if prev and prev_density_mode:
        for course in [r["course_name"] for r in today_slots]:
            # 겹치는 play_date 범위에서만 비교 (공정한 비교)
            shared_dates = q(db, """
                SELECT DISTINCT a.play_date FROM latest_daily_snapshots a
                WHERE a.collected_date=? AND a.course_name=?
                AND EXISTS (SELECT 1 FROM latest_daily_snapshots b
                    WHERE b.collected_date=? AND b.course_name=? AND b.play_date=a.play_date)
            """, (prev, course, latest, course))
            shared_date_set = set(r["play_date"] for r in shared_dates)

            if prev_density_mode == "sparse":
                prev_ts = set((r["play_date"], r["tee_time"]) for r in q(db,
                    "SELECT DISTINCT play_date, tee_time FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?",
                    (prev, course)) if r["play_date"] in shared_date_set)
                today_ts = set((r["play_date"], r["tee_time"]) for r in q(db,
                    "SELECT DISTINCT play_date, tee_time FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?",
                    (latest, course)) if r["play_date"] in shared_date_set)

                consumed = len(prev_ts - today_ts)
                appeared = today_ts - prev_ts
                stayed   = len(prev_ts & today_ts)
                prev_count = len(prev_ts)
                today_count = len(today_ts)
            else:
                if shared_date_set:
                    sd_list = tuple(shared_date_set)
                    sd_ph = ",".join("?" * len(sd_list))
                    today_rows = q(db,
                        f"SELECT slot_group_key, play_date FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND play_date IN ({sd_ph})",
                        (latest, course) + sd_list)
                    prev_rows = q(db,
                        f"SELECT slot_group_key, play_date FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND play_date IN ({sd_ph})",
                        (prev, course) + sd_list)
                    today_keys = set(r["slot_group_key"] for r in today_rows)
                    prev_keys = set(r["slot_group_key"] for r in prev_rows)
                    today_key_pd = {r["slot_group_key"]: r["play_date"] for r in today_rows}
                else:
                    today_keys = set()
                    prev_keys = set()
                    today_key_pd = {}

                consumed = len(prev_keys - today_keys)
                appeared = today_keys - prev_keys  # 어제 없었는데 오늘 있는 슬롯들
                stayed   = len(prev_keys & today_keys)
                prev_count = len(prev_keys)
                today_count = len(today_keys)

            # 신규오픈: 이전 수집에 없던 play_date 중 이전 max보다 먼 것만
            course_prev_max = scalar(db,
                "SELECT MAX(play_date) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?",
                (prev, course)) or ""
            all_new_slots = scalar(db, """
                SELECT COUNT(*) FROM latest_daily_snapshots
                WHERE collected_date=? AND course_name=? AND play_date NOT IN (
                    SELECT DISTINCT play_date FROM latest_daily_snapshots
                    WHERE collected_date=? AND course_name=?
                )
            """, (latest, course, prev, course)) or 0
            # 이전 max보다 먼 것만 진짜 신규오픈, 나머지는 티취소로
            new_open_slots = scalar(db, """
                SELECT COUNT(*) FROM latest_daily_snapshots
                WHERE collected_date=? AND course_name=? AND play_date > ?
                AND play_date NOT IN (
                    SELECT DISTINCT play_date FROM latest_daily_snapshots
                    WHERE collected_date=? AND course_name=?
                )
            """, (latest, course, course_prev_max, prev, course)) or 0
            # 기존 범위 안에서 새로 나타난 play_date = 티취소로 재분류
            reclassified = all_new_slots - new_open_slots

            # 티취소 = shared 내 나타난 슬롯 + 재분류분
            cancel_reopen = (len(appeared) if not isinstance(appeared, int) else appeared) + reclassified

            # 회원제 분리
            member_new = 0
            if course in MEMBER_COURSES and prev_density_mode == "normal":
                member_sub = MEMBER_COURSES[course]["회원제"]
                ms_ph = ",".join("?" * len(member_sub))
                member_new = scalar(db,
                    f"SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND course_sub IN ({ms_ph}) AND play_date IN (SELECT play_date FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND play_date NOT IN (SELECT DISTINCT play_date FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?))",
                    (latest, course) + tuple(member_sub) + (latest, course, prev, course)) or 0

            # 전체 오늘 슬롯 수 (shared + new play_dates)
            total_today_course = scalar(db,
                "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?",
                (latest, course)) or 0
            total_prev_course = scalar(db,
                "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?",
                (prev, course)) or 0

            # 미판매 슬롯 (어제 있었지만 play_date가 오늘의 shared에 없음 → 팔리지 않고 경기일 지남)
            unsold = total_prev_course - prev_count

            consumption.append({
                "course_name": course,
                "prev_slots": total_prev_course,
                "today_slots": total_today_course,
                "slot_delta": total_today_course - total_prev_course,
                # 세분화된 개수
                "new_open": new_open_slots - member_new,   # 신규오픈 (새 play_date의 슬롯)
                "member_open": member_new,                  # 회원제 신규오픈
                "cancel_reopen": cancel_reopen,             # 티취소 (재오픈)
                "consumed": consumed,                       # 소진 (예약됨)
                "unsold": unsold,                           # 미판매 (팔리지 않고 경기일 지남)
                "stayed": stayed,                           # 유지
                "consume_rate": round(consumed / prev_count * 100, 1) if prev_count else None,
                "data_quality": "ok",
                "compare_mode": "timeslot" if prev_density_mode == "sparse" else "slot_key",
            })
    else:
        for r in today_slots:
            # 첫 수집일: 모든 슬롯이 신규오픈
            total_course = r["slots"]
            consumption.append({
                "course_name": r["course_name"],
                "prev_slots": None, "today_slots": total_course,
                "slot_delta": None,
                "new_open": total_course, "member_open": None,
                "cancel_reopen": 0,
                "consumed": None, "unsold": 0, "stayed": None, "consume_rate": None,
                "data_quality": "first_collection",
            })
    # consumption 배열에 품질 경고 메타데이터 추가
    if consumption:
        if consumption_data_note:
            consumption[0]["data_note"] = consumption_data_note

    # ── 정규화 + 판매력 + D-day 분포 + 대중/회원 분리 ──
    consumption = _enrich_consumption(db, consumption, latest, prev)

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
        FROM latest_daily_snapshots
        WHERE collected_date = ? AND d_day <= 7
        GROUP BY play_date, weekday_type
        ORDER BY play_date
    """, (latest,))

    total_today = sum(r["slots"] for r in today_slots)
    total_prev  = sum(r["slots"] for r in prev_slots.values())
    total_changes = len(price_changes)
    total_promo = sum(r["promo_slots"] for r in today_slots)

    # 소진 요약 집계 (consumption 기반)
    cons_total_consumed = sum(c.get("consumed") or 0 for c in consumption)
    cons_total_new_open = sum(c.get("new_open") or 0 for c in consumption)
    cons_total_cancel_reopen = sum(c.get("cancel_reopen") or 0 for c in consumption)
    cons_total_member_open = sum(c.get("member_open") or 0 for c in consumption)
    cons_total_unsold = sum(c.get("unsold") or 0 for c in consumption)
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
            "cancel_reopen_count": cons_total_cancel_reopen,
            "member_open_count": cons_total_member_open,
            "unsold_count": cons_total_unsold,
            "compare_prev_slots": cons_total_prev,
            "compare_today_slots": cons_total_today,
            "compare_mode": cons_compare_mode,
        },
        "course_kpi": today_slots,
        "prev_course_kpi": prev_slots,
        "price_changes": dict(changes_by_type),
        "consumption": consumption,
        "unsold_summary": _get_unsold_summary(db, latest),
        "weather": _get_weather_summary(db, latest),
        "alerts": sorted(alerts, key=lambda x: {"error": 0, "warning": 1, "info": 2}[x["level"]]),
        "calendar": calendar,
    }

def _get_weather_summary(db, latest):
    """기상 요약: 실황 + 향후 7일 예보."""
    # 실황 (대표 지점: 어등산 = 광주)
    obs = q(db, """
        SELECT course_name, temperature, rainfall, humidity, wind_speed, precip_type, sky_condition
        FROM weather_observations WHERE collected_date = ? LIMIT 1
    """, (latest,))

    # 향후 7일 예보 (코스 평균)
    forecasts = q(db, """
        SELECT play_date,
               ROUND(AVG(rain_prob)) as avg_rain_prob,
               ROUND(AVG(temperature_high), 1) as avg_temp_high,
               MAX(precip_type) as max_precip,
               MAX(sky_condition) as max_sky,
               GROUP_CONCAT(DISTINCT forecast_changed) as changes
        FROM weather_forecasts
        WHERE forecast_date = ? AND play_date > ?
        GROUP BY play_date
        ORDER BY play_date
        LIMIT 7
    """, (latest, latest))

    if not obs and not forecasts:
        return None

    sky_icons = {1: "☀️", 3: "⛅", 4: "☁️"}
    precip_icons = {0: "", 1: "🌧️", 2: "🌨️", 3: "❄️"}

    fc_list = []
    for f in forecasts:
        rain = f["avg_rain_prob"] or 0
        sky = sky_icons.get(f["max_sky"], "")
        precip = precip_icons.get(f["max_precip"], "")
        icon = precip if f["max_precip"] and f["max_precip"] > 0 else sky
        changes = (f["changes"] or "").split(",")
        has_change = "악화" in changes or "호전" in changes
        fc_list.append({
            "play_date": f["play_date"],
            "rain_prob": int(rain),
            "temp_high": f["avg_temp_high"],
            "icon": icon,
            "alert": rain >= 60,
            "forecast_changed": "악화" if "악화" in changes else "호전" if "호전" in changes else None,
        })

    return {
        "observation": dict(obs[0]) if obs else None,
        "forecasts": fc_list,
    }


def _calc_demand_density(db, latest, course_name, tee_interval=7, op_hours=(6, 16)):
    """시간대별 수요/소진율/잔여/밀도 계산.
    경기일별로 이론 최대 대비 잔여를 계산한 뒤 평균.
    """
    profile = COURSE_PROFILES.get(course_name, {})
    interval = profile.get("tee_interval_min", tee_interval)
    max_per_hour = 60 // interval  # per sub-course per play_date

    # 서브코스 수 (멤버십 제외)
    subs = q(db, """
        SELECT COUNT(DISTINCT course_sub) as cnt FROM latest_daily_snapshots
        WHERE collected_date=? AND course_name=? AND course_sub NOT LIKE '멤버십%'
    """, (latest, course_name))
    sub_count = subs[0]["cnt"] if subs else 1
    theoretical_max_per_day = max_per_hour * sub_count  # 1시간 × 1경기일

    # 경기일별 × 시간대별 잔여 슬롯
    slots_detail = q(db, """
        SELECT play_date,
               CAST(SUBSTR(tee_time, 1, 2) AS INTEGER) as hour,
               COUNT(*) as remaining
        FROM latest_daily_snapshots
        WHERE collected_date=? AND course_name=? AND course_sub NOT LIKE '멤버십%'
        GROUP BY play_date, hour ORDER BY hour
    """, (latest, course_name))

    # 시간대별 경기일 수
    play_dates_per_hour = defaultdict(set)
    for r in slots_detail:
        play_dates_per_hour[r["hour"]].add(r["play_date"])

    # 3시간 구간으로 묶기 (06~09, 09~12, 12~15, 15~16+)
    buckets = [
        {"label": "06~09시", "hours": [6, 7, 8]},
        {"label": "09~12시", "hours": [9, 10, 11]},
        {"label": "12~15시", "hours": [12, 13, 14]},
        {"label": "15~17시", "hours": [15, 16]},
    ]

    total_remaining_all = sum(r["remaining"] for r in slots_detail)

    result = []
    for bucket in buckets:
        bucket_slots = [r for r in slots_detail if r["hour"] in bucket["hours"]]
        if not bucket_slots:
            continue

        remaining = sum(r["remaining"] for r in bucket_slots)
        # 경기일 수 = 해당 시간대에 데이터 있는 경기일
        play_dates = set()
        for h in bucket["hours"]:
            play_dates.update(play_dates_per_hour.get(h, set()))
        num_days = len(play_dates) or 1

        # 이론 최대 = 경기일 수 × 시간 수 × 시간당 슬롯
        theoretical_total = num_days * len(bucket["hours"]) * theoretical_max_per_day
        consumed = max(0, theoretical_total - remaining)
        consume_rate = round(consumed / theoretical_total * 100, 1) if theoretical_total > 0 else 0
        density = round(remaining / total_remaining_all * 100, 1) if total_remaining_all > 0 else 0

        # 수요 판정
        if consume_rate >= 80:
            demand = "높음"
            signal = "🔥"
        elif consume_rate >= 50:
            demand = "보통"
            signal = "🟡"
        else:
            demand = "낮음"
            signal = "⚠️"

        result.append({
            "label": bucket["label"],
            "remaining": remaining,
            "theoretical_max": theoretical_total,
            "consume_rate": consume_rate,
            "density": density,
            "demand": demand,
            "signal": signal,
        })
    return result


def _calc_consumption_velocity(db, latest, course_name):
    """D-day 구간별 소진 속도 계산. 최소 2일 데이터 필요."""
    all_dates = [r["collected_date"] for r in q(db,
        "SELECT DISTINCT collected_date FROM latest_daily_snapshots ORDER BY collected_date")]
    if len(all_dates) < 2:
        return None

    # D-day 구간별 잔여 슬롯 추이
    ranges = [
        {"label": "D15+", "min": 15, "max": 99},
        {"label": "D8-14", "min": 8, "max": 14},
        {"label": "D1-7", "min": 1, "max": 7},
    ]

    result = []
    for rng in ranges:
        today_cnt = scalar(db,
            "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND d_day>=? AND d_day<=?",
            (latest, course_name, rng["min"], rng["max"])) or 0
        # Previous collection
        prev = all_dates[-2] if len(all_dates) >= 2 else None
        if prev:
            prev_cnt = scalar(db,
                "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND d_day>=? AND d_day<=?",
                (prev, course_name, rng["min"], rng["max"])) or 0
            daily_consumed = prev_cnt - today_cnt
        else:
            daily_consumed = 0
            prev_cnt = 0

        result.append({
            "label": rng["label"],
            "remaining": today_cnt,
            "daily_consumed": daily_consumed,
            "velocity": round(daily_consumed / max(prev_cnt, 1) * 100, 1) if prev_cnt > 0 else 0,
        })

    # Acceleration detection
    velocities = [r["velocity"] for r in result if r["velocity"] > 0]
    if len(velocities) >= 2:
        latest_v = velocities[-1]
        prev_v = velocities[-2]
        if prev_v > 0:
            ratio = latest_v / prev_v
            if ratio > 1.3:
                accel = "가속"
            elif ratio < 0.7:
                accel = "주춤"
            else:
                accel = "유지"
        else:
            accel = "유지"
    else:
        accel = "판단보류"

    return {"ranges": result, "acceleration": accel}


def _get_unsold_summary(db, latest):
    """미판매 요약: 전일 경기의 미판매 슬롯 분석."""
    try:
        unsold = q(db, """
            SELECT course_name, part_type, promo_flag, price_krw, membership_type, weather_cause
            FROM unsold_slots WHERE recorded_date = ?
        """, (latest,))
    except Exception:
        # weather_cause 컬럼이 아직 없는 경우 fallback
        unsold = q(db, """
            SELECT course_name, part_type, promo_flag, price_krw, membership_type
            FROM unsold_slots WHERE recorded_date = ?
        """, (latest,))
    if not unsold:
        return None
    total = len(unsold)
    # 매출 손실 = 1인 가격 × 4 + 카트비 (팀당)
    total_loss = 0
    for r in unsold:
        p = COURSE_PROFILES.get(r["course_name"], {})
        cart = p.get("cart_fee_team", 100000)
        total_loss += (r["price_krw"] or 0) * 4 + cart
    promo_unsold = sum(1 for r in unsold if r["promo_flag"])

    # 코스별 (건수 + 금액)
    by_course_count = defaultdict(int)
    by_course_loss = defaultdict(int)
    for r in unsold:
        by_course_count[r["course_name"]] += 1
        by_course_loss[r["course_name"]] += (r["price_krw"] or 0) * 4 + COURSE_PROFILES.get(r["course_name"], {}).get("cart_fee_team", 100000)
    course_list = sorted(by_course_count.items(), key=lambda x: -x[1])

    # 시간대별
    by_part = defaultdict(int)
    for r in unsold:
        by_part[r["part_type"] or "기타"] += 1

    # 기상 원인별
    by_weather = defaultdict(int)
    for r in unsold:
        wc = r.get("weather_cause")
        if wc:
            by_weather[wc] += 1

    return {
        "total": total,
        "total_loss_krw": total_loss,
        "promo_unsold": promo_unsold,
        "promo_unsold_pct": round(promo_unsold / total * 100, 1) if total else 0,
        "by_course": [{"course_name": c, "count": n, "loss_krw": by_course_loss[c]} for c, n in course_list],
        "by_part": dict(by_part),
        "by_weather_cause": dict(by_weather),
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
        FROM latest_daily_snapshots
        WHERE collected_date = ?
        ORDER BY course_name, play_date, tee_time
    """, (latest,))

    consumed_slots = []
    if prev:
        prev_keys = set(r["slot_group_key"] for r in q(db,
            "SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=?", (prev,)))
        today_keys = set(r["slot_group_key"] for r in q(db,
            "SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=?", (latest,)))

        # 신규오픈 판정: 이전 수집에 없던 play_date
        prev_pds = set(r["play_date"] for r in q(db,
            "SELECT DISTINCT play_date FROM latest_daily_snapshots WHERE collected_date=?", (prev,)))
        new_open_pds = set(r["play_date"] for r in q(db,
            "SELECT DISTINCT play_date FROM latest_daily_snapshots WHERE collected_date=?", (latest,))) - prev_pds

        # 어제 없었는데 오늘 있는 슬롯 중 과거 이력 조회 (티취소 판정)
        appeared_keys = today_keys - prev_keys
        history_keys = set()
        if appeared_keys:
            app_list = tuple(appeared_keys)
            app_ph = ",".join("?" * len(app_list))
            history_keys = set(r["slot_group_key"] for r in q(db,
                f"SELECT DISTINCT slot_group_key FROM latest_daily_snapshots WHERE slot_group_key IN ({app_ph}) AND collected_date < ?",
                app_list + (prev,)))

        # 오늘 슬롯 상태 분류 (세분화)
        for s in today_slots:
            if s["slot_group_key"] in prev_keys:
                s["status"] = "stayed"
            elif s["play_date"] in new_open_pds:
                s["status"] = "new_open"            # 신규오픈 (이전 max보다 먼 play_date)
            elif s["slot_group_key"] in history_keys:
                s["status"] = "cancel_reopen"       # 티취소 (재오픈)
            else:
                s["status"] = "add_open"             # 추가오픈

        # 소진된 슬롯 (어제 있었는데 오늘 없음)
        consumed_rows = q(db, """
            SELECT course_name, course_sub, membership_type, play_date, tee_time,
                   price_krw, promo_flag, d_day, slot_group_key, weekday_type, part_type
            FROM latest_daily_snapshots
            WHERE collected_date = ?
            ORDER BY course_name, play_date, tee_time
        """, (prev,))
        consumed_slots = [r for r in consumed_rows if r["slot_group_key"] not in today_keys]
        for c in consumed_slots:
            c["status"] = "consumed"
    else:
        for s in today_slots:
            s["status"] = "new_open"

    # 골프장별 생애주기 집계
    lifecycle_summary = defaultdict(lambda: {
        "active": 0, "consumed": 0, "new_open": 0,
        "cancel_reopen": 0, "stayed": 0,
        "total": 0, "avg_price": 0, "prices": []
    })

    for s in today_slots:
        cn = s["course_name"]
        lifecycle_summary[cn]["total"] += 1
        lifecycle_summary[cn]["prices"].append(s["price_krw"])
        status = s.get("status", "stayed")
        if status == "stayed":
            lifecycle_summary[cn]["stayed"] += 1
        elif status == "new_open":
            lifecycle_summary[cn]["new_open"] += 1
        elif status in ("cancel_reopen", "add_open"):
            lifecycle_summary[cn]["cancel_reopen"] += 1

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
        FROM latest_daily_snapshots
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
            SELECT slot_group_key, weekday_type, part_type, course_name, price_krw, promo_flag, play_date
            FROM latest_daily_snapshots WHERE collected_date=?
        """, (prev,))
        today_keys = set(r["slot_group_key"] for r in q(db,
            "SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=?", (latest,)))

        # 요일 × 파트별 소진 집계
        grid = defaultdict(lambda: {"total": 0, "consumed": 0, "promo_consumed": 0})
        for s in prev_keys_full:
            key = (s["weekday_type"], s["part_type"])
            grid[key]["total"] += 1
            if s["slot_group_key"] not in today_keys:
                # 미판매 제외: play_date가 latest 이전이면 소진이 아니라 미판매(경기일 지남)
                if s.get("play_date", "") > latest:
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
                # 미판매 제외: play_date가 latest 이전이면 소진이 아니라 미판매(경기일 지남)
                if s.get("play_date", "") > latest:
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
        FROM latest_daily_snapshots
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
        FROM latest_daily_snapshots
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
        FROM latest_daily_snapshots
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

    # 전체 포함 (샘플링 없음)
    _sampled = sorted(scatter_raw, key=lambda r: (r["course_name"], r["d_day"]))

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
        FROM latest_daily_snapshots WHERE collected_date = ?
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

    # ── 기상 원인 태깅 ──
    _weather_causes = _get_weather_causes(db, latest)
    for ev in discount_events:
        ev["weather_cause"] = _weather_causes.get(ev.get("play_date"))

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
        FROM latest_daily_snapshots
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
        FROM latest_daily_snapshots
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
    """할인 강도 분석 — 최초 포착 가격(정가) 대비 현재 가격"""
    # 공개제 슬롯만 분석
    all_slots = q(db, """
        SELECT course_name, course_sub, weekday_type, part_type, membership_type,
               price_krw, promo_flag, d_day, play_date, slot_group_key
        FROM latest_daily_snapshots
        WHERE collected_date = ?
          AND (membership_type = '대중제' OR membership_type IS NULL)
          AND course_sub NOT LIKE '멤버십%'
        ORDER BY course_name
    """, (latest,))

    # 슬롯별 최초 포착 가격 조회 (정가 기준)
    first_prices = {}
    if all_slots:
        keys = list(set(s["slot_group_key"] for s in all_slots if s.get("slot_group_key")))
        # 배치 조회 (1000개씩)
        for i in range(0, len(keys), 500):
            batch = keys[i:i+500]
            ph = ",".join("?" * len(batch))
            rows = q(db, f"""
                SELECT slot_group_key, price_krw, collected_date
                FROM latest_daily_snapshots
                WHERE slot_group_key IN ({ph})
                AND price_krw IS NOT NULL
                ORDER BY collected_date ASC
            """, tuple(batch))
            for r in rows:
                if r["slot_group_key"] not in first_prices:
                    first_prices[r["slot_group_key"]] = r["price_krw"]

    # 세그먼트별 비할인 중앙값 (폴백용)
    seg_prices = defaultdict(list)
    for s in all_slots:
        if not s["promo_flag"]:
            key = (s["course_name"], s["weekday_type"], s["part_type"])
            seg_prices[key].append(s["price_krw"])
    seg_baselines = {}
    for key, prices in seg_prices.items():
        seg_baselines[key] = statistics.median(prices) if prices else None

    # 할인 강도 계산 (정가 = 최초 포착 가격 우선, 폴백 = 세그먼트 중앙값)
    yield_slots = []
    for s in all_slots:
        # 1순위: 최초 포착 가격
        baseline = first_prices.get(s.get("slot_group_key"))
        baseline_type = "first_seen"
        # 2순위: 세그먼트 비할인 중앙값
        if not baseline or baseline <= 0:
            key = (s["course_name"], s["weekday_type"], s["part_type"])
            baseline = seg_baselines.get(key)
            baseline_type = "segment"
        # 3순위: 코스 전체 비할인 중앙값
        if not baseline or baseline <= 0:
            cn_prices = [x["price_krw"] for x in all_slots
                         if x["course_name"] == s["course_name"] and not x["promo_flag"]]
            baseline = statistics.median(cn_prices) if cn_prices else None
            baseline_type = "course"

        if baseline and baseline > 0:
            yield_val = round(s["price_krw"] / baseline, 3)
            discount_pct = round((1 - yield_val) * 100, 1)
            yield_slots.append({
                "course_name": s["course_name"],
                "weekday_type": s["weekday_type"],
                "part_type": s["part_type"],
                "price_krw": s["price_krw"],
                "promo_flag": s["promo_flag"],
                "yield": yield_val,
                "discount_pct": discount_pct,
                "baseline": baseline,
                "baseline_type": baseline_type,
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
        wday_avg = round(statistics.mean(wday_yields), 3) if wday_yields else None
        wend_avg = round(statistics.mean(wend_yields), 3) if wend_yields else None
        # 할인 강도: (1 - yield) * 100  → 양수면 할인 중, 음수면 프리미엄
        wday_discount = round((1 - wday_avg) * 100, 1) if wday_avg else None
        wend_discount = round((1 - wend_avg) * 100, 1) if wend_avg else None
        yield_summary.append({
            "course_name": cn,
            "weekday_avg_yield": wday_avg,
            "weekend_avg_yield": wend_avg,
            "weekday_discount_pct": wday_discount,   # 할인 강도 (양수=할인, 음수=프리미엄)
            "weekend_discount_pct": wend_discount,
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
        "yield_slots": yield_slots,
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
        FROM latest_daily_snapshots
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
            FROM latest_daily_snapshots
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
        "SELECT DISTINCT course_name FROM latest_daily_snapshots WHERE collected_date=? ORDER BY course_name",
        (latest,))]

    # 전일 대비 소진 데이터
    today_keys_all = set(r["slot_group_key"] for r in q(db,
        "SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=?", (latest,)))
    prev_keys_all = set(r["slot_group_key"] for r in q(db,
        "SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=?", (prev,))) if prev else set()

    all_diagnostics = []

    for course in courses:
        findings = []

        # ── 오늘 슬롯 정보 ──
        today_course = q(db, """
            SELECT slot_group_key, price_krw, promo_flag, d_day, weekday_type,
                   part_type, course_sub, membership_type
            FROM latest_daily_snapshots
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
            FROM latest_daily_snapshots
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
                "SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?",
                (prev, course)))
            today_course_keys = set(s["slot_group_key"] for s in today_course)
            consumed_keys = prev_course_keys - today_course_keys

            if consumed_keys:
                # 전일 소진된 비할인 슬롯 (subquery 방식)
                non_promo_consumed = q(db, """
                    SELECT s.price_krw, s.d_day, s.promo_flag
                    FROM latest_daily_snapshots s
                    WHERE s.collected_date=? AND s.course_name=?
                      AND s.slot_group_key NOT IN (
                        SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=?
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

    # 구장별 종합 해설 생성 (템플릿 기반)
    narratives = _generate_course_narratives(db, latest, prev, all_diagnostics)
    for diag in all_diagnostics:
        diag["narrative"] = narratives.get(diag["course_name"], "")

    # 수집 일수
    all_dates = [r["collected_date"] for r in q(db,
        "SELECT DISTINCT collected_date FROM latest_daily_snapshots ORDER BY collected_date")]
    data_days = len(all_dates)

    return {
        "diagnostics": all_diagnostics,
        "data_days": data_days,
        "rules_applicable": ["A", "B", "E", "H"],
        "rules_pending": ["C", "D", "F", "G", "I", "J"],
        "data_note": f"현재 {data_days}일 데이터 기준." + (" C/D/F/G/I/J 룰은 30일+ 축적 후 활성화" if data_days < 30 else ""),
    }


def _generate_course_narratives(db, latest, prev, diagnostics):
    """구장별 종합 해설 문장 생성 (템플릿 기반)."""
    narratives = {}

    # consumption 데이터 (Tab1에서 이미 계산된 것과 동일 로직)
    for diag in diagnostics:
        cn = diag["course_name"]
        parts = []

        # 슬롯 수
        total = scalar(db,
            "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?",
            (latest, cn)) or 0

        # 소진율
        if prev:
            prev_cnt = scalar(db,
                "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=?",
                (prev, cn)) or 0
            if prev_cnt > 0:
                consumed = prev_cnt - total  # 단순 차이
                rate = round(abs(consumed) / prev_cnt * 100, 1)
                parts.append(f"잔여 {total:,}슬롯, 전일 대비 {'소진' if consumed > 0 else '증가'} {abs(consumed)}건(소진율 {rate}%)")

        # 특가 분석
        promo_data = q(db, """
            SELECT COUNT(*) as total, SUM(CASE WHEN promo_flag=1 THEN 1 ELSE 0 END) as promo
            FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND course_sub NOT LIKE '멤버십%'
        """, (latest, cn))
        if promo_data and promo_data[0]["total"] > 0:
            pct = round(promo_data[0]["promo"] / promo_data[0]["total"] * 100, 1)
            if pct >= 80:
                parts.append(f"특가율 {pct}%로 상시 할인 구조(마케팅 특가)")
            elif pct >= 20:
                parts.append(f"특가율 {pct}%로 적극적 할인 운영 중")
            elif pct > 0:
                parts.append(f"특가율 {pct}%로 소폭 할인")
            else:
                parts.append("특가 없이 정가 판매 유지")

        # 미판매
        unsold_cnt = scalar(db,
            "SELECT COUNT(*) FROM unsold_slots WHERE recorded_date=? AND course_name=?",
            (latest, cn)) or 0
        if unsold_cnt > 0:
            unsold_loss = scalar(db,
                "SELECT SUM(price_krw) FROM unsold_slots WHERE recorded_date=? AND course_name=?",
                (latest, cn)) or 0
            promo_unsold = scalar(db,
                "SELECT COUNT(*) FROM unsold_slots WHERE recorded_date=? AND course_name=? AND promo_flag=1",
                (latest, cn)) or 0
            parts.append(f"미판매 {unsold_cnt}건(추정 손실 {unsold_loss//10000:,}만원)")
            if promo_unsold > 0:
                parts.append(f"특가 미판매 {promo_unsold}건 — 할인해도 수요 부족 구간 존재")

        # D-day 분포
        dday_near = scalar(db,
            "SELECT COUNT(*) FROM latest_daily_snapshots WHERE collected_date=? AND course_name=? AND d_day <= 3",
            (latest, cn)) or 0
        if dday_near > 0:
            parts.append(f"D1-3 임박 잔여 {dday_near}개")

        # 수요 밀도
        density = _calc_demand_density(db, latest, cn)
        high_demand = [d for d in density if d["consume_rate"] >= 80]
        low_demand = [d for d in density if d["consume_rate"] < 50]
        if high_demand:
            hours = ", ".join(d["label"] for d in high_demand[:3])
            parts.append(f"수요 높은 시간대: {hours} (인상 여력)")
        if low_demand:
            hours = ", ".join(d["label"] for d in low_demand[:3])
            parts.append(f"수요 부진 시간대: {hours} (할인 검토)")

        # 소진 속도
        velocity = _calc_consumption_velocity(db, latest, cn)
        if velocity:
            accel = velocity["acceleration"]
            if accel == "가속":
                parts.append("소진 속도 가속 중 — 가격 유지 또는 인상 검토")
            elif accel == "주춤":
                parts.append("소진 속도 주춤 — 할인 투입 시점 검토")

        # 기상 영향
        weather_note = None
        try:
            wf = q(db, """
                SELECT rain_prob, forecast_changed FROM weather_forecasts
                WHERE forecast_date=? AND course_name=? AND rain_prob >= 60 LIMIT 1
            """, (latest, cn))
            if wf:
                weather_note = f"우천 예보(강수확률 {wf[0]['rain_prob']}%) 영향 가능"
        except Exception:
            pass
        if weather_note:
            parts.append(weather_note)

        # 종합 판정
        sev = diag.get("severity_max", 0)
        if sev >= 3:
            parts.insert(0, "⚠️ 즉시 대응 필요.")
        elif sev >= 2:
            parts.insert(0, "주의 관찰 필요.")

        narratives[cn] = " ".join(parts) if parts else "데이터 축적 중."

    return narratives

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
               d_day, season, slot_group_key
        FROM latest_daily_snapshots
        WHERE collected_date = ?
        ORDER BY course_name, play_date, tee_time
    """, (date,))

    for r in rows:
        if r["membership_type"] is None:
            r["membership_type"] = "단일"
        r["sub_display"] = get_sub_label(r["course_sub"], r["membership_type"])

    # Add slot_status: 이전 수집에 없던 play_date = 신규오픈
    prev = scalar(db, "SELECT MAX(collected_date) FROM latest_daily_snapshots WHERE collected_date < ?", (date,))
    if prev:
        prev_keys = set(r2["slot_group_key"] for r2 in q(db,
            "SELECT slot_group_key FROM latest_daily_snapshots WHERE collected_date=?", (prev,)))
        # 코스별 이전 play_date + max play_date
        prev_pds_by_course = {}
        prev_max_by_course = {}
        for r2 in q(db, "SELECT course_name, play_date FROM latest_daily_snapshots WHERE collected_date=?", (prev,)):
            prev_pds_by_course.setdefault(r2["course_name"], set()).add(r2["play_date"])
            cur_max = prev_max_by_course.get(r2["course_name"], "")
            if r2["play_date"] > cur_max:
                prev_max_by_course[r2["course_name"]] = r2["play_date"]

        for r in rows:
            sgk = r.get("slot_group_key")
            course_prev_pds = prev_pds_by_course.get(r["course_name"], set())
            course_max = prev_max_by_course.get(r["course_name"], "")
            if r["play_date"] not in course_prev_pds and r["play_date"] > course_max:
                r["slot_status"] = "new_open"
            elif sgk and sgk not in prev_keys:
                r["slot_status"] = "cancel_reopen"
            else:
                r["slot_status"] = "stayed"
            r.pop("slot_group_key", None)
    else:
        for r in rows:
            r["slot_status"] = "new_open"
            r.pop("slot_group_key", None)

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
        FROM latest_daily_snapshots
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
def build_v5_data(db, skip_ai=False):
    """Build complete V5 structure with all dates keyed."""
    meta = get_metadata(db)
    dates = meta["all_dates"]
    latest = meta["latest_date"]
    prev = meta["prev_date"]

    # Tab4, Tab5a: 날짜별 데이터 생성 (기준일 전환 지원)
    tab4_all = {}
    tab5a_all = {}
    for i, d in enumerate(dates):
        p = dates[i - 1] if i > 0 else None
        tab4_all[d] = get_tab4(db, d)
        tab5a_all[d] = get_tab5a(db, d, p)

    # TAB 7: skip_ai 시 기존 데이터 재사용
    if skip_ai:
        tab7_data = _load_previous_tab7()
        print("  [skip-ai] TAB 7 AI 진단: 이전 데이터 재사용")
    else:
        tab7_data = get_tab7_all(db, dates)

    v5_data = {
        "metadata": meta,
        "tab1": get_tab1_all(db, dates),
        "tab3": get_tab3_all(db, dates),
        "tab4": tab4_all,
        "tab5a": tab5a_all,
        "tab5b": get_tab5b_all(db, dates),
        "tab6": get_tab6_all(db, dates),
        "tab7": tab7_data,
        # tab8: excluded (separate JSON files per date)
    }
    return v5_data


def _load_previous_tab7():
    """기존 dashboard_data.json에서 tab7 데이터를 읽어 재사용"""
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
        return prev_data.get("tab7", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

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

    # 날짜별 풀 대시보드 보관 (과거 조회용)
    import shutil
    archive_dir = os.path.join(os.path.dirname(OUT_PATH) or ".", "dashboard_archive")
    os.makedirs(archive_dir, exist_ok=True)
    dated_path = os.path.join(archive_dir, f"dashboard_data_{latest}.json")
    shutil.copy2(OUT_PATH, dated_path)
    print(f"  → {dated_path} 아카이브 저장")

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
            # Tab4: date-keyed — 각 날짜별로 scatter 샘플링
            tab4_embed = {}
            if isinstance(data.get("tab4"), dict):
                for dk, dv in data["tab4"].items():
                    if isinstance(dv, dict) and "scatter" in dv:
                        tab4_embed[dk] = {
                            "dday_trend": dv.get("dday_trend", []),
                            "histogram": dv.get("histogram", []),
                            "price_events": dv.get("price_events", []),
                            "scatter": dv.get("scatter", []),
                            "ghost_events": dv.get("ghost_events", []),
                        }
                    else:
                        tab4_embed[dk] = dv
            embed = {
                "metadata": data["metadata"],
                "tab1": data["tab1"],  # keyed by date
                "tab3": data["tab3"],  # keyed by date
                "tab4": tab4_embed,
                "tab5a": data["tab5a"],  # keyed by date
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
            "scatter": data["tab4"]["scatter"],
            "ghost_events": data["tab4"].get("ghost_events", []),
        },
        "tab5a": data["tab5a"] if "tab5a" in data else {},
        "tab5b": {
            "yield_slots": data["tab5b"]["yield_slots"],
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
