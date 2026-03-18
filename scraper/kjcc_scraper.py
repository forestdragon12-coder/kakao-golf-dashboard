"""
광주CC 공식 홈페이지 스크래퍼 (kjcc.co.kr)

서버 렌더링(SSR) 방식 — API가 아니라 form submit → HTML 파싱.
Playwright로 로그인 후 날짜별 페이지를 순회하며 티타임 추출.
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
COURSE_NAME = "광주CC"
DOMAIN = "https://www.kjcc.co.kr"
COLLECT_DAYS = 30


def _load_creds() -> dict:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    uid = os.getenv("KJCC_ID", "")
    pw = os.getenv("KJCC_PW", "")
    return {"id": uid, "pw": pw} if uid and pw else {}


class KjccScraper:
    """광주CC 공식 홈페이지 스크래퍼"""

    def __init__(self):
        self.today = date.today()
        now = datetime.now()
        self.collected_date = self.today.isoformat()
        self.collected_at = now.strftime("%Y-%m-%dT%H:%M:00")
        self.creds = _load_creds()

    async def collect_course(self) -> list[dict]:
        if not self.creds:
            logger.warning(f"[{COURSE_NAME}] 로그인 정보 없음 (KJCC_ID/KJCC_PW)")
            return []

        all_rows = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True, args=["--no-sandbox"]
                )
                page = await browser.new_page()
                async def handle_dialog(d):
                    await d.accept()
                page.on("dialog", handle_dialog)

                # 로그인
                ok = await self._login(page)
                if not ok:
                    await browser.close()
                    return []

                # 예약 페이지
                await page.goto(
                    f"{DOMAIN}/html/reserve/reserve01.asp",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await asyncio.sleep(2)

                # 캘린더에서 잔여팀 > 0인 날짜 추출
                avail_dates = await self._get_available_dates(page)
                logger.info(f"[{COURSE_NAME}] 예약 가능 {len(avail_dates)}일")

                # 각 날짜별 클릭 → HTML 파싱
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
            await page.goto(
                f"{DOMAIN}/html/member/login.asp",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await asyncio.sleep(1)
            await page.locator("#loginId").click()
            await page.keyboard.type(self.creds["id"], delay=30)
            await page.locator("#loginPw").click()
            await page.keyboard.type(self.creds["pw"], delay=30)
            await page.evaluate("Login1()")
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
        """캘린더 HTML에서 잔여팀 > 0인 날짜 추출"""
        html = await page.content()
        # Date_Click('2026','03','23','*') 패턴 + 잔여 텍스트
        pattern = re.compile(
            r"Date_Click\('(\d{4})','(\d{2})','(\d{2})','[^']*'\)"
        )
        dates = []
        today_str = self.today.strftime("%Y%m%d")

        for m in pattern.finditer(html):
            y, mo, d = m.group(1), m.group(2), m.group(3)
            ds = f"{y}{mo}{d}"
            if ds > today_str:
                dates.append(ds)

        return dates

    async def _get_tee_list(self, page, play_date_str: str) -> list[dict]:
        """날짜 클릭 → HTML에서 티타임 파싱"""
        y = play_date_str[:4]
        m = play_date_str[4:6]
        d = play_date_str[6:8]

        try:
            await page.evaluate(f"Date_Click('{y}','{m}','{d}','*')")
            await asyncio.sleep(2)

            text = await page.evaluate("() => document.body?.innerText || ''")
            return self._parse_tee_times(text, play_date_str)
        except Exception as e:
            logger.debug(f"[{COURSE_NAME}] {play_date_str} 오류: {e}")
            return []

    def _parse_tee_times(self, text: str, play_date_str: str) -> list[dict]:
        """HTML innerText에서 티타임 블록 파싱"""
        play_date = date(
            int(play_date_str[:4]),
            int(play_date_str[4:6]),
            int(play_date_str[6:8]),
        )
        d_day = (play_date - self.today).days
        weekday_type = get_weekday_type(play_date.weekday())
        season = get_season(play_date.month)

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        rows = []
        current_course = None
        time_re = re.compile(r"^(\d{1,2}):(\d{2})$")
        price_re = re.compile(r"^([\d,]+)$")

        i = 0
        while i < len(lines):
            line = lines[i]

            # 코스 헤더: "동악 (동악 → 섬진)" — 괄호 포함만 헤더
            if any(line.startswith(c) for c in ("동악 (", "섬진 (", "설산 (")):
                current_course = line.split("(")[0].strip()
                i += 1
                continue

            # 테이블 헤더 스킵
            if line in ("코스", "홀", "시간", "비회원", "예약"):
                i += 1
                continue

            # 코스명 줄 (데이터 행의 시작)
            if current_course and line in ("동악", "섬진", "설산"):
                course_sub = line
                # 다음: 홀 → 시간 → 가격
                if i + 3 < len(lines):
                    holes = lines[i + 1]  # "18홀"
                    time_str = lines[i + 2]  # "06:54"
                    price_str = lines[i + 3]  # "75,000"

                    tm = time_re.match(time_str)
                    pm = price_re.match(price_str.replace(",", ""))

                    if tm and pm:
                        hour = int(tm.group(1))
                        if 5 <= hour <= 19:
                            tee_time = f"{hour:02d}:{tm.group(2)}"
                            price_krw = int(pm.group(1))
                            part_type = get_part_type(hour)
                            course_variant = normalize_course_variant(
                                course_sub=course_sub
                            )
                            slot_id_key = make_slot_identity_key(
                                0,
                                play_date.isoformat(),
                                tee_time,
                                part_type,
                                course_variant,
                                SOURCE_CHANNEL,
                            )
                            row = {
                                "course_name": COURSE_NAME,
                                "collected_date": self.collected_date,
                                "collected_at": self.collected_at,
                                "play_date": play_date.isoformat(),
                                "tee_time": tee_time,
                                "price_krw": price_krw,
                                "course_sub": course_sub,
                                "membership_type": "",
                                "promo_flag": 0,
                                "promo_text": None,
                                "pax_condition": "4인",
                                "price_type": "비회원",
                                "d_day": d_day,
                                "part_type": part_type,
                                "season": season,
                                "weekday_type": weekday_type,
                                "source_channel": SOURCE_CHANNEL,
                                "course_variant": course_variant,
                                "slot_identity_key": slot_id_key,
                                "slot_observation_key": make_slot_observation_key(
                                    slot_id_key, self.collected_at
                                ),
                                "hash_key": make_hash(
                                    COURSE_NAME,
                                    self.collected_at,
                                    play_date.isoformat(),
                                    tee_time,
                                    course_sub,
                                ),
                                "slot_group_key": make_slot_key(
                                    COURSE_NAME,
                                    play_date.isoformat(),
                                    tee_time,
                                    course_sub,
                                ),
                                "listed_price_krw": price_krw,
                                "normal_price_krw": price_krw,
                                "sale_price_krw": None,
                                "price_badge": None,
                            }
                            rows.append(row)

                    i += 4
                    continue

            i += 1

        return rows
