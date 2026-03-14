"""
카카오골프 티타임 수집봇
실행: python run.py
"""
import asyncio
import argparse
import os
import platform
import sys
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
from rich.console import Console
from rich.table import Table
from playwright.async_api import Error as PlaywrightError, async_playwright

# 경로 설정
sys.path.insert(0, str(Path(__file__).parent))

from config.courses import COURSES
from db.database import init_db, get_or_create_course, start_run, finish_run, insert_snapshots, upsert_daily_summary
from scraper.kakao_scraper import KakaoGolfScraper, COURSE_DELAY
from scraper.calculator import compute_daily_summary
from analytics.price_change_detector import detect_price_changes, get_change_summary
from analytics.price_response_detector import detect_price_responses
from analytics.daily_aggregator import aggregate_daily, get_aggregation_summary
from analytics.rule_engine import evaluate_rules
from analytics.report_payload_builder import (
    build_daily_report_payload,
    build_weekly_report_payload,
    build_monthly_report_payload,
    build_yearly_report_payload,
)
from analytics.report_generator import render_daily_text_report
from analytics.llm_report_writer import render_report as render_report_with_llm
from analytics.strategy_profile import build_daily_strategy_profiles
from telegram_bot import send_message as send_telegram_message, get_config_help as get_telegram_config_help

console = Console()
_ENV_CACHE = None

# ── 로그 설정
def setup_logging():
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}",
        level="INFO"
    )
    logger.add(
        log_dir / f"collect_{datetime.now().strftime('%Y-%m-%d')}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="카카오골프 수집/보고서 실행기")
    parser.add_argument("--mode", choices=["collect", "report"], default="collect")
    parser.add_argument("--report-type", choices=["daily", "weekly", "monthly", "yearly", "all"], default="daily")
    parser.add_argument("--date", dest="report_date", default=datetime.now().date().isoformat())
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="수집 시 Playwright 브라우저 창을 표시합니다. 기본값은 headless 백그라운드 실행입니다.",
    )
    return parser.parse_args()


def _load_local_env() -> dict[str, str]:
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE

    loaded: dict[str, str] = {}
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
            loaded[key] = value
    _ENV_CACHE = loaded
    return loaded


def _reports_enabled() -> bool:
    _load_local_env()
    return os.getenv("REPORTS_ENABLED", "true").lower() == "true"

# ── 메인 수집 루틴
async def main():
    args = parse_args()
    setup_logging()

    if args.mode == "report":
        if not _reports_enabled():
            logger.warning("보고서 기능 비활성화 상태입니다. report 모드를 종료합니다.")
            console.print("[yellow]보고서 기능이 비활성화되어 report 모드를 건너뜁니다.[/yellow]")
            return
        await init_db()
        await generate_reports(args.report_date, args.report_type)
        return

    logger.info("=" * 50)
    logger.info("카카오골프 티타임 수집 시작")
    logger.info(f"대상 골프장: {COURSES}")
    logger.info("=" * 50)

    # DB 초기화
    await init_db()
    logger.info("DB 초기화 완료")

    # 수집 실행 기록 시작
    run_id = await start_run()

    total_rows = 0
    results = []
    failed_courses = 0
    browser = None
    context = None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=not args.show_browser,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
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
            scraper = KakaoGolfScraper()

            for course_name in COURSES:
                logger.info(f"── [{course_name}] 수집 시작")
                try:
                    course_id = await get_or_create_course(course_name)
                    rows = await scraper.collect_course(page, course_name, course_id, run_id)

                    if rows:
                        inserted = await insert_snapshots(rows)
                        summaries = compute_daily_summary(rows)
                        await upsert_daily_summary(summaries)
                        total_rows += inserted
                        results.append({"name": course_name, "count": inserted, "status": "✅"})
                        logger.info(f"── [{course_name}] 저장 완료: {inserted}개")
                    else:
                        results.append({"name": course_name, "count": 0, "status": "⚠️"})
                        logger.warning(f"── [{course_name}] 수집된 데이터 없음")

                except Exception as e:
                    failed_courses += 1
                    results.append({"name": course_name, "count": 0, "status": "❌"})
                    logger.exception(f"── [{course_name}] 오류: {e}")

                await asyncio.sleep(COURSE_DELAY)
    except Exception as exc:
        await finish_run(run_id, "failed", total_rows, str(exc))
        raise
    finally:
        await _safe_close_playwright_resource(context, "browser context")
        await _safe_close_playwright_resource(browser, "browser")

    run_status = "success"
    run_error = None
    if failed_courses == len(COURSES):
        run_status = "failed"
        run_error = "all courses failed"
    elif failed_courses > 0:
        run_status = "partial_success"
        run_error = f"{failed_courses} course(s) failed"

    await finish_run(run_id, run_status, total_rows, run_error)

    # 결과 출력
    table = Table(title="수집 완료", show_header=True)
    table.add_column("골프장", style="cyan")
    table.add_column("티타임 수", justify="right", style="green")
    table.add_column("상태")

    for r in results:
        table.add_row(r["name"], str(r["count"]), r["status"])

    console.print(table)
    console.print(f"\n[bold green]총 {total_rows}개 티타임 저장 완료[/bold green]")
    logger.info(f"수집 완료. 총 {total_rows}개 저장.")

    # ── 분석 파이프라인 (수집 성공 시 실행)
    if total_rows > 0:
        logger.info("=" * 50)
        logger.info("분석 파이프라인 시작")

        event_count = 0
        response_count = 0
        change_summary = {"total": 0, "by_type": {}, "by_course": {}, "biggest_cut": None}
        agg_summary = {"courses": {}, "member_opens_today": []}
        rule_summary = {
            "high_defense": [],
            "repeat_discount": [],
            "price_response": [],
            "premium_candidates": [],
            "member_open_alerts": [],
        }

        try:
            # 1. 가격 변동 감지 (전일 vs 당일)
            event_count = await detect_price_changes()
            change_summary = await get_change_summary()
            if event_count > 0:
                by_type = change_summary["by_type"]
                console.print(
                    f"\n[bold yellow]가격 변동 감지: {event_count}건[/bold yellow]"
                    f"  (인하 {by_type['인하']}, 인상 {by_type['인상']}, "
                    f"특가부착 {by_type['특가부착']}, 특가해제 {by_type['특가해제']})"
                )
                if change_summary["biggest_cut"]:
                    bc = change_summary["biggest_cut"]
                    console.print(
                        f"  최대 인하: {bc['course_name']} {bc['play_date']} "
                        f"{bc['tee_time']} {bc['delta_price_krw']:+,}원 ({bc['delta_pct']:+.1f}%)"
                    )
            else:
                console.print("\n[dim]가격 변동 없음[/dim]")
        except Exception as e:
            logger.error(f"가격변동 감지 오류: {e}")

        try:
            # 2. 일간 지표 집계 (daily_course_metrics + member_open_events)
            group_count = await aggregate_daily()
            agg_summary = await get_aggregation_summary()

            agg_table = Table(title="일간 집계", show_header=True)
            agg_table.add_column("골프장", style="cyan")
            agg_table.add_column("대중제 잔여티", justify="right")
            agg_table.add_column("특가티", justify="right", style="yellow")
            agg_table.add_column("최저가", justify="right", style="green")

            for cn, info in sorted(agg_summary["courses"].items()):
                agg_table.add_row(
                    cn,
                    str(info["total_slots"]),
                    str(info["promo_slots"]),
                    f"{info['min_price']:,}원" if info["min_price"] else "-",
                )
            console.print(agg_table)

            if agg_summary["member_opens_today"]:
                console.print("\n[bold magenta]회원제 오픈 신규 감지:[/bold magenta]")
                for mo in agg_summary["member_opens_today"]:
                    promo_tag = " [특가]" if mo["promo_flag"] else ""
                    console.print(
                        f"  {mo['course_name']} / {mo['play_date']} "
                        f"→ {mo['slot_count']}슬롯{promo_tag}"
                    )
        except Exception as e:
            logger.error(f"일간 집계 오류: {e}")

        try:
            # 2-1. 구간 단위 할인 반응 측정
            response_count = await detect_price_responses()
            if response_count > 0:
                console.print(f"[dim]구간 할인 반응 측정 {response_count}건[/dim]")
        except Exception as e:
            logger.error(f"할인반응 측정 오류: {e}")

        try:
            # 3. 판단 룰 엔진
            rule_summary = await evaluate_rules()
            if rule_summary["high_defense"]:
                console.print("\n[bold green]가격 유지 여력 구간:[/bold green]")
                for item in rule_summary["high_defense"][:5]:
                    console.print(
                        f"  {item['course_name']} / {item['play_date']} / {item['part_type']} "
                        f"→ 잔여 {item['open_slots']} / 최저 {item['min_price_krw']:,}원"
                    )

            if rule_summary["premium_candidates"]:
                console.print("\n[bold cyan]프리미엄 후보 구간:[/bold cyan]")
                for item in rule_summary["premium_candidates"][:5]:
                    console.print(
                        f"  {item['course_name']} / {item['play_date']} / {item['part_type']} "
                        f"→ 평균 {item['avg_price_krw']:,}원 / 잔여 {item['open_slots']}"
                    )

            if rule_summary["repeat_discount"]:
                console.print("\n[bold yellow]할인 의존 신호:[/bold yellow]")
                for item in rule_summary["repeat_discount"][:5]:
                    ratio = item.get("signal_ratio")
                    ratio_text = f"{ratio:.0%}" if isinstance(ratio, float) else "-"
                    console.print(
                        f"  {item['course_name']} / {item.get('play_date', item.get('weekday_type', '-'))} / "
                        f"{item['part_type']} → {item['signal']} ({ratio_text})"
                    )
            if rule_summary["price_response"]:
                console.print("\n[bold magenta]할인 반응 신호:[/bold magenta]")
                for item in rule_summary["price_response"][:5]:
                    speed = item.get("response_speed") or "-"
                    d3 = item.get("drop_rate_d3")
                    d3_text = f"{d3:.0%}" if isinstance(d3, float) else "-"
                    console.print(
                        f"  {item['course_name']} / {item['play_date']} / {item.get('part_type', '-')} "
                        f"→ {item['response_grade']} ({speed}, 3일감소율 {d3_text})"
                    )
        except Exception as e:
            logger.error(f"룰 엔진 오류: {e}")

        if _reports_enabled():
            current_report_date = datetime.now().date().isoformat()
            prev_report_date = (datetime.now().date() - timedelta(days=1)).isoformat()
            prev_agg_summary = await get_aggregation_summary(prev_report_date)
            prev_rule_summary = await evaluate_rules(prev_report_date)
            strategy_profile = await build_daily_strategy_profiles(current_report_date)
            report_payload = build_daily_report_payload(
                report_date=current_report_date,
                total_rows=total_rows,
                change_summary=change_summary,
                agg_summary=agg_summary,
                prev_agg_summary=prev_agg_summary,
                rule_summary=rule_summary,
                prev_rule_summary=prev_rule_summary,
                strategy_profile=strategy_profile,
            )
            brief_text, render_meta = render_report_with_llm(report_payload, prefer_llm=True)
            output_path = _write_report_file("daily", current_report_date, brief_text)
            console.print("\n[bold white]일간 브리핑[/bold white]")
            console.print(brief_text)
            logger.info(f"보고서 렌더링 방식: {render_meta}")
            logger.info(f"[보고서] 저장 완료: {output_path.name}")

            sent = send_telegram_message(brief_text)
            if not sent:
                logger.info(get_telegram_config_help())
        else:
            logger.info("보고서 기능 비활성화: 일간 브리핑 생성 및 전송을 건너뜁니다.")

        # ── 대시보드 빌드 (V5)
        try:
            from build_dashboard import build_all
            build_all()
            logger.info("대시보드 빌드 완료")
        except Exception as e:
            logger.error(f"대시보드 빌드 오류: {e}")

        # ── GitHub Pages 자동 배포
        try:
            _deploy_github_pages()
        except Exception as e:
            logger.error(f"GitHub Pages 배포 오류: {e}")

        logger.info("분석 파이프라인 완료")

        # ── macOS 시스템 알림
        _notify_macos(total_rows, event_count, agg_summary)

    else:
        logger.warning("수집 결과 없음 → 분석 파이프라인 스킵")
        _notify_macos_error()


def _deploy_github_pages():
    """대시보드 HTML → GitHub Pages 자동 배포"""
    import subprocess, shutil

    script_dir = Path(__file__).parent
    docs_dir = script_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    # docs/index.html 로 복사
    html_src = script_dir / "golf_dashboard.html"
    if not html_src.exists():
        logger.warning("golf_dashboard.html 없음 → GitHub 배포 스킵")
        return

    shutil.copy2(html_src, docs_dir / "index.html")

    # tab8 JSON 파일도 복사
    for f in script_dir.glob("golf_tab8_*.json"):
        shutil.copy2(f, docs_dir / f.name)

    # git add + commit + push
    git_dir = script_dir / ".git"
    if not git_dir.exists():
        logger.warning(".git 없음 → GitHub 배포 스킵 (먼저 deploy_github_pages.sh 실행 필요)")
        return

    try:
        subprocess.run(["git", "add", "docs/"], cwd=script_dir, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", f"📊 자동 업데이트 {datetime.now().strftime('%m/%d %H:%M')}"],
            cwd=script_dir, capture_output=True, text=True
        )
        if result.returncode == 0:
            subprocess.run(["git", "push", "origin", "main"], cwd=script_dir, check=True, capture_output=True, timeout=60)
            logger.info("GitHub Pages 배포 완료")
        else:
            logger.info("GitHub Pages: 변경사항 없음 (스킵)")
    except subprocess.TimeoutExpired:
        logger.error("GitHub push 타임아웃 (60초)")
    except subprocess.CalledProcessError as e:
        logger.error(f"GitHub 배포 실패: {e.stderr}")


def _notify_macos(total_rows: int, event_count: int, agg_summary: dict):
    """macOS 시스템 알림 — 수집·분석 완료 시"""
    import subprocess

    if platform.system() != "Darwin":
        return

    # 최저가 골프장 찾기
    courses = agg_summary.get("courses", {})
    if courses:
        cheapest = min(courses.items(), key=lambda x: x[1]["min_price"] or 999999)
        price_line = f"{cheapest[0]} {cheapest[1]['min_price']:,}원~"
    else:
        price_line = "-"

    # 가격 변동 문구
    if event_count > 0:
        change_line = f"가격변동 {event_count}건"
    else:
        change_line = "가격변동 없음"

    title   = "카카오골프 수집 완료"
    message = f"티타임 {total_rows:,}개 | {change_line} | 최저 {price_line}"

    script = (
        f'display notification "{_escape_applescript(message)}" '
        f'with title "{_escape_applescript(title)}" '
        f'sound name "Glass"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        logger.debug(f"[알림] macOS 알림 전송: {message}")
    except Exception as e:
        logger.debug(f"[알림] osascript 실패: {e}")


def _notify_macos_error():
    """macOS 시스템 알림 — 수집 실패 시"""
    import subprocess
    if platform.system() != "Darwin":
        return
    script = (
        'display notification "수집된 티타임 없음. 로그 확인 필요." '
        'with title "카카오골프 ⚠️ 수집 실패" '
        'sound name "Sosumi"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception:
        pass


def _escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


async def _safe_close_playwright_resource(resource, label: str):
    if resource is None:
        return
    try:
        await resource.close()
    except PlaywrightError as exc:
        if "Target page, context or browser has been closed" in str(exc):
            logger.debug(f"{label} already closed")
            return
        logger.warning(f"{label} close failed: {exc}")
    except Exception as exc:
        logger.warning(f"{label} close failed: {exc}")


async def generate_reports(report_date: str, report_type: str):
    if not _reports_enabled():
        logger.warning("보고서 기능 비활성화 상태입니다. 보고서 생성을 건너뜁니다.")
        console.print("[yellow]보고서 기능이 비활성화되어 생성하지 않습니다.[/yellow]")
        return

    logger.info("=" * 50)
    logger.info(f"보고서 생성 모드 시작: type={report_type}, date={report_date}")
    logger.info("=" * 50)

    targets = ["daily", "weekly", "monthly", "yearly"] if report_type == "all" else [report_type]
    generated_files = []

    for current_type in targets:
        payload = await _build_report_payload(current_type, report_date)
        text, meta = render_report_with_llm(payload, prefer_llm=True)
        output_path = _write_report_file(current_type, report_date, text)
        generated_files.append(output_path)

        console.print(f"\n[bold white]{current_type.upper()} 보고서[/bold white]")
        console.print(text)
        logger.info(f"[보고서] 저장 완료: {output_path.name} / meta={meta}")

    console.print("\n[bold green]보고서 생성 완료[/bold green]")
    for path in generated_files:
        console.print(f" - {path.name}")


async def _build_report_payload(report_type: str, report_date: str) -> dict:
    if report_type == "daily":
        prev_report_date = (datetime.fromisoformat(report_date).date() - timedelta(days=1)).isoformat()
        change_summary = await get_change_summary(report_date)
        agg_summary = await get_aggregation_summary(report_date)
        prev_agg_summary = await get_aggregation_summary(prev_report_date)
        rule_summary = await evaluate_rules(report_date)
        prev_rule_summary = await evaluate_rules(prev_report_date)
        strategy_profile = await build_daily_strategy_profiles(report_date)

        total_rows = 0
        for info in agg_summary.get("courses", {}).values():
            total_rows += info.get("total_slots") or 0

        return build_daily_report_payload(
            report_date=report_date,
            total_rows=total_rows,
            change_summary=change_summary,
            agg_summary=agg_summary,
            prev_agg_summary=prev_agg_summary,
            rule_summary=rule_summary,
            prev_rule_summary=prev_rule_summary,
            strategy_profile=strategy_profile,
        )
    if report_type == "weekly":
        return await build_weekly_report_payload(report_date)
    if report_type == "monthly":
        return await build_monthly_report_payload(report_date)
    if report_type == "yearly":
        return await build_yearly_report_payload(report_date)
    raise ValueError(f"unsupported report_type: {report_type}")


def _write_report_file(report_type: str, report_date: str, text: str) -> Path:
    output_dir = Path(__file__).parent / "reports" / report_type
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report_type}_report_{report_date}.txt"
    output_path.write_text(text, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    asyncio.run(main())
