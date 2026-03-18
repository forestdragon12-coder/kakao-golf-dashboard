"""
푸른솔장성 공식 홈페이지 스크래퍼 (purunsolgc.co.kr)

ASP.NET + AJAX 방식.
- 로그인: POST /_AJAX/member/services.asmx/Login
- 티타임: POST /_AJAX/reservation/services.asmx/GetGolfTimeList
- 응답: HTML 테이블 → 정규식 파싱
"""
import asyncio
import json
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
COURSE_NAME = "푸른솔장성"
DOMAIN = "https://www.purunsolgc.co.kr"
GOLF_GBN = "109"
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
    uid = os.getenv("PURUNSOL_ID", "")
    pw = os.getenv("PURUNSOL_PW", "")
    return {"id": uid, "pw": pw} if uid and pw else {}


class PurunsolScraper:

    def __init__(self):
        self.today = date.today()
        now = datetime.now()
        self.collected_date = self.today.isoformat()
        self.collected_at = now.strftime("%Y-%m-%dT%H:%M:00")
        self.creds = _load_creds()

    async def collect_course(self) -> list[dict]:
        if not self.creds:
            logger.warning(f"[{COURSE_NAME}] 로그인 정보 없음 (PURUNSOL_ID/PW)")
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

                # D+1 ~ D+30
                for d_offset in range(1, COLLECT_DAYS + 1):
                    play_date = self.today + timedelta(days=d_offset)
                    play_date_str = play_date.strftime("%Y%m%d")
                    rows = await self._get_tee_list(page, play_date_str)
                    all_rows.extend(rows)

                await browser.close()
        except Exception as e:
            logger.error(f"[{COURSE_NAME}] 수집 오류: {e}")

        logger.info(f"[{COURSE_NAME}] 수집 완료: {len(all_rows)}건")
        return all_rows

    async def _login(self, page) -> bool:
        try:
            await page.goto(f"{DOMAIN}/Booking/GolfCalendar.aspx", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1)

            result = await page.evaluate(f"""
                () => new Promise((resolve) => {{
                    $.ajax({{
                        type: "POST",
                        url: "/_AJAX/member/services.asmx/Login",
                        data: JSON.stringify({{ 'p_id': '{self.creds["id"]}', 'p_pwd': '{self.creds["pw"]}' }}),
                        contentType: "application/json; charset=utf-8",
                        dataType: "json",
                        success: function(r) {{ resolve(r.d); }},
                        error: function() {{ resolve('error'); }}
                    }});
                    setTimeout(() => resolve('timeout'), 10000);
                }})
            """)
            data = json.loads(result) if isinstance(result, str) else result
            if isinstance(data, dict) and data.get("code") == 0:
                logger.debug(f"[{COURSE_NAME}] 로그인 성공")
                await page.reload()
                await asyncio.sleep(1)
                return True

            logger.error(f"[{COURSE_NAME}] 로그인 실패: {result}")
            return False
        except Exception as e:
            logger.error(f"[{COURSE_NAME}] 로그인 오류: {e}")
            return False

    async def _get_tee_list(self, page, play_date_str: str) -> list[dict]:
        try:
            result = await page.evaluate(f"""
                () => new Promise((resolve) => {{
                    $.ajax({{
                        type: "POST",
                        url: "/_AJAX/reservation/services.asmx/GetGolfTimeList",
                        data: JSON.stringify({{ 'p_golfgbn': '{GOLF_GBN}', 'p_date': '{play_date_str}', 'p_cos': '', 'p_rtype': '' }}),
                        contentType: "application/json; charset=utf-8",
                        dataType: "json",
                        success: function(r) {{ resolve(r.d); }},
                        error: function() {{ resolve('error'); }}
                    }});
                    setTimeout(() => resolve('timeout'), 10000);
                }})
            """)

            if isinstance(result, str):
                data = json.loads(result)
            else:
                data = result

            if isinstance(data, dict):
                html_content = data.get("html", "")
                if html_content:
                    return self._parse_html(html_content, play_date_str)

            return []
        except Exception as e:
            logger.debug(f"[{COURSE_NAME}] {play_date_str} 오류: {e}")
            return []

    def _parse_html(self, html: str, play_date_str: str) -> list[dict]:
        """API 응답 HTML에서 티타임 추출"""
        play_date = date(int(play_date_str[:4]), int(play_date_str[4:6]), int(play_date_str[6:8]))
        d_day = (play_date - self.today).days
        weekday_type = get_weekday_type(play_date.weekday())
        season = get_season(play_date.month)

        rows = []
        # <tr> 단위로 파싱
        # 패턴: <td>06:30<br />(1부)</td><td>마운틴<br />(18홀)</td><td>가격</td>
        tr_re = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
        time_re = re.compile(r"(\d{1,2}:\d{2})<br\s*/?>.*?\((\d)부\)")
        course_re = re.compile(r"([가-힣a-zA-Z]+)<br\s*/?>.*?\((\d+)홀\)")
        price_re = re.compile(r"([\d,]+)원")
        promo_re = re.compile(r"특가")

        for tr_match in tr_re.finditer(html):
            tr = tr_match.group(1)
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
            if len(tds) < 3:
                continue

            # 시간
            tm = time_re.search(tds[0])
            if not tm:
                continue
            tee_time = tm.group(1)
            hour = int(tee_time.split(":")[0])
            if hour < 5 or hour > 19:
                continue
            part_type = get_part_type(hour)

            # 코스
            cm = course_re.search(tds[1])
            course_sub = cm.group(1) if cm else ""

            # 가격 + 특가
            promo_flag = 1 if promo_re.search(tds[2]) else 0
            pm = price_re.search(tds[2])
            if not pm:
                continue
            price_krw = int(pm.group(1).replace(",", ""))

            course_variant = normalize_course_variant(course_sub=course_sub or None)
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
                "course_sub": course_sub or None,
                "membership_type": "",
                "promo_flag": promo_flag,
                "promo_text": "특가" if promo_flag else None,
                "pax_condition": "4인",
                "price_type": "",
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
                "price_badge": "특가" if promo_flag else None,
            }
            rows.append(row)

        return rows
