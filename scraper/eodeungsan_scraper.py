"""
어등산CC 공식 홈페이지 스크래퍼 (eodeungsancc.com)

Vue.js SPA + REST API 방식.
- API Base: https://api.eodeungsancc.com/v1
- 로그인: POST /auth/issue → JWT 토큰
- 인증 헤더: Authorization: {membershipId} {accessToken}
- 캘린더: GET /reservation-calender?year=Y&month=M
- 상세: GET /reservation-calender/YYYY-MM-DD → resveTimes[]
- 코스: 1=어등, 2=송정, 3=하남
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
COURSE_NAME = "어등산"
API_BASE = "https://api.eodeungsancc.com/v1"

COURSE_MAP = {"1": "어등", "2": "송정", "3": "하남"}
PART_MAP = {"1": "1부", "2": "2부", "3": "3부"}


def _load_creds() -> dict:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    uid = os.getenv("EODEUNGSAN_ID", "")
    pw = os.getenv("EODEUNGSAN_PW", "")
    return {"id": uid, "pw": pw} if uid and pw else {}


class EodeungsanScraper:

    def __init__(self):
        self.today = date.today()
        now = datetime.now()
        self.collected_date = self.today.isoformat()
        self.collected_at = now.strftime("%Y-%m-%dT%H:%M:00")
        self.creds = _load_creds()

    async def collect_course(self) -> list[dict]:
        if not self.creds:
            logger.warning(f"[{COURSE_NAME}] 로그인 정보 없음 (EODEUNGSAN_ID/PW)")
            return []

        all_rows = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = await browser.new_page()
                # SPA 로드 (CORS 쿠키용)
                await page.goto("https://www.eodeungsancc.com", wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(1)

                token, membership_id = await self._login(page)
                if not token:
                    await browser.close()
                    return []

                headers = {"Authorization": f"{membership_id} {token}"}

                # 오픈 날짜 수집 (현재월 ~ +2개월)
                open_dates = []
                for m_offset in range(3):
                    target = self.today.replace(day=1) + timedelta(days=32 * m_offset)
                    y, m = target.year, target.month
                    dates = await self._fetch_calendar(page, headers, y, m)
                    open_dates.extend(dates)

                logger.info(f"[{COURSE_NAME}] 오픈 날짜 {len(open_dates)}일")

                # 날짜별 상세 조회
                for play_date_str in open_dates:
                    rows = await self._fetch_tee_times(page, headers, play_date_str)
                    all_rows.extend(rows)

                await browser.close()
        except Exception as e:
            logger.error(f"[{COURSE_NAME}] 수집 오류: {e}")

        logger.info(f"[{COURSE_NAME}] 수집 완료: {len(all_rows)}건")
        return all_rows

    async def _login(self, page) -> tuple[str, str]:
        try:
            resp = await page.request.post(
                f"{API_BASE}/auth/issue",
                data=json.dumps({"idHpNo": self.creds["id"], "password": self.creds["pw"]}),
                headers={"Content-Type": "application/json"},
            )
            data = await resp.json()
            if data.get("status") != "OK":
                logger.error(f"[{COURSE_NAME}] 로그인 실패: {data.get('status')}")
                return "", ""

            token = data["data"]["accessToken"]
            memberships = data["data"].get("tgMemberships", [])
            membership_id = memberships[0]["membershipId"] if memberships else ""
            logger.debug(f"[{COURSE_NAME}] 로그인 성공 (membershipId={membership_id})")
            return token, membership_id
        except Exception as e:
            logger.error(f"[{COURSE_NAME}] 로그인 오류: {e}")
            return "", ""

    async def _fetch_calendar(self, page, headers: dict, year: int, month: int) -> list[str]:
        """월별 캘린더 조회 → 잔여석 있는 날짜 목록"""
        try:
            resp = await page.request.get(
                f"{API_BASE}/reservation-calender?year={year}&month={month}",
                headers=headers,
            )
            data = await resp.json()
            if data.get("status") != "OK":
                return []

            open_dates = []
            for cal in data["data"]["calenders"]:
                bsn_date = cal["bsnDate"]
                play_date = date.fromisoformat(bsn_date)
                if play_date <= self.today:
                    continue
                remain = cal.get("reservationAvailableTimeCount", 0)
                status = cal.get("availableStatusByDate", "")
                if remain > 0 or status == "ING":
                    open_dates.append(bsn_date)
            return open_dates
        except Exception as e:
            logger.debug(f"[{COURSE_NAME}] 캘린더 {year}-{month:02d} 오류: {e}")
            return []

    async def _fetch_tee_times(self, page, headers: dict, play_date_str: str) -> list[dict]:
        """날짜별 티타임 상세 조회"""
        try:
            resp = await page.request.get(
                f"{API_BASE}/reservation-calender/{play_date_str}",
                headers=headers,
            )
            data = await resp.json()
            if data.get("status") != "OK":
                return []

            resve_times = data["data"].get("resveTimes", [])
            return self._parse_tee_times(resve_times, play_date_str)
        except Exception as e:
            logger.debug(f"[{COURSE_NAME}] {play_date_str} 상세 오류: {e}")
            return []

    def _parse_tee_times(self, resve_times: list[dict], play_date_str: str) -> list[dict]:
        play_date = date.fromisoformat(play_date_str)
        d_day = (play_date - self.today).days
        weekday_type = get_weekday_type(play_date.weekday())
        season = get_season(play_date.month)

        rows = []
        for t in resve_times:
            # EMPTY만 수집 (예약 가능 슬롯)
            if t.get("timeStatus") != "EMPTY":
                continue
            # 웹 오픈 아닌 것 제외
            if not t.get("webOpenFlag", False):
                continue

            tee_time = t["resveTime"]  # "06:47"
            hour = int(tee_time.split(":")[0])
            if hour < 5 or hour > 19:
                continue

            course_code = str(t.get("resveCourse", ""))
            course_sub = COURSE_MAP.get(course_code, course_code)
            part_type = get_part_type(hour)

            # 가격 결정: promtnPrice(프로모션) > eventPrice > price > norPrice
            nor_price = int(t.get("norPrice", 0))
            price = int(t.get("price", 0)) or nor_price
            event_price = int(t.get("eventPrice", 0))
            promtn_price = int(t.get("promtnPrice", 0))

            # 표시 가격 = 가장 낮은 유효 가격
            display_price = price
            promo_flag = 0
            promo_text = None

            promtn = t.get("tgResvePromtn")
            if promtn and promtn_price > 0:
                display_price = promtn_price
                promo_flag = 1
                promo_text = promtn.get("promtnName", "프로모션")
            elif event_price > 0 and event_price < price:
                display_price = event_price
                promo_flag = 1
                promo_text = "이벤트"

            pax = f"{t.get('visitCnt', 4)}인"
            course_variant = normalize_course_variant(course_sub=course_sub)
            slot_id_key = make_slot_identity_key(
                0, play_date_str, tee_time, part_type, course_variant, SOURCE_CHANNEL
            )

            row = {
                "course_name": COURSE_NAME,
                "collected_date": self.collected_date,
                "collected_at": self.collected_at,
                "play_date": play_date_str,
                "tee_time": tee_time,
                "price_krw": display_price,
                "course_sub": course_sub,
                "membership_type": "대중제",
                "promo_flag": promo_flag,
                "promo_text": promo_text,
                "pax_condition": pax,
                "price_type": "",
                "d_day": d_day,
                "part_type": part_type,
                "season": season,
                "weekday_type": weekday_type,
                "source_channel": SOURCE_CHANNEL,
                "course_variant": course_variant,
                "slot_identity_key": slot_id_key,
                "slot_observation_key": make_slot_observation_key(slot_id_key, self.collected_at),
                "hash_key": make_hash(COURSE_NAME, self.collected_at, play_date_str, tee_time, course_sub),
                "slot_group_key": make_slot_key(COURSE_NAME, play_date_str, tee_time, course_sub),
                "listed_price_krw": nor_price,
                "normal_price_krw": nor_price,
                "sale_price_krw": display_price if promo_flag else None,
                "price_badge": promo_text,
            }
            rows.append(row)

        return rows
