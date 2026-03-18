"""
해피니스CC 공식 홈페이지 스크래퍼 (happinesscc.com)

SSR 방식 — Date_Click(year, month, day) → HTML 파싱.
광주CC와 유사 구조, 이벤트(특가) 컬럼 추가.
"""
import asyncio
import os
import re
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
COURSE_NAME = "해피니스"
DOMAIN = "https://www.happinesscc.com"
COURSE_SUBS = {"하트", "히든", "힐링", "해피", "휴먼"}


def _load_creds() -> dict:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    uid = os.getenv("HAPPINESS_ID", "")
    pw = os.getenv("HAPPINESS_PW", "")
    return {"id": uid, "pw": pw} if uid and pw else {}


class HappinessScraper:

    def __init__(self):
        self.today = date.today()
        now = datetime.now()
        self.collected_date = self.today.isoformat()
        self.collected_at = now.strftime("%Y-%m-%dT%H:%M:00")
        self.creds = _load_creds()

    async def collect_course(self) -> list[dict]:
        if not self.creds:
            logger.warning(f"[{COURSE_NAME}] 로그인 정보 없음 (HAPPINESS_ID/PW)")
            return []

        all_rows = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = await browser.new_page()
                async def handle_dialog(d):
                    await d.accept()
                page.on("dialog", handle_dialog)

                ok = await self._login(page)
                if not ok:
                    await browser.close()
                    return []

                await page.goto(f"{DOMAIN}/html/reserve/reserve01.asp", wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)

                avail_dates = await self._get_available_dates(page)
                logger.info(f"[{COURSE_NAME}] 예약 가능 {len(avail_dates)}일")

                for play_date_str in avail_dates:
                    rows = await self._get_tee_list(page, play_date_str)
                    all_rows.extend(rows)
                    await asyncio.sleep(0.5)

                await browser.close()
        except Exception as e:
            logger.error(f"[{COURSE_NAME}] 수집 오류: {e}")

        logger.info(f"[{COURSE_NAME}] 수집 완료: {len(all_rows)}건")
        return all_rows

    async def _login(self, page) -> bool:
        try:
            await page.goto(f"{DOMAIN}/html/member/login.asp", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1)
            await page.locator('input[name="memb_inet_no"]').first.fill(self.creds["id"])
            await page.locator('input[name="memb_inet_pass"]').first.fill(self.creds["pw"])
            await page.evaluate("Login_Check()")
            await asyncio.sleep(2)

            if "login" in page.url.lower() and "login_ok" not in page.url.lower():
                logger.error(f"[{COURSE_NAME}] 로그인 실패")
                return False
            logger.debug(f"[{COURSE_NAME}] 로그인 성공")
            return True
        except Exception as e:
            logger.error(f"[{COURSE_NAME}] 로그인 오류: {e}")
            return False

    async def _get_available_dates(self, page) -> list[str]:
        html = await page.content()
        pattern = re.compile(r"Date_Click\('(\d{4})','(\d{2})','(\d{2})'\)")
        dates = []
        today_str = self.today.strftime("%Y%m%d")
        for m in pattern.finditer(html):
            ds = f"{m.group(1)}{m.group(2)}{m.group(3)}"
            if ds > today_str:
                dates.append(ds)
        return dates

    async def _get_tee_list(self, page, play_date_str: str) -> list[dict]:
        y, m, d = play_date_str[:4], play_date_str[4:6], play_date_str[6:8]
        try:
            await page.evaluate(f"Date_Click('{y}','{m}','{d}')")
            await asyncio.sleep(2)
            text = await page.evaluate("() => document.body?.innerText || ''")
            return self._parse_tee_times(text, play_date_str)
        except Exception as e:
            logger.debug(f"[{COURSE_NAME}] {play_date_str} 오류: {e}")
            return []

    def _parse_tee_times(self, text: str, play_date_str: str) -> list[dict]:
        play_date = date(int(play_date_str[:4]), int(play_date_str[4:6]), int(play_date_str[6:8]))
        d_day = (play_date - self.today).days
        weekday_type = get_weekday_type(play_date.weekday())
        season = get_season(play_date.month)

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        rows = []
        time_re = re.compile(r"^(\d{1,2}):(\d{2})$")
        price_re = re.compile(r"^([\d,]+)$")

        i = 0
        while i < len(lines):
            line = lines[i]

            # 데이터 행: 코스명이 COURSE_SUBS에 포함
            if line in COURSE_SUBS and i + 3 < len(lines):
                course_sub = line
                next1 = lines[i + 1]  # "18"

                # 홀 수 확인
                if next1.isdigit():
                    # 시간 찾기
                    time_idx = i + 2
                    promo_flag = 0
                    promo_text = None

                    tm = time_re.match(lines[time_idx])
                    if tm:
                        tee_time_str = lines[time_idx]
                        # 다음: 이벤트(특가) 또는 가격
                        price_idx = time_idx + 1
                        if price_idx < len(lines) and lines[price_idx] == "특가":
                            promo_flag = 1
                            promo_text = "특가"
                            price_idx += 1

                        if price_idx < len(lines):
                            price_str = lines[price_idx].replace(",", "")
                            if price_re.match(price_str):
                                hour = int(tm.group(1))
                                if 5 <= hour <= 19:
                                    tee_time = f"{hour:02d}:{tm.group(2)}"
                                    price_krw = int(price_str)
                                    part_type = get_part_type(hour)
                                    course_variant = normalize_course_variant(course_sub=course_sub)
                                    slot_id_key = make_slot_identity_key(
                                        0, play_date.isoformat(), tee_time, part_type, course_variant, SOURCE_CHANNEL
                                    )
                                    row = {
                                        "course_name": COURSE_NAME,
                                        "collected_date": self.collected_date,
                                        "collected_at": self.collected_at,
                                        "play_date": play_date.isoformat(),
                                        "tee_time": tee_time,
                                        "price_krw": price_krw,
                                        "course_sub": course_sub,
                                        "membership_type": "회원제" if course_sub in ("해피", "휴먼") else "대중제",
                                        "promo_flag": promo_flag,
                                        "promo_text": promo_text,
                                        "pax_condition": "4인",
                                        "price_type": "비회원",
                                        "d_day": d_day,
                                        "part_type": part_type,
                                        "season": season,
                                        "weekday_type": weekday_type,
                                        "source_channel": SOURCE_CHANNEL,
                                        "course_variant": course_variant,
                                        "slot_identity_key": slot_id_key,
                                        "slot_observation_key": make_slot_observation_key(slot_id_key, self.collected_at),
                                        "hash_key": make_hash(COURSE_NAME, self.collected_at, play_date.isoformat(), tee_time, course_sub),
                                        "slot_group_key": make_slot_key(COURSE_NAME, play_date.isoformat(), tee_time, course_sub),
                                        "listed_price_krw": price_krw,
                                        "normal_price_krw": price_krw,
                                        "sale_price_krw": price_krw if promo_flag else None,
                                        "price_badge": promo_text,
                                    }
                                    rows.append(row)

                                    # "예약" 줄 스킵
                                    i = price_idx + 2
                                    continue

            i += 1

        return rows
