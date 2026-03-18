"""
골프장 데이터 소스 자동 탐색 엔진

골프장 이름을 받아 카카오골프, 티스캐너에서의 수집 가능 여부를 체크하고
소스 진단 보고서를 생성한다.

사용법:
    from scraper.source_checker import SourceChecker
    checker = SourceChecker()
    report = await checker.check_all("베르힐CC영종")
    print(report["summary"])
"""
import asyncio
import re
from datetime import date, timedelta
from loguru import logger
from playwright.async_api import async_playwright, Page

from scraper.teescanner_scraper import TeescannerScraper

KAKAO_GOLF_URL = "https://www.kakao.golf"


class SourceChecker:

    def __init__(self):
        self._ts = TeescannerScraper()
        self._ts_loaded = False

    # ─────────────────────────────────────────
    # 카카오골프 체크
    # ─────────────────────────────────────────
    async def check_kakao(self, name: str) -> dict:
        """카카오골프에서 골프장 검색 → 카드 존재 + D+1 티타임 유무 확인"""
        result = {
            "source": "kakao",
            "found": False,
            "has_teetimes": False,
            "sample_count": 0,
            "error": None,
        }

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/17.0 Mobile/15E148 Safari/604.1"
                    ),
                    viewport={"width": 390, "height": 844},
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                )
                page = await context.new_page()

                # 카카오골프 접속 → 검색
                await page.goto(KAKAO_GOLF_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(1.5)

                # 검색창 찾기
                search_input = None
                for sel in ['input[placeholder*="검색"]', 'input[type="search"]', 'input']:
                    try:
                        el = await page.wait_for_selector(sel, timeout=3000)
                        if el:
                            search_input = el
                            break
                    except Exception:
                        continue

                if not search_input:
                    result["error"] = "검색창 없음"
                    await browser.close()
                    return result

                await search_input.click()
                await asyncio.sleep(0.3)
                await search_input.fill(name)
                await asyncio.sleep(0.3)
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)

                # 검색 결과에서 카드 존재 여부
                body_text = await page.evaluate("() => document.body?.innerText || ''")
                if "검색 결과가 없습니다" in body_text or "검색결과가 없습니다" in body_text:
                    await browser.close()
                    return result

                # 카드 존재 확인: 골프장명이 텍스트에 있으면 found
                name_stripped = name.replace("CC", "").replace("cc", "").replace("GC", "").strip()
                if name in body_text or name_stripped in body_text:
                    result["found"] = True

                    # 카드 클릭 → 티타임 존재 확인
                    clicked = await self._click_first_card(page, name, name_stripped)
                    if clicked:
                        await asyncio.sleep(2)
                        tt_text = await page.evaluate("() => document.body?.innerText || ''")

                        if "잔여 티타임이 없어요" in tt_text or "티타임이 없습니다" in tt_text:
                            result["has_teetimes"] = False
                        else:
                            # 시간 패턴으로 티타임 개수 추정
                            time_re = re.compile(r'\b\d{1,2}:\d{2}\b')
                            times = time_re.findall(tt_text)
                            valid = [t for t in times if 5 <= int(t.split(":")[0]) <= 19]
                            result["sample_count"] = len(valid)
                            result["has_teetimes"] = len(valid) > 0

                await browser.close()

        except Exception as e:
            result["error"] = str(e)
            logger.debug(f"[SourceChecker] 카카오 체크 오류: {e}")

        return result

    async def _click_first_card(self, page: Page, name: str, name_stripped: str) -> bool:
        """검색 결과에서 첫 번째 카드 클릭"""
        import json
        variants = json.dumps([name_stripped, name], ensure_ascii=False)
        try:
            rect = await page.evaluate(f"""
                () => {{
                    const variants = {variants};
                    const containers = document.querySelectorAll(
                        'a[href], li, [role="listitem"], [class*="item"], [class*="card"]'
                    );
                    for (const el of containers) {{
                        const text = (el.innerText || '').trim();
                        const firstLine = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0)[0] || '';
                        for (const v of variants) {{
                            if (firstLine === v || firstLine.includes(v)) {{
                                const r = (el.closest('a') || el).getBoundingClientRect();
                                return {{x: r.left + r.width / 2, y: r.top + r.height / 2}};
                            }}
                        }}
                    }}
                    return null;
                }}
            """)
            if rect and rect.get("x") and rect.get("y"):
                await page.mouse.click(rect["x"], rect["y"])
                return True
        except Exception:
            pass

        # locator fallback
        for v in [name_stripped, name]:
            try:
                loc = page.get_by_text(v, exact=False).first
                await loc.click(timeout=3000)
                return True
            except Exception:
                continue
        return False

    # ─────────────────────────────────────────
    # 티스캐너 체크
    # ─────────────────────────────────────────
    def check_teescanner(self, name: str) -> dict:
        """티스캐너 API에서 골프장 퍼지 매칭"""
        result = {
            "source": "teescanner",
            "found": False,
            "ts_name": None,
            "match_type": None,
            "sample_count": 0,
            "error": None,
        }

        try:
            if not self._ts_loaded:
                self._ts.fetch_all_courses()
                self._ts_loaded = True

            ts_names = list(self._ts.course_map.keys())

            # 1순위: 정확히 일치
            if name in ts_names:
                result["found"] = True
                result["ts_name"] = name
                result["match_type"] = "exact"
            else:
                # 2순위: 이름 포함 매칭 (양방향)
                clean_name = name.replace("CC", "").replace("cc", "").replace("GC", "").replace("(P)", "").strip()
                matches = []
                for ts_name in ts_names:
                    clean_ts = ts_name.replace("(P)", "").replace("(P9)", "").strip()
                    if clean_name in clean_ts or clean_ts in clean_name:
                        matches.append(ts_name)
                    elif name in ts_name or ts_name in name:
                        matches.append(ts_name)

                if matches:
                    result["found"] = True
                    result["ts_name"] = matches[0]
                    result["match_type"] = "fuzzy"
                    if len(matches) > 1:
                        result["all_matches"] = matches

            # 티타임 샘플 카운트
            if result["found"] and result["ts_name"]:
                try:
                    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
                    teetimes = self._ts.fetch_teetimes(tomorrow)
                    count = sum(
                        1 for t in teetimes
                        if t.get("golfclub_name") == result["ts_name"]
                    )
                    result["sample_count"] = count
                except Exception as e:
                    logger.debug(f"[SourceChecker] 티스캐너 샘플 조회 실패: {e}")

        except Exception as e:
            result["error"] = str(e)
            logger.debug(f"[SourceChecker] 티스캐너 체크 오류: {e}")

        return result

    # ─────────────────────────────────────────
    # 전체 소스 체크 + 보고서 생성
    # ─────────────────────────────────────────
    async def check_all(self, name: str) -> dict:
        """카카오 + 티스캐너 전체 체크 → 소스 진단 보고서"""
        logger.info(f"[SourceChecker] '{name}' 소스 탐색 시작")

        # 티스캐너는 동기 — 먼저 실행
        ts_result = self.check_teescanner(name)

        # 카카오는 비동기
        kakao_result = await self.check_kakao(name)

        # 추천 소스 결정
        recommendation = self._recommend(name, kakao_result, ts_result)

        report = {
            "course_name": name,
            "kakao": kakao_result,
            "teescanner": ts_result,
            "recommendation": recommendation,
            "summary": self._format_report(name, kakao_result, ts_result, recommendation),
        }

        logger.info(f"[SourceChecker] '{name}' 탐색 완료: {recommendation['source']}")
        return report

    def _recommend(self, name: str, kakao: dict, ts: dict) -> dict:
        """소스 우선순위에 따른 추천"""
        # 카카오에 티타임이 있으면 → 카카오 (가장 상세한 데이터)
        if kakao["has_teetimes"] and kakao["sample_count"] > 0:
            return {
                "source": "kakao",
                "scraper": "KakaoApiScraper",
                "reason": f"카카오골프에서 D+1 {kakao['sample_count']}건 확인",
            }

        # 티스캐너에 있으면 → 티스캐너
        if ts["found"]:
            return {
                "source": "teescanner",
                "scraper": "TeescannerScraper",
                "ts_name": ts["ts_name"],
                "reason": f"티스캐너 '{ts['ts_name']}' 매칭 ({ts['match_type']})",
            }

        # 카카오에 카드만 있고 티타임 없음 → auto (폴백 기대)
        if kakao["found"]:
            return {
                "source": "auto",
                "scraper": "KakaoApiScraper",
                "reason": "카카오 카드 있으나 티타임 없음 — auto 폴백 권장",
            }

        # 둘 다 없음 → 공식HP 탐색 필요
        return {
            "source": "unknown",
            "scraper": None,
            "reason": "카카오/티스캐너 미등록 — 공식 홈페이지 탐색 필요",
        }

    def _format_report(self, name: str, kakao: dict, ts: dict, rec: dict) -> str:
        """사람이 읽을 수 있는 보고서 텍스트"""
        lines = [f"=== {name} 소스 진단 ===", ""]

        # 카카오
        if kakao["error"]:
            lines.append(f"[카카오골프] ⚠️ 체크 실패: {kakao['error']}")
        elif kakao["has_teetimes"]:
            lines.append(f"[카카오골프] ✅ {kakao['sample_count']}건 수집 가능")
        elif kakao["found"]:
            lines.append(f"[카카오골프] ⚠️ 카드 있음, 티타임 없음")
        else:
            lines.append(f"[카카오골프] ❌ 미등록")

        # 티스캐너
        if ts["error"]:
            lines.append(f"[티스캐너]  ⚠️ 체크 실패: {ts['error']}")
        elif ts["found"]:
            sample = f", D+1 {ts['sample_count']}건" if ts["sample_count"] else ""
            lines.append(f"[티스캐너]  ✅ '{ts['ts_name']}' 매칭 ({ts['match_type']}{sample})")
        else:
            lines.append(f"[티스캐너]  ❌ 미등록")

        lines.append("")
        lines.append(f"→ 추천: {rec['source']} ({rec['reason']})")

        if rec.get("scraper"):
            lines.append(f"→ 스크래퍼: {rec['scraper']}")

        return "\n".join(lines)

    # ─────────────────────────────────────────
    # 배치: 여러 골프장 한번에 체크
    # ─────────────────────────────────────────
    async def check_batch(self, names: list[str]) -> list[dict]:
        """여러 골프장 일괄 체크"""
        results = []
        for name in names:
            report = await self.check_all(name)
            results.append(report)
        return results


if __name__ == "__main__":
    import sys

    names = sys.argv[1:]
    if not names:
        print("사용법: python -m scraper.source_checker 골프장1 골프장2 ...")
        sys.exit(1)

    checker = SourceChecker()
    for name in names:
        report = asyncio.run(checker.check_all(name))
        print(report["summary"])
        print()
