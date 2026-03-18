"""
run.py 테스트
- parse_args 인자 파싱 (--skip-ai, --skip-analysis, --courses 등)
- 파이프라인 흐름: skip_ai / skip_analysis 분기 검증
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# 1. parse_args 테스트
# ---------------------------------------------------------------------------
class ParseArgsTests(unittest.TestCase):
    """parse_args 가 CLI 인자를 올바르게 파싱하는지 검증"""

    def _parse(self, argv: list[str]):
        with patch("sys.argv", ["run.py"] + argv):
            from run import parse_args
            return parse_args()

    def test_default_values(self):
        args = self._parse([])
        self.assertEqual(args.mode, "collect")
        self.assertEqual(args.report_type, "daily")
        self.assertFalse(args.skip_ai)
        self.assertFalse(args.skip_analysis)
        self.assertIsNone(args.courses)
        self.assertFalse(args.show_browser)

    def test_skip_ai_flag(self):
        args = self._parse(["--skip-ai"])
        self.assertTrue(args.skip_ai)
        self.assertFalse(args.skip_analysis)

    def test_skip_analysis_flag(self):
        args = self._parse(["--skip-analysis"])
        self.assertTrue(args.skip_analysis)
        self.assertFalse(args.skip_ai)

    def test_both_skip_flags(self):
        args = self._parse(["--skip-ai", "--skip-analysis"])
        self.assertTrue(args.skip_ai)
        self.assertTrue(args.skip_analysis)

    def test_courses_single(self):
        args = self._parse(["--courses", "광주CC"])
        self.assertEqual(args.courses, ["광주CC"])

    def test_courses_multiple(self):
        args = self._parse(["--courses", "광주CC", "골드레이크"])
        self.assertEqual(args.courses, ["광주CC", "골드레이크"])

    def test_courses_none_by_default(self):
        args = self._parse([])
        self.assertIsNone(args.courses)

    def test_mode_report(self):
        args = self._parse(["--mode", "report"])
        self.assertEqual(args.mode, "report")

    def test_report_type_weekly(self):
        args = self._parse(["--report-type", "weekly"])
        self.assertEqual(args.report_type, "weekly")

    def test_show_browser_flag(self):
        args = self._parse(["--show-browser"])
        self.assertTrue(args.show_browser)

    def test_date_override(self):
        args = self._parse(["--date", "2026-01-15"])
        self.assertEqual(args.report_date, "2026-01-15")

    def test_combined_flags(self):
        args = self._parse([
            "--skip-ai",
            "--courses", "광주CC", "골드레이크",
            "--show-browser",
        ])
        self.assertTrue(args.skip_ai)
        self.assertFalse(args.skip_analysis)
        self.assertEqual(args.courses, ["광주CC", "골드레이크"])
        self.assertTrue(args.show_browser)


# ---------------------------------------------------------------------------
# 2. 파이프라인 흐름 테스트 (main 함수 분기)
# ---------------------------------------------------------------------------
def _run_async(coro):
    """유틸: 코루틴을 동기적으로 실행"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# 공통으로 사용할 가짜 scraper/page/context/browser
def _make_fake_playwright_cm(scraper_rows=None):
    """async_playwright() 컨텍스트매니저를 모킹하여 반환"""
    if scraper_rows is None:
        scraper_rows = [{"dummy": 1}]

    fake_page = AsyncMock()
    fake_context = AsyncMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)
    fake_browser = AsyncMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)

    fake_pw = AsyncMock()
    fake_pw.chromium.launch = AsyncMock(return_value=fake_browser)

    # async context manager
    fake_pw_cm = AsyncMock()
    fake_pw_cm.__aenter__ = AsyncMock(return_value=fake_pw)
    fake_pw_cm.__aexit__ = AsyncMock(return_value=False)

    return fake_pw_cm, fake_page


class SkipAiPipelineTests(unittest.TestCase):
    """--skip-ai 시 LLM 보고서를 건너뛰고, build_all(skip_ai=True)로 호출하는지 검증"""

    @patch("run._notify_macos")
    @patch("run._deploy_firebase")
    @patch("run.send_telegram_message")
    @patch("run.render_report_with_llm")
    @patch("run.evaluate_rules", new_callable=AsyncMock, return_value={
        "high_defense": [], "repeat_discount": [],
        "price_response": [], "premium_candidates": [],
        "member_open_alerts": [],
    })
    @patch("run.detect_price_responses", new_callable=AsyncMock, return_value=0)
    @patch("run.aggregate_daily", new_callable=AsyncMock, return_value=0)
    @patch("run.get_aggregation_summary", new_callable=AsyncMock, return_value={
        "courses": {}, "member_opens_today": [],
    })
    @patch("run.get_change_summary", new_callable=AsyncMock, return_value={
        "total": 0, "by_type": {"인하": 0, "인상": 0, "특가부착": 0, "특가해제": 0},
        "by_course": {}, "biggest_cut": None,
    })
    @patch("run.detect_price_changes", new_callable=AsyncMock, return_value=0)
    @patch("run.compute_daily_summary", return_value=[])
    @patch("run.insert_snapshots", new_callable=AsyncMock, return_value=5)
    @patch("run.upsert_daily_summary", new_callable=AsyncMock)
    @patch("run.get_or_create_course", new_callable=AsyncMock, return_value=1)
    @patch("run.start_run", new_callable=AsyncMock, return_value=1)
    @patch("run.finish_run", new_callable=AsyncMock)
    @patch("run.init_db", new_callable=AsyncMock)
    @patch("run.setup_logging")
    @patch("run.COURSE_DELAY", 0)
    def test_skip_ai_skips_llm_but_calls_build_all(
        self,
        mock_setup_logging,
        mock_init_db,
        mock_finish_run,
        mock_start_run,
        mock_get_or_create,
        mock_upsert_daily,
        mock_insert_snap,
        mock_compute_daily,
        mock_detect_price,
        mock_get_change,
        mock_get_agg,
        mock_agg_daily,
        mock_detect_resp,
        mock_eval_rules,
        mock_render_llm,
        mock_send_tg,
        mock_deploy_fb,
        mock_notify,
    ):
        fake_pw_cm, fake_page = _make_fake_playwright_cm()
        fake_scraper = MagicMock()
        fake_scraper.collect_course = AsyncMock(return_value=[{"dummy": 1}])
        fake_scraper.collected_at = "2026-03-17 10:00:00"

        with patch("sys.argv", ["run.py", "--skip-ai", "--courses", "TestCC"]), \
             patch("run.async_playwright", return_value=fake_pw_cm), \
             patch("run.COURSES", ["TestCC"]), \
             patch("run._reports_enabled", return_value=True), \
             patch("scraper.kakao_api_scraper.KakaoApiScraper", return_value=fake_scraper), \
             patch("run.record_unsold_slots", create=True, return_value=0) as _, \
             patch("run.collect_weather", create=True, return_value=0) as _, \
             patch("analytics.unsold_tracker.record_unsold_slots", create=True, return_value=0), \
             patch("analytics.weather_collector.collect_weather", create=True, return_value=0), \
             patch("build_dashboard.build_all") as mock_build_all:

            from run import main
            _run_async(main())

        # LLM 보고서 렌더링이 호출되지 않아야 함
        mock_render_llm.assert_not_called()

        # build_all 은 skip_ai=True 로 호출되어야 함
        mock_build_all.assert_called_once_with(skip_ai=True)

        # 텔레그램도 호출되지 않아야 함
        mock_send_tg.assert_not_called()

    @patch("run._notify_macos")
    @patch("run._deploy_firebase")
    @patch("run.send_telegram_message", return_value=True)
    @patch("run.render_report_with_llm", return_value=("test report", {"used_llm": False}))
    @patch("run.build_daily_report_payload", return_value={})
    @patch("run.build_daily_strategy_profiles", new_callable=AsyncMock, return_value=[])
    @patch("run.evaluate_rules", new_callable=AsyncMock, return_value={
        "high_defense": [], "repeat_discount": [],
        "price_response": [], "premium_candidates": [],
        "member_open_alerts": [],
    })
    @patch("run.detect_price_responses", new_callable=AsyncMock, return_value=0)
    @patch("run.aggregate_daily", new_callable=AsyncMock, return_value=0)
    @patch("run.get_aggregation_summary", new_callable=AsyncMock, return_value={
        "courses": {}, "member_opens_today": [],
    })
    @patch("run.get_change_summary", new_callable=AsyncMock, return_value={
        "total": 0, "by_type": {"인하": 0, "인상": 0, "특가부착": 0, "특가해제": 0},
        "by_course": {}, "biggest_cut": None,
    })
    @patch("run.detect_price_changes", new_callable=AsyncMock, return_value=0)
    @patch("run.compute_daily_summary", return_value=[])
    @patch("run.insert_snapshots", new_callable=AsyncMock, return_value=5)
    @patch("run.upsert_daily_summary", new_callable=AsyncMock)
    @patch("run.get_or_create_course", new_callable=AsyncMock, return_value=1)
    @patch("run.start_run", new_callable=AsyncMock, return_value=1)
    @patch("run.finish_run", new_callable=AsyncMock)
    @patch("run.init_db", new_callable=AsyncMock)
    @patch("run.setup_logging")
    @patch("run.COURSE_DELAY", 0)
    def test_no_skip_ai_calls_llm_and_build_all_without_skip(
        self,
        mock_setup_logging,
        mock_init_db,
        mock_finish_run,
        mock_start_run,
        mock_get_or_create,
        mock_upsert_daily,
        mock_insert_snap,
        mock_compute_daily,
        mock_detect_price,
        mock_get_change,
        mock_get_agg,
        mock_agg_daily,
        mock_detect_resp,
        mock_eval_rules,
        mock_strategy,
        mock_build_payload,
        mock_render_llm,
        mock_send_tg,
        mock_deploy_fb,
        mock_notify,
    ):
        fake_pw_cm, fake_page = _make_fake_playwright_cm()
        fake_scraper = MagicMock()
        fake_scraper.collect_course = AsyncMock(return_value=[{"dummy": 1}])
        fake_scraper.collected_at = "2026-03-17 10:00:00"

        with patch("sys.argv", ["run.py", "--courses", "TestCC"]), \
             patch("run.async_playwright", return_value=fake_pw_cm), \
             patch("run.COURSES", ["TestCC"]), \
             patch("run._reports_enabled", return_value=True), \
             patch("run._write_report_file", return_value=Path("/tmp/test.txt")), \
             patch("scraper.kakao_api_scraper.KakaoApiScraper", return_value=fake_scraper), \
             patch("analytics.unsold_tracker.record_unsold_slots", create=True, return_value=0), \
             patch("analytics.weather_collector.collect_weather", create=True, return_value=0), \
             patch("build_dashboard.build_all") as mock_build_all:

            from run import main
            _run_async(main())

        # skip-ai 없으면 LLM 보고서가 호출되어야 함
        mock_render_llm.assert_called_once()

        # build_all 은 skip_ai=False 로 호출되어야 함
        mock_build_all.assert_called_once_with(skip_ai=False)


class SkipAnalysisPipelineTests(unittest.TestCase):
    """--skip-analysis 시 경량 분석(hourly_analyzer)만 실행 후 즉시 반환하는지 검증"""

    @patch("run._notify_macos")
    @patch("run._deploy_firebase")
    @patch("run.detect_price_changes", new_callable=AsyncMock)
    @patch("run.aggregate_daily", new_callable=AsyncMock)
    @patch("run.compute_daily_summary", return_value=[])
    @patch("run.insert_snapshots", new_callable=AsyncMock, return_value=3)
    @patch("run.upsert_daily_summary", new_callable=AsyncMock)
    @patch("run.get_or_create_course", new_callable=AsyncMock, return_value=1)
    @patch("run.start_run", new_callable=AsyncMock, return_value=1)
    @patch("run.finish_run", new_callable=AsyncMock)
    @patch("run.init_db", new_callable=AsyncMock)
    @patch("run.setup_logging")
    @patch("run.COURSE_DELAY", 0)
    def test_skip_analysis_runs_hourly_then_returns(
        self,
        mock_setup_logging,
        mock_init_db,
        mock_finish_run,
        mock_start_run,
        mock_get_or_create,
        mock_upsert_daily,
        mock_insert_snap,
        mock_compute_daily,
        mock_detect_price,
        mock_agg_daily,
        mock_deploy_fb,
        mock_notify,
    ):
        fake_pw_cm, fake_page = _make_fake_playwright_cm()
        fake_scraper = MagicMock()
        fake_scraper.collect_course = AsyncMock(return_value=[{"dummy": 1}])
        fake_scraper.collected_at = "2026-03-17 06:00:00"

        mock_hourly_build = AsyncMock(return_value={"some": "summary"})
        mock_hourly_detect = AsyncMock(return_value=2)

        with patch("sys.argv", ["run.py", "--skip-analysis", "--courses", "TestCC"]), \
             patch("run.async_playwright", return_value=fake_pw_cm), \
             patch("run.COURSES", ["TestCC"]), \
             patch("scraper.kakao_api_scraper.KakaoApiScraper", return_value=fake_scraper), \
             patch("analytics.hourly_analyzer.build_hourly_summary_from_db", mock_hourly_build), \
             patch("analytics.hourly_analyzer.detect_hourly_price_changes", mock_hourly_detect):

            from run import main
            _run_async(main())

        # hourly_analyzer 가 호출되었어야 함
        mock_hourly_build.assert_called_once_with("2026-03-17 06:00:00")
        mock_hourly_detect.assert_called_once_with("2026-03-17 06:00:00")

        # 전체 분석 파이프라인은 실행되지 않아야 함
        mock_detect_price.assert_not_called()
        mock_agg_daily.assert_not_called()

        # 배포도 실행되지 않아야 함
        mock_deploy_fb.assert_not_called()

        # macOS 알림도 실행되지 않아야 함
        mock_notify.assert_not_called()

    @patch("run.compute_daily_summary", return_value=[])
    @patch("run.insert_snapshots", new_callable=AsyncMock, return_value=0)
    @patch("run.upsert_daily_summary", new_callable=AsyncMock)
    @patch("run.get_or_create_course", new_callable=AsyncMock, return_value=1)
    @patch("run.start_run", new_callable=AsyncMock, return_value=1)
    @patch("run.finish_run", new_callable=AsyncMock)
    @patch("run.init_db", new_callable=AsyncMock)
    @patch("run.setup_logging")
    @patch("run.COURSE_DELAY", 0)
    def test_skip_analysis_no_rows_skips_hourly(
        self,
        mock_setup_logging,
        mock_init_db,
        mock_finish_run,
        mock_start_run,
        mock_get_or_create,
        mock_upsert_daily,
        mock_insert_snap,
        mock_compute_daily,
    ):
        """수집 결과가 0건이면 hourly_analyzer도 실행하지 않고 반환"""
        fake_pw_cm, fake_page = _make_fake_playwright_cm()
        fake_scraper = MagicMock()
        # 빈 결과 반환
        fake_scraper.collect_course = AsyncMock(return_value=[])
        fake_scraper.collected_at = "2026-03-17 06:00:00"

        mock_hourly_build = AsyncMock()

        with patch("sys.argv", ["run.py", "--skip-analysis", "--courses", "TestCC"]), \
             patch("run.async_playwright", return_value=fake_pw_cm), \
             patch("run.COURSES", ["TestCC"]), \
             patch("scraper.kakao_api_scraper.KakaoApiScraper", return_value=fake_scraper), \
             patch("analytics.hourly_analyzer.build_hourly_summary_from_db", mock_hourly_build):

            from run import main
            _run_async(main())

        # total_rows == 0이면 hourly 분석도 스킵
        mock_hourly_build.assert_not_called()


class BuildAllSkipAiArgTests(unittest.TestCase):
    """build_all 호출 시 skip_ai 인자가 정확히 전달되는지 집중 검증"""

    def _run_pipeline_with_skip_ai(self, skip_ai_flag: bool):
        """공통: skip_ai 플래그에 따라 main()을 실행하고 build_all mock 반환"""
        fake_pw_cm, _ = _make_fake_playwright_cm()
        fake_scraper = MagicMock()
        fake_scraper.collect_course = AsyncMock(return_value=[{"dummy": 1}])
        fake_scraper.collected_at = "2026-03-17 10:00:00"

        argv = ["run.py", "--courses", "TestCC"]
        if skip_ai_flag:
            argv.append("--skip-ai")

        patches = {
            "run.async_playwright": MagicMock(return_value=fake_pw_cm),
            "run.setup_logging": MagicMock(),
            "run.init_db": AsyncMock(),
            "run.start_run": AsyncMock(return_value=1),
            "run.finish_run": AsyncMock(),
            "run.get_or_create_course": AsyncMock(return_value=1),
            "run.insert_snapshots": AsyncMock(return_value=5),
            "run.upsert_daily_summary": AsyncMock(),
            "run.compute_daily_summary": MagicMock(return_value=[]),
            "run.detect_price_changes": AsyncMock(return_value=0),
            "run.get_change_summary": AsyncMock(return_value={
                "total": 0,
                "by_type": {"인하": 0, "인상": 0, "특가부착": 0, "특가해제": 0},
                "by_course": {}, "biggest_cut": None,
            }),
            "run.get_aggregation_summary": AsyncMock(return_value={
                "courses": {}, "member_opens_today": [],
            }),
            "run.aggregate_daily": AsyncMock(return_value=0),
            "run.detect_price_responses": AsyncMock(return_value=0),
            "run.evaluate_rules": AsyncMock(return_value={
                "high_defense": [], "repeat_discount": [],
                "price_response": [], "premium_candidates": [],
                "member_open_alerts": [],
            }),
            "run.COURSES": ["TestCC"],
            "run.COURSE_DELAY": 0,
            "run._reports_enabled": MagicMock(return_value=True),
            "run._deploy_firebase": MagicMock(),
            "run._notify_macos": MagicMock(),
            "run.send_telegram_message": MagicMock(return_value=True),
            "run.render_report_with_llm": MagicMock(return_value=("report", {"used_llm": False})),
            "run.build_daily_report_payload": MagicMock(return_value={}),
            "run.build_daily_strategy_profiles": AsyncMock(return_value=[]),
            "run._write_report_file": MagicMock(return_value=Path("/tmp/test.txt")),
            "scraper.kakao_api_scraper.KakaoApiScraper": MagicMock(return_value=fake_scraper),
            "analytics.unsold_tracker.record_unsold_slots": MagicMock(return_value=0),
            "analytics.weather_collector.collect_weather": MagicMock(return_value=0),
        }

        mock_build_all = MagicMock()
        patches["build_dashboard.build_all"] = mock_build_all

        import contextlib
        with patch("sys.argv", argv), \
             contextlib.ExitStack() as stack:
            for target, mock_obj in patches.items():
                stack.enter_context(patch(target, mock_obj))

            from run import main
            _run_async(main())

        return mock_build_all

    def test_skip_ai_true_passes_to_build_all(self):
        mock_build = self._run_pipeline_with_skip_ai(skip_ai_flag=True)
        mock_build.assert_called_once_with(skip_ai=True)

    def test_skip_ai_false_passes_to_build_all(self):
        mock_build = self._run_pipeline_with_skip_ai(skip_ai_flag=False)
        mock_build.assert_called_once_with(skip_ai=False)


if __name__ == "__main__":
    unittest.main()
