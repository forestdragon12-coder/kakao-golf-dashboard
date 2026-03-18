"""
카카오골프 API 응답 가로채기 스크래퍼

기존 DOM 텍스트 파싱 대신 Playwright response 이벤트로
/api/golf/booktime 응답 JSON을 직접 캡처한다.
API 가로채기 실패 시 기존 DOM 파싱으로 자동 폴백.

사용법:
    python run.py --scraper api
"""
import asyncio
import json
import re
from datetime import date, timedelta
from pathlib import Path
from loguru import logger
from playwright.async_api import Page, Response

from scraper.kakao_scraper import KakaoGolfScraper

# API 응답 URL 매칭 패턴
BOOKTIME_URL_PATTERN = "booktime"

RAW_DIR = Path(__file__).parent.parent / "raw" / "api_responses"

_MEMBER_RE = re.compile(r"\((대중제|회원제)\)")


class KakaoApiScraper(KakaoGolfScraper):
    """API 응답 가로채기 스크래퍼.

    부모의 검색/날짜클릭/날짜루프/_build_rows를 그대로 쓰고,
    _collect_date만 오버라이드하여 데이터 추출 방식을 교체.
    API 실패 시 부모의 DOM 파싱으로 자동 폴백 → 기존 대비 데이터 손실 없음.
    """

    def __init__(self):
        super().__init__()
        self._api_buffer: list[dict] = []
        self._raw_response: dict | None = None
        self._listener_installed: bool = False
        self._api_success_count: int = 0
        self._dom_fallback_count: int = 0

    # ─────────────────────────────────────────
    # collect_course: 리스너 설치 후 부모 로직 위임
    # ─────────────────────────────────────────
    async def collect_course(
        self,
        page: Page,
        course_name: str,
        course_id: int,
        run_id: int,
    ) -> list[dict]:
        self._api_success_count = 0
        self._dom_fallback_count = 0

        async def on_response(response: Response):
            await self._handle_api_response(response)

        page.on("response", on_response)
        self._listener_installed = True

        try:
            rows = await super().collect_course(page, course_name, course_id, run_id)
        finally:
            page.remove_listener("response", on_response)
            self._listener_installed = False

        total = self._api_success_count + self._dom_fallback_count
        if total > 0:
            logger.info(
                f"[{course_name}] 수집 방식: API {self._api_success_count}일 / "
                f"DOM폴백 {self._dom_fallback_count}일"
            )

        return rows

    # ─────────────────────────────────────────
    # _collect_date 오버라이드: API 우선, DOM 폴백
    # ─────────────────────────────────────────
    async def _collect_date(
        self,
        page: Page,
        course_name: str,
        course_id: int,
        run_id: int,
        play_date: date,
    ) -> list[dict]:
        # 버퍼 초기화
        self._api_buffer = []
        self._raw_response = None

        # 날짜 클릭
        clicked = await self._click_date(page, play_date)
        if not clicked:
            return []

        # API 응답 대기
        try:
            await page.wait_for_response(
                lambda r: BOOKTIME_URL_PATTERN in r.url and r.status == 200,
                timeout=8000,
            )
        except Exception:
            pass

        # 응답 처리 완료 대기
        await asyncio.sleep(0.5)

        # ── API 성공: 구조화된 데이터 사용
        if self._api_buffer:
            self._api_success_count += 1
            self._save_raw(course_name, play_date)

            is_earlybird = False
            if self._raw_response:
                is_earlybird = bool(self._raw_response.get("earlybird", False))

            tee_items = []
            for item in self._api_buffer:
                parsed = self._transform_api_item(item, is_earlybird)
                if parsed:
                    tee_items.append(parsed)

            # 부모의 _build_rows 호출 → row dict 형식 완전 동일
            return self._build_rows(tee_items, course_name, course_id, run_id, play_date)

        # ── API 실패: DOM 파싱 폴백 (날짜는 이미 클릭됨)
        self._dom_fallback_count += 1
        logger.debug(f"  [{course_name}] {play_date} API 응답 없음 → DOM 폴백")

        await asyncio.sleep(1.0)
        tee_items = await self._parse_tee_times(page)

        if course_name in self.debug_courses and play_date == (self.today + timedelta(days=1)):
            await self._dump_debug(page, course_name, "teetimes_api_fallback")

        return self._build_rows(tee_items, course_name, course_id, run_id, play_date)

    # ─────────────────────────────────────────
    # API 응답 핸들러
    # ─────────────────────────────────────────
    async def _handle_api_response(self, response: Response):
        if BOOKTIME_URL_PATTERN not in response.url:
            return
        if response.status != 200:
            return

        try:
            body = await response.json()
            if isinstance(body, dict) and "list" in body:
                self._raw_response = body
                items = body.get("list") or []
                self._api_buffer.extend(items)
            elif isinstance(body, list):
                self._api_buffer.extend(body)
                self._raw_response = {"list": body}
        except Exception as e:
            logger.debug(f"  [API] JSON 파싱 실패: {e}")

    # ─────────────────────────────────────────
    # API JSON → 파싱 아이템 변환
    # 출력 형식은 _parse_blocks()와 동일:
    #   tee_time, price_krw, course_sub, membership_type,
    #   promo_flag, promo_text, pax_condition, price_type,
    #   listed_price_krw, normal_price_krw, sale_price_krw
    # ─────────────────────────────────────────
    @staticmethod
    def _transform_api_item(item: dict, is_earlybird: bool = False) -> dict | None:
        book_time = item.get("bookTime")
        if not book_time or len(str(book_time)) < 3:
            return None

        # "1205" → "12:05"
        bt = str(book_time).zfill(4)
        tee_time = f"{bt[:2]}:{bt[2:]}"

        hour = int(bt[:2])
        if hour < 5 or hour > 19:
            return None

        # ── 가격 ──
        green_fee_dc = item.get("greenFeeDC")   # 실결제가 (int)
        green_fee_dp = item.get("greenFeeDP")   # 표시정상가 (str)

        price_krw = green_fee_dc
        listed_price = None
        normal_price = None
        sale_price = green_fee_dc

        if green_fee_dp:
            try:
                listed_price = int(green_fee_dp)
                if listed_price != green_fee_dc and listed_price > 0:
                    normal_price = listed_price
            except (ValueError, TypeError):
                pass

        if listed_price is None:
            listed_price = green_fee_dc

        # ── 코스 서브 ──
        course_sub = item.get("CourseName")

        # ── 회원제/대중제 ──
        membership_type = None
        if course_sub:
            m = _MEMBER_RE.search(course_sub)
            if m:
                membership_type = m.group(1)

        # ── 프로모 ──
        promo_flag = 0
        promo_text = None
        badge_list = item.get("badgeList") or []
        is_low = item.get("isLowGuarantee", 0)

        if is_low:
            promo_flag = 1
            promo_text = "임박특가"
        if badge_list:
            promo_flag = 1
            badge_names = []
            for b in badge_list:
                if isinstance(b, dict):
                    badge_names.append(b.get("name", str(b)))
                else:
                    badge_names.append(str(b))
            if badge_names:
                promo_text = ",".join(badge_names)
        if is_earlybird:
            promo_flag = 1
            if not promo_text:
                promo_text = "얼리버드"

        sale_fee = item.get("saleFee", 0)
        if sale_fee and sale_fee > 0 and not promo_flag:
            promo_flag = 1
            if not promo_text:
                promo_text = "특가"

        # ── 인원 조건 ──
        visitor_cnt = item.get("visitorCnt")
        max_visitor_cnt = item.get("maxVisitorCnt")
        pax_condition = None
        if visitor_cnt and max_visitor_cnt:
            if visitor_cnt >= max_visitor_cnt:
                pax_condition = f"{visitor_cnt}인 필수"
            else:
                pax_condition = f"{visitor_cnt}인 이상"

        # ── 가격 유형 ──
        # DOM 파서의 필터와 동일: PRICE_TYPE_KW 포함 + CONDITION_KW 미포함 시만 저장.
        # bookName이 "(전원)골프장 회원가입 필수" 같은 예약 조건이면 None 처리.
        price_type = None
        book_name = item.get("bookName") or ""
        _PRICE_KW = {"그린피", "카트비", "캐디피", "캐디비"}
        _COND_KW = {"회원가입", "회원 가입"}
        if any(pk in book_name for pk in _PRICE_KW) and not any(ck in book_name for ck in _COND_KW):
            price_type = book_name

        return {
            "tee_time": tee_time,
            "price_krw": price_krw,
            "course_sub": course_sub,
            "membership_type": membership_type,
            "promo_flag": promo_flag,
            "promo_text": promo_text,
            "pax_condition": pax_condition,
            "price_type": price_type,
            "listed_price_krw": listed_price,
            "normal_price_krw": normal_price,
            "sale_price_krw": sale_price,
        }

    # ─────────────────────────────────────────
    # 원본 JSON 저장
    # ─────────────────────────────────────────
    def _save_raw(self, course_name: str, play_date: date):
        data = self._raw_response or {"list": self._api_buffer}
        try:
            out_dir = RAW_DIR / self.collected_date
            out_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{course_name}_{play_date.strftime('%Y%m%d')}.json"
            filepath = out_dir / filename

            record = {
                "_meta": {
                    "collectedAt": self.collected_date,
                    "courseName": course_name,
                    "playDate": play_date.isoformat(),
                    "teetimeCount": len(data.get("list") or []),
                },
                "data": data,
            }
            filepath.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.debug(f"  [RAW] 원본 저장 실패: {e}")
