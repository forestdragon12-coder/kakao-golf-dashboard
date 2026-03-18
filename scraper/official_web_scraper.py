"""
공식 홈페이지 직접 수집 스크래퍼

ReservationController.asp 기반 골프장 공통 스크래퍼.
- 르오네뜨 (coDiv=215, lehonnetecc.com)
- 베르힐 함평 (coDiv=214, verthillcc.co.kr)

Playwright로 로그인 후 API 호출하여 티타임 데이터 수집.
카카오/티스캐너 스크래퍼와 동일 row dict 포맷으로 DB 저장.
"""
import asyncio
import json
import os
from datetime import date, timedelta, datetime
from pathlib import Path
from loguru import logger
from playwright.async_api import async_playwright

from config.courses import get_season, get_weekday_type, get_part_type
from db.database import (
    make_hash,
    make_slot_identity_key,
    make_slot_key,
    make_slot_observation_key,
    normalize_course_variant,
)

SOURCE_CHANNEL = "official_web"
COLLECT_DAYS = 30

# 골프장별 설정
SITES = {
    "르오네뜨": {
        "coDiv": "215",
        "domain": "https://www.lehonnetecc.com",
        "login_path": "/join/login.asp",
        "reserve_path": "/reservation/reservation.asp",
        "id_selector": 'input[type="text"]',
        "pw_selector": 'input[type="password"]',
        "extra_tee_params": {
            "msDivision": "21",
            "msClass": "00",
            "msLevel": "00",
        },
    },
    "베르힐": {
        "coDiv": "214",
        "domain": "https://www.verthillcc.co.kr",
        "login_path": "/member/login.asp",
        "reserve_path": "/reservation/reservation.asp",
        "id_selector": "#txtId",
        "pw_selector": "#txtPw",
        "extra_tee_params": {},
    },
}


def _load_credentials() -> dict:
    """환경변수 또는 .env에서 골프장별 로그인 정보 로드"""
    creds = {}
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    for course_name, site in SITES.items():
        key_prefix = course_name.upper().replace(" ", "_")
        # LEHONNETE_ID / LEHONNETE_PW 또는 VERHILL_ID / VERHILL_PW
        alt_prefix = {
            "르오네뜨": "LEHONNETE",
            "베르힐": "VERHILL",
        }.get(course_name, key_prefix)

        uid = os.getenv(f"{alt_prefix}_ID", "")
        pw = os.getenv(f"{alt_prefix}_PW", "")
        if uid and pw:
            creds[course_name] = {"id": uid, "pw": pw}

    return creds


class OfficialWebScraper:
    """공식 홈페이지 ReservationController 기반 스크래퍼"""

    def __init__(self):
        self.today = date.today()
        now = datetime.now()
        self.collected_date = self.today.isoformat()
        self.collected_at = now.strftime("%Y-%m-%dT%H:%M:00")
        self.credentials = _load_credentials()

    async def collect_course(self, course_name: str) -> list[dict]:
        """1개 골프장 수집 (로그인 → 캘린더 → 티타임)"""
        site = SITES.get(course_name)
        if not site:
            logger.warning(f"[공식HP] '{course_name}' 미지원")
            return []

        cred = self.credentials.get(course_name)
        if not cred:
            logger.warning(f"[공식HP] '{course_name}' 로그인 정보 없음")
            return []

        all_rows = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                page = await browser.new_page()
                page.on("dialog", lambda d: d.accept())

                # 1. 로그인
                ok = await self._login(page, site, cred)
                if not ok:
                    await browser.close()
                    return []

                # 2. 예약 페이지 이동
                await page.goto(
                    site["domain"] + site["reserve_path"],
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await asyncio.sleep(2)

                # 3. 캘린더 조회 → 예약 가능 날짜 수집
                avail_dates = await self._get_available_dates(page, site)
                logger.info(f"[공식HP:{course_name}] 예약 가능 {len(avail_dates)}일")

                # 4. 각 날짜별 티타임 수집
                for play_date_str, team_count in avail_dates:
                    tee_rows = await self._get_tee_list(
                        page, site, course_name, play_date_str
                    )
                    all_rows.extend(tee_rows)

                await browser.close()

        except Exception as e:
            logger.error(f"[공식HP:{course_name}] 수집 오류: {e}")

        logger.info(f"[공식HP:{course_name}] 수집 완료: {len(all_rows)}건")
        return all_rows

    async def collect_courses(self, target_courses: list[str] = None) -> list[dict]:
        """여러 골프장 순차 수집"""
        targets = target_courses or list(SITES.keys())
        all_rows = []
        for name in targets:
            if name in SITES:
                rows = await self.collect_course(name)
                all_rows.extend(rows)
        return all_rows

    # ─── 로그인 ───

    async def _login(self, page, site: dict, cred: dict) -> bool:
        """공식 홈페이지 로그인"""
        try:
            url = site["domain"] + site["login_path"]
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1)

            await page.locator(site["id_selector"]).first.fill(cred["id"])
            await page.locator(site["pw_selector"]).first.fill(cred["pw"])
            await page.evaluate("doLogin()")
            await asyncio.sleep(3)

            if "login" in page.url.lower():
                logger.error(f"[공식HP] 로그인 실패: {site['domain']}")
                return False

            logger.debug(f"[공식HP] 로그인 성공: {site['domain']}")
            return True

        except Exception as e:
            logger.error(f"[공식HP] 로그인 오류: {e}")
            return False

    # ─── 캘린더 조회 ───

    async def _get_available_dates(self, page, site: dict) -> list[tuple]:
        """예약 가능 날짜 목록 (YYYYMMDD, 팀수) 반환"""
        coDiv = site["coDiv"]
        avail = []

        # 현재 월 ~ +2개월
        now = date.today()
        months = []
        for i in range(3):
            dt = now.replace(day=1) + timedelta(days=32 * i)
            months.append(dt.strftime("%Y%m"))
        # 중복 제거
        months = list(dict.fromkeys(months))

        for ym in months:
            try:
                cal_json = await page.evaluate(f"""
                    () => {{
                        return new Promise((resolve) => {{
                            var params = {{}};
                            params["method"] = "getCalendar";
                            params["coDiv"] = "{coDiv}";
                            params["selYm"] = "{ym}";
                            mAjax("/controller/ReservationController.asp", params, "POST", true, function(data) {{
                                resolve(JSON.stringify(data));
                            }});
                            setTimeout(() => resolve('{{"rows":[]}}'), 10000);
                        }});
                    }}
                """)
                cal_data = json.loads(cal_json)
                today_str = now.strftime("%Y%m%d")

                for row in cal_data.get("rows", []):
                    solar = row.get("CL_SOLAR", "")
                    team = int(row.get("BK_TEAM", 0))
                    if solar > today_str and team > 0:
                        avail.append((solar, team))

            except Exception as e:
                logger.debug(f"[공식HP] 캘린더 {ym} 오류: {e}")

        return avail

    # ─── 티타임 조회 ───

    async def _get_tee_list(
        self, page, site: dict, course_name: str, play_date_str: str
    ) -> list[dict]:
        """특정 날짜의 티타임 목록 → DB row 형식으로 변환"""
        try:
            # onClickDay → doSearch 경유 (베르힐 등 세션 의존 사이트 호환)
            captured = []

            async def on_resp(resp):
                if "ReservationController" in resp.url:
                    try:
                        body = await resp.text()
                        if '"getTeeList"' not in body and '"rows"' in body:
                            captured.append(body)
                        elif "BK_TIME" in body:
                            captured.append(body)
                    except:
                        pass

            page.on("response", on_resp)
            await page.evaluate(f"onClickDay('{play_date_str}')")
            await asyncio.sleep(2)
            page.remove_listener("response", on_resp)

            if captured:
                tee_data = json.loads(captured[-1])
                api_rows = tee_data.get("rows", [])
                if api_rows:
                    return self._build_rows(api_rows, course_name, play_date_str)

            # fallback: 직접 mAjax 호출
            coDiv = site["coDiv"]
            extra = site.get("extra_tee_params", {})
            params_js_parts = [
                f'params["method"] = "getTeeList";',
                f'params["coDiv"] = "{coDiv}";',
                f'params["date"] = "{play_date_str}";',
            ]
            for k, v in extra.items():
                params_js_parts.append(f'params["{k}"] = "{v}";')
            params_js = "\n".join(params_js_parts)

            tee_json = await page.evaluate(f"""
                () => {{
                    return new Promise((resolve) => {{
                        var params = {{}};
                        {params_js}
                        mAjax("/controller/ReservationController.asp", params, "POST", true, function(data) {{
                            resolve(JSON.stringify(data));
                        }});
                        setTimeout(() => resolve('{{"rows":[]}}'), 10000);
                    }});
                }}
            """)
            tee_data = json.loads(tee_json)
            api_rows = tee_data.get("rows", [])
            if api_rows:
                return self._build_rows(api_rows, course_name, play_date_str)

            return []

        except Exception as e:
            logger.debug(f"[공식HP:{course_name}] {play_date_str} 티타임 오류: {e}")
            return []

    # ─── row 변환 ───

    def _build_rows(
        self, api_rows: list[dict], course_name: str, play_date_str: str
    ) -> list[dict]:
        """API 응답 → 카카오/티스캐너 호환 row dict 리스트"""
        play_date = date(
            int(play_date_str[:4]),
            int(play_date_str[4:6]),
            int(play_date_str[6:8]),
        )
        d_day = (play_date - self.today).days
        weekday_type = get_weekday_type(play_date.weekday())
        season = get_season(play_date.month)

        rows = []
        for item in api_rows:
            bk_time = item.get("BK_TIME", "")
            if len(bk_time) < 4:
                continue
            tee_time = f"{bk_time[:2]}:{bk_time[2:]}"
            hour = int(bk_time[:2])
            if hour < 5 or hour > 19:
                continue

            part_type = get_part_type(hour)
            course_sub = item.get("BK_COS_NM", "")

            # 가격: BK_B_CHARGE_NM(정상가), BK_S_CHARGE_NM(특가)
            normal_str = str(item.get("BK_B_CHARGE_NM", "0")).replace(",", "")
            sale_str = str(item.get("BK_S_CHARGE_NM", "")).replace(",", "")

            try:
                normal_price = int(normal_str) if normal_str else 0
            except ValueError:
                normal_price = 0
            try:
                sale_price = int(sale_str) if sale_str else None
            except ValueError:
                sale_price = None

            price_krw = sale_price if sale_price and sale_price > 0 else normal_price
            promo_flag = 1 if sale_price and sale_price > 0 else 0
            sale_memo = item.get("SALE_MEMO_NM", "")
            promo_text = sale_memo if sale_memo else ("특가" if promo_flag else "")

            course_variant = normalize_course_variant(
                course_sub=course_sub or None
            )
            slot_identity_key = make_slot_identity_key(
                0,
                play_date.isoformat(),
                tee_time,
                part_type,
                course_variant,
                SOURCE_CHANNEL,
            )

            row = {
                "course_name": course_name,
                "collected_date": self.collected_date,
                "collected_at": self.collected_at,
                "play_date": play_date.isoformat(),
                "tee_time": tee_time,
                "price_krw": price_krw,
                "course_sub": course_sub or None,
                "membership_type": "",
                "promo_flag": promo_flag,
                "promo_text": promo_text or None,
                "pax_condition": "4인",
                "price_type": item.get("BK_CS", ""),
                "d_day": d_day,
                "part_type": part_type,
                "season": season,
                "weekday_type": weekday_type,
                "source_channel": SOURCE_CHANNEL,
                "course_variant": course_variant,
                "slot_identity_key": slot_identity_key,
                "slot_observation_key": make_slot_observation_key(
                    slot_identity_key, self.collected_at
                ),
                "hash_key": make_hash(
                    course_name,
                    self.collected_at,
                    play_date.isoformat(),
                    tee_time,
                    course_sub,
                ),
                "slot_group_key": make_slot_key(
                    course_name,
                    play_date.isoformat(),
                    tee_time,
                    course_sub,
                ),
                "listed_price_krw": normal_price,
                "normal_price_krw": normal_price,
                "sale_price_krw": sale_price,
                "price_badge": promo_text or None,
            }
            rows.append(row)

        return rows
