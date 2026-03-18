import asyncio
import re
from datetime import date, timedelta, datetime
from loguru import logger
from playwright.async_api import Page

from config.courses import get_season, get_weekday_type, get_part_type
from db.database import (
    make_hash,
    make_slot_identity_key,
    make_slot_key,
    make_slot_observation_key,
    normalize_course_variant,
)

KAKAO_GOLF_URL = "https://www.kakao.golf"
COLLECT_DAYS = 30   # 오늘부터 D+1 ~ D+30
DATE_DELAY  = 1.5   # 날짜 클릭 간 딜레이 (초)
COURSE_DELAY = 3.0  # 골프장 간 딜레이 (초)
MAX_RETRY   = 2     # 실패 시 재시도 횟수

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class KakaoGolfScraper:

    def __init__(self):
        self.today = date.today()
        now = datetime.now()
        self.collected_date = self.today.isoformat()
        self.collected_at = now.strftime("%Y-%m-%dT%H:%M:00")  # 분 단위 (매 수집 고유)
        self.debug_courses = {"광주CC", "르오네뜨"}

    # ─────────────────────────────────────────
    # 1개 골프장 전체 수집
    # ─────────────────────────────────────────
    async def collect_course(
        self,
        page: Page,
        course_name: str,
        course_id: int,
        run_id: int,
    ) -> list[dict]:
        all_rows = []

        # ── 검색 → 골프장 진입
        ok = await self._search_and_enter(page, course_name)
        if not ok:
            logger.warning(f"[{course_name}] 골프장 진입 실패 - 스킵")
            return []

        # ── D+1 ~ D+30 날짜 순회
        target_dates = [
            self.today + timedelta(days=i) for i in range(1, COLLECT_DAYS + 1)
        ]

        for play_date in target_dates:
            for attempt in range(MAX_RETRY + 1):
                try:
                    rows = await self._collect_date(
                        page, course_name, course_id, run_id, play_date
                    )
                    all_rows.extend(rows)
                    logger.debug(
                        f"  [{course_name}] {play_date} → {len(rows)}개"
                    )
                    await asyncio.sleep(DATE_DELAY)
                    break
                except Exception as e:
                    if attempt < MAX_RETRY:
                        logger.warning(f"  [{course_name}] {play_date} 재시도 {attempt+1}: {e}")
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"  [{course_name}] {play_date} 실패: {e}")

        logger.info(f"[{course_name}] 완료 → 총 {len(all_rows)}개 티타임")
        return all_rows

    # ─────────────────────────────────────────
    # 검색 → 골프장 카드 클릭 → 티타임 리스트 진입
    # ─────────────────────────────────────────
    async def _search_and_enter(self, page: Page, course_name: str) -> bool:
        try:
            await page.goto(KAKAO_GOLF_URL, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1.5)

            # 검색창 찾기 (여러 셀렉터 시도)
            search_selectors = [
                'input[placeholder*="검색"]',
                'input[type="search"]',
                'input[placeholder*="골프장"]',
                '[class*="search"] input',
                '[class*="Search"] input',
                'input',
            ]
            search_input = None
            for sel in search_selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=3000)
                    if el:
                        search_input = el
                        break
                except Exception:
                    continue

            if not search_input:
                logger.error(f"[{course_name}] 검색창을 찾을 수 없음")
                return False

            # 검색어 입력
            await search_input.click()
            await asyncio.sleep(0.5)
            await search_input.fill(course_name)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)

            # 검색 결과에서 골프장 카드 클릭
            clicked = await self._click_course_card(page, course_name)
            if not clicked:
                return False

            await asyncio.sleep(2)
            if course_name in self.debug_courses:
                await self._dump_debug(page, course_name, "after_search_regression")
            return True

        except Exception as e:
            logger.error(f"[{course_name}] 검색 실패: {e}")
            return False

    # ─────────────────────────────────────────
    # 디버그: HTML + 텍스트 덤프
    # ─────────────────────────────────────────
    async def _dump_debug(self, page: Page, course_name: str, label: str):
        try:
            from pathlib import Path
            debug_dir = Path(__file__).parent.parent / "logs"
            debug_dir.mkdir(exist_ok=True)

            # 현재 URL
            url = page.url
            logger.info(f"  [DEBUG] 현재 URL: {url}")

            # body innerText (실제 보이는 텍스트)
            body_text = await page.evaluate("() => document.body?.innerText || ''")
            txt_path = debug_dir / f"debug_{course_name}_{label}.txt"
            txt_path.write_text(body_text, encoding="utf-8")
            logger.info(f"  [DEBUG] 텍스트 저장: {txt_path.name}")

            # 스크린샷
            shot_path = debug_dir / f"debug_{course_name}_{label}.png"
            await page.screenshot(path=str(shot_path))
            logger.info(f"  [DEBUG] 스크린샷 저장: {shot_path.name}")
        except Exception as e:
            logger.debug(f"  [DEBUG] 덤프 실패: {e}")

    # ─────────────────────────────────────────
    # 검색 결과 카드 클릭
    # ─────────────────────────────────────────
    async def _click_course_card(self, page: Page, course_name: str) -> bool:
        import json

        # 검색어 변형: "광주CC" → ["광주", "광주CC"]
        name_variants = self._build_course_name_variants(course_name)

        variants_js = json.dumps(name_variants, ensure_ascii=False)

        # ── 1순위: JS로 요소 좌표 찾기 → mouse.click (React SPA에서 가장 신뢰성 높음)
        try:
            rect = await page.evaluate(f"""
                () => {{
                    const variants = {variants_js};
                    const containers = document.querySelectorAll(
                        'a[href], li, [role="listitem"], ' +
                        '[class*="item"], [class*="card"], [class*="course"]'
                    );
                    for (const el of containers) {{
                        const text = (el.innerText || el.textContent || '').trim();
                        const firstLine = text.split('\\n')
                            .map(l => l.trim())
                            .filter(l => l.length > 0)[0] || '';
                        for (const v of variants) {{
                            if (firstLine === v) {{
                                const r = (el.closest('a') || el).getBoundingClientRect();
                                return {{
                                    x: r.left + r.width / 2,
                                    y: r.top + r.height / 2,
                                    found: firstLine
                                }};
                            }}
                        }}
                    }}
                    return null;
                }}
            """)
            if rect and rect.get('x') and rect.get('y'):
                await page.mouse.click(rect['x'], rect['y'])
                logger.debug(f"  [{course_name}] 좌표 클릭 성공: '{rect['found']}' ({rect['x']:.0f}, {rect['y']:.0f})")
                return True
        except Exception as e:
            logger.debug(f"  좌표 클릭 오류: {e}")

        # ── 2순위: Playwright locator → scroll + click
        for name in name_variants:
            try:
                locator = page.get_by_text(name, exact=True).first
                await locator.scroll_into_view_if_needed(timeout=3000)
                await locator.click(timeout=3000)
                logger.debug(f"  [{course_name}] locator 클릭 성공: '{name}'")
                return True
            except Exception as e:
                logger.debug(f"  [{course_name}] locator 클릭 실패 '{name}': {e}")
                continue

        logger.warning(f"[{course_name}] 카드 클릭 실패 (시도 이름: {name_variants})")
        return False

    # ─────────────────────────────────────────
    # 특정 날짜 클릭 → 티타임 파싱
    # ─────────────────────────────────────────
    async def _collect_date(
        self,
        page: Page,
        course_name: str,
        course_id: int,
        run_id: int,
        play_date: date,
    ) -> list[dict]:

        # 날짜 클릭
        clicked = await self._click_date(page, play_date)
        if not clicked:
            return []

        # 날짜 전환 반영 대기
        await asyncio.sleep(1.5)

        # 티타임 파싱
        tee_items = await self._parse_tee_times(page)
        if course_name in self.debug_courses and play_date == (self.today + timedelta(days=1)):
            await self._dump_debug(page, course_name, "teetimes_page_regression")

        return self._build_rows(tee_items, course_name, course_id, run_id, play_date)

    # ─────────────────────────────────────────
    # 파싱된 아이템 → DB row dict 빌드 (공용)
    # ─────────────────────────────────────────
    def _build_rows(
        self,
        tee_items: list[dict],
        course_name: str,
        course_id: int,
        run_id: int,
        play_date: date,
    ) -> list[dict]:
        rows = []
        d_day = (play_date - self.today).days
        for item in tee_items:
            hour = int(item["tee_time"].split(":")[0])
            cs = item.get("course_sub") or ""
            part_type = get_part_type(hour)
            source_channel = "kakao_mobile"
            course_variant = normalize_course_variant(
                course_sub=cs or None,
                membership_type=item.get("membership_type"),
                price_type=item.get("price_type"),
            )
            slot_identity_key = make_slot_identity_key(
                course_id,
                play_date.isoformat(),
                item["tee_time"],
                part_type,
                course_variant,
                source_channel,
            )
            row = {
                "crawl_run_id":    run_id,
                "course_id":       course_id,
                "course_name":     course_name,
                "collected_date":  self.collected_date,
                "collected_at":    self.collected_at,
                "play_date":       play_date.isoformat(),
                "tee_time":        item["tee_time"],
                "price_krw":       item.get("price_krw"),
                "course_sub":      cs or None,
                "membership_type": item.get("membership_type"),
                "promo_flag":      item.get("promo_flag", 0),
                "promo_text":      item.get("promo_text"),
                "pax_condition":   item.get("pax_condition"),
                "price_type":      item.get("price_type"),
                "d_day":           d_day,
                "part_type":       part_type,
                "season":          get_season(play_date.month),
                "weekday_type":    get_weekday_type(play_date.weekday()),
                "source_channel":  source_channel,
                "course_variant":  course_variant,
                "slot_identity_key": slot_identity_key,
                "slot_identity_version": 1,
                "slot_observation_key": make_slot_observation_key(slot_identity_key, self.collected_at),
                "slot_status":     "available",
                "status_reason":   "observed_in_listing",
                "visible_flag":    1,
                "inventory_observed_flag": 1,
                "listed_price_krw": item.get("listed_price_krw") or item.get("price_krw"),
                "normal_price_krw": item.get("normal_price_krw"),
                "sale_price_krw":  item.get("sale_price_krw") or item.get("price_krw"),
                "price_badge":     item.get("promo_text"),
                "previous_price_krw": None,
                "price_changed_flag": 0,
                "price_change_delta_krw": None,
                "price_change_delta_pct": None,
                "price_change_count_7d": 0,
                "first_discount_dday": d_day if item.get("promo_flag", 0) else None,
                "hash_key": make_hash(
                    course_name, self.collected_at,
                    play_date.isoformat(), item["tee_time"], cs
                ),
                "slot_group_key": make_slot_key(
                    course_name, play_date.isoformat(),
                    item["tee_time"], cs
                ),
            }
            rows.append(row)
        return rows

    # ─────────────────────────────────────────
    # 날짜 탭 클릭
    # 날짜 바 형식: 일반일 → "14", 매월 1일 → "4/1", "5/1"
    # ─────────────────────────────────────────
    async def _click_date(self, page: Page, play_date: date) -> bool:
        # 매월 1일은 "M/1" 형식으로 표시됨
        if play_date.day == 1:
            date_text = f"{play_date.month}/1"
        else:
            date_text = str(play_date.day)

        # JS로 좌표 찾기 → mouse.click (React SPA 대응)
        import json
        dt_js = json.dumps(date_text)
        try:
            rect = await page.evaluate(f"""
                () => {{
                    const target = {dt_js};
                    const els = document.querySelectorAll(
                        '[class*="date"], [class*="day"], [class*="Date"], [class*="Day"], ' +
                        'td, th, li, span, button'
                    );
                    for (const el of els) {{
                        if (el.textContent.trim() === target) {{
                            const r = el.getBoundingClientRect();
                            if (r.width > 0) {{
                                return {{x: r.left + r.width/2, y: r.top + r.height/2}};
                            }}
                        }}
                    }}
                    return null;
                }}
            """)
            if rect:
                await page.mouse.click(rect['x'], rect['y'])
                return True
        except Exception as e:
            logger.debug(f"  날짜 클릭 오류: {e}")

        # Playwright locator fallback
        try:
            el = page.get_by_text(date_text, exact=True).first
            await el.scroll_into_view_if_needed(timeout=2000)
            await el.click(timeout=2000)
            return True
        except Exception as e:
            logger.debug(f"  locator 날짜 클릭 실패 {date_text}: {e}")

        logger.warning(f"날짜 클릭 실패: {date_text} ({play_date})")
        return False

    # ─────────────────────────────────────────
    # 티타임 파싱 (블록 기반)
    # 실제 페이지 구조:
    #   06:54       ← 시간 (단독 줄)
    #   75,000원    ← 가격 (단독 줄)
    #   특가        ← 프로모 태그 (optional)
    #   동악        ← 코스명 (optional, 한글 2-5자)
    #   18홀        ← 홀 수
    #   4인 필수    ← 인원 조건
    # ─────────────────────────────────────────
    async def _parse_tee_times(self, page: Page) -> list[dict]:
        try:
            body_text = await page.evaluate("() => document.body?.innerText || ''")
            if "잔여 티타임이 없어요" in body_text or "티타임이 없습니다" in body_text:
                return []
            return self._parse_blocks(body_text)
        except Exception as e:
            logger.debug(f"티타임 파싱 오류: {e}")
            return []

    def _parse_blocks(self, body_text: str) -> list[dict]:
        # ── 정규식 ──────────────────────────────────────────────────
        time_re   = re.compile(r'^(\d{1,2}):(\d{2})$')
        price_re  = re.compile(r'^([\d,]+)원$')
        hole_re   = re.compile(r'^\d+홀$')
        pax_re    = re.compile(r'^(\d인.+)$')
        # "밸리(대중제)", "힐(대중제)", "골드(회원제)", "동악", "Sky", "Lake", "OUT" 등
        # 한글·영문 코스명 모두 허용 (베르힐=Sky/Lake, 르오네뜨=OUT)
        course_re = re.compile(r'^[가-힣a-zA-Z]{1,10}(?:\([가-힣/]+\))?$')
        member_re = re.compile(r'\((대중제|회원제)\)')

        # ── 상수 ────────────────────────────────────────────────────
        SECTION_HEADERS = {
            '새벽 5-7시', '오전 7-12시', '오후 12-4시',
            '날짜 선택', '날짜 선택 완료',
        }
        PROMO_KW = {'특가', '할인', '%'}
        # '카트비'를 포함하는 모든 변형 대응:
        #   '카트비별도', '카트비 별도', '(특가)+카트비 및 기본요금(24,500원)별도' 등
        # '그린피' 단독 / '카카오골프특가' 등은 별도 처리
        PRICE_TYPE_KW = {'그린피', '카트비', '캐디피', '캐디비'}
        # 아래는 가격 유형이 아닌 예약 조건 → price_type 저장 제외
        CONDITION_KW  = {'회원가입', '회원 가입'}
        SKIP_WORDS  = {
            '환급할인', '조인모집가능', '모든티타임',
            '멤버십특가', '앱 열기',
        }

        lines = [l.strip() for l in body_text.split('\n')]
        items = []
        i = 0

        while i < len(lines):
            line = lines[i]
            tm = time_re.match(line)
            if tm:
                hour, minute = int(tm.group(1)), tm.group(2)
                if 5 <= hour <= 19:
                    tee_time        = f"{hour:02d}:{minute}"
                    price_krw       = None
                    course_sub      = None
                    membership_type = None
                    promo_flag      = 0
                    promo_text      = None
                    pax_condition   = None
                    price_type      = None

                    j = i + 1
                    while j < min(i + 14, len(lines)):
                        l = lines[j]

                        # 다음 티타임 / 섹션 헤더 → 블록 종료
                        if time_re.match(l) or l in SECTION_HEADERS:
                            break
                        if not l or l in SKIP_WORDS:
                            j += 1
                            continue

                        # ① 가격 "80,000원"
                        pm = price_re.match(l)
                        if pm and price_krw is None:
                            price_krw = int(pm.group(1).replace(",", ""))
                            j += 1
                            continue

                        # ② 가격 유형: "그린피" / "카트비별도" / "(특가)+카트비 및 기본요금별도" 등
                        #    → 프로모 체크보다 먼저: 카트비 관련 문구가 PROMO_KW에도 걸리기 때문
                        #    단, "회원가입 필수" 등 예약 조건 문구는 price_type이 아님 → 제외
                        if price_type is None:
                            has_price_kw = any(pt in l for pt in PRICE_TYPE_KW)
                            has_cond_kw  = any(ck in l for ck in CONDITION_KW)
                            if has_price_kw and not has_cond_kw:
                                price_type = l
                                j += 1
                                continue

                        # ③ 프로모 태그 "특가" (가격 확인 후, course_sub 전에 등장)
                        if price_krw is not None and course_sub is None:
                            if any(kw in l for kw in PROMO_KW):
                                promo_flag = 1
                                promo_text = l
                                j += 1
                                continue

                        # ④ 홀 수 (스킵)
                        if hole_re.match(l):
                            j += 1
                            continue

                        # ⑤ 인원 조건 "4인 필수" / "3인 이상"
                        pm2 = pax_re.match(l)
                        if pm2 and pax_condition is None:
                            pax_condition = pm2.group(1)
                            j += 1
                            continue

                        # ⑥ 코스명 "밸리(대중제)" / "힐(대중제)" / "레이크(회원제)"
                        if course_sub is None and price_krw is not None:
                            if course_re.match(l):
                                course_sub = l
                                m = member_re.search(l)
                                if m:
                                    membership_type = m.group(1)
                                j += 1
                                continue

                        j += 1

                    items.append({
                        "tee_time":        tee_time,
                        "price_krw":       price_krw,
                        "course_sub":      course_sub,
                        "membership_type": membership_type,
                        "promo_flag":      promo_flag,
                        "promo_text":      promo_text,
                        "pax_condition":   pax_condition,
                        "price_type":      price_type,
                    })
            i += 1

        logger.debug(f"  블록 파싱 결과: {len(items)}개")
        return items

    def _build_course_name_variants(self, course_name: str) -> list[str]:
        variants = []
        stripped = course_name.replace("CC", "").replace("cc", "").replace("GC", "").strip()
        if stripped and stripped != course_name:
            variants.append(stripped)
        variants.append(course_name)
        return variants
