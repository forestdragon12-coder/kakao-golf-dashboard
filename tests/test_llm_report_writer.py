import os
import json
import unittest
from unittest.mock import MagicMock, patch

from analytics.llm_report_writer import (
    _extract_response_text,
    _finalize_rendered_report,
    _validate_rendered_report,
    get_prompt_template,
    get_model_for_report_type,
    render_report,
)


class LlmReportWriterTests(unittest.TestCase):
    def test_render_report_falls_back_when_disabled(self):
        payload = {
            "report_type": "daily",
            "report_date": "2026-03-13",
            "summary": {"total_rows": 10, "total_courses": 1, "total_slots": 10, "promo_slots": 0, "promo_ratio": 0.0, "price_change_events": 0, "price_response_events": 0, "top_signals": []},
            "actions": [],
            "evidence": {"price_change_watch": {"total": 0, "by_type": {}}, "discount_response": {"strong_count": 0, "weak_count": 0, "none_count": 0}},
            "risks": [],
            "recommendations": [],
            "course_focus": [],
        }
        with patch.dict(os.environ, {"REPORT_LLM_ENABLED": "false"}, clear=False):
            text, meta = render_report(payload, prefer_llm=True)

        self.assertIn("일간 브리핑", text)
        self.assertFalse(meta["used_llm"])
        self.assertEqual(meta["fallback_reason"], "llm_disabled")
        self.assertEqual(get_prompt_template("monthly"), "monthly_prompt_pro_v3_sectioned")

    def test_render_report_calls_openai_when_enabled_and_configured(self):
        payload = {
            "report_type": "daily",
            "report_date": "2026-03-13",
            "summary": {"total_rows": 10, "total_courses": 1, "total_slots": 10, "promo_slots": 0, "promo_ratio": 0.0, "price_change_events": 0, "price_response_events": 0, "top_signals": []},
            "actions": [],
            "evidence": {"price_change_watch": {"total": 0, "by_type": {}}, "discount_response": {"strong_count": 0, "weak_count": 0, "none_count": 0}},
            "risks": [],
            "recommendations": [],
            "course_focus": [],
        }

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps(
            {
                "output_text": (
                    "1. 오늘의 한 줄 결론\n"
                    "- 테스트 결론입니다.\n\n"
                    "2. 오늘의 가격 변화\n"
                    "- 테스트 변화입니다.\n\n"
                    "3. 오늘의 판매 흐름 변화\n"
                    "- 테스트 흐름입니다.\n\n"
                    "4. 베르힐CC 오늘 포인트\n"
                    "- 테스트 포인트입니다.\n\n"
                    "5. 오늘의 핵심 액션\n"
                    "- 테스트 액션입니다.\n\n"
                    "6. 내일 확인 포인트\n"
                    "- 테스트 확인 포인트입니다.\n"
                    "[보고서 종료]"
                )
            }
        ).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        with patch.dict(
            os.environ,
            {
                "REPORT_LLM_ENABLED": "true",
                "OPENAI_API_KEY": "test-key",
                "REPORT_LLM_MODEL": "gpt-5",
                "REPORT_LLM_MODEL_DAILY": "gpt-5",
                "REPORT_LLM_SECTIONED_DAILY": "false",
            },
            clear=False,
        ), patch("analytics.llm_report_writer.urllib.request.urlopen", return_value=fake_response) as mocked_urlopen:
            text, meta = render_report(payload, prefer_llm=True)

        self.assertIn("1. 오늘의 한 줄 결론", text)
        self.assertIn("[카카오골프 일간 브리핑] 2026-03-13", text)
        self.assertTrue(meta["used_llm"])
        self.assertEqual(meta["model"], "gpt-5")
        self.assertEqual(mocked_urlopen.call_count, 1)

    def test_extract_response_text_from_output_items(self):
        text = _extract_response_text(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "첫 줄"},
                            {"type": "output_text", "text": "둘째 줄"},
                        ]
                    }
                ]
            }
        )
        self.assertEqual(text, "첫 줄\n둘째 줄")

    def test_get_model_for_report_type_prefers_specific_env(self):
        with patch.dict(
            os.environ,
            {
                "REPORT_LLM_MODEL": "gpt-5-mini",
                "REPORT_LLM_MODEL_DAILY": "gpt-5-mini",
                "REPORT_LLM_MODEL_WEEKLY": "gpt-5",
            },
            clear=False,
        ):
            self.assertEqual(get_model_for_report_type("weekly"), "gpt-5")
            self.assertEqual(get_model_for_report_type("daily"), "gpt-5-mini")

    def test_validate_rendered_report_requires_terminator(self):
        text = (
            "1. 오늘의 한 줄 결론\n"
            "- 결론.\n\n"
            "2. 오늘의 가격 변화\n"
            "- 수치.\n\n"
            "3. 오늘의 판매 흐름 변화\n"
            "- 없음.\n\n"
            "4. 베르힐CC 오늘 포인트\n"
            "- 없음.\n\n"
            "5. 오늘의 핵심 액션\n"
            "- 없음.\n\n"
            "6. 내일 확인 포인트\n"
            "- 설명."
        )
        self.assertEqual(_validate_rendered_report(text, "daily"), "missing_terminator")

    def test_finalize_rendered_report_adds_title_and_sanitizes_internal_labels(self):
        payload = {"report_type": "daily", "report_date": "2026-03-14"}
        raw = (
            "1. 오늘의 한 줄 결론\n"
            "광주CC (priority_score: 100, severity: high)\n"
            "hold 46, strong/weak/none 0\n"
            "[보고서 종료]"
        )
        finalized = _finalize_rendered_report(raw, payload)
        self.assertIn("[카카오골프 일간 브리핑] 2026-03-14", finalized)
        self.assertIn("(우선순위 높음)", finalized)
        self.assertIn("판단보류 46", finalized)
        self.assertNotIn("priority_score", finalized)
        self.assertNotIn("severity", finalized)

    def test_render_report_uses_sectioned_daily_generation(self):
        payload = {
            "report_type": "daily",
            "report_date": "2026-03-13",
            "summary": {"total_rows": 10, "total_courses": 1, "total_slots": 10, "promo_slots": 0, "promo_ratio": 0.0, "price_change_events": 0, "price_response_events": 0, "top_signals": []},
            "actions": [],
            "evidence": {
                "metric_glossary": [{"metric": "기본 체급", "description": "설명", "interpretation": "해석"}],
                "price_change_watch": {"total": 0, "by_type": {}},
                "discount_response": {"strong_count": 0, "weak_count": 0, "none_count": 0},
            },
            "risks": [],
            "recommendations": [],
            "course_focus": [],
        }

        responses = []
        for text in (
            "1. 오늘의 한 줄 결론\n- 결론.\n\n2. 오늘의 가격 변화\n- 수치.",
            "3. 오늘의 판매 흐름 변화\n- 없음.\n\n4. 베르힐CC 오늘 포인트\n- 없음.",
            "5. 오늘의 핵심 액션\n- 없음.\n\n6. 내일 확인 포인트\n- 설명.\n[보고서 종료]",
        ):
            fake_response = MagicMock()
            fake_response.read.return_value = json.dumps({"output_text": text}).encode("utf-8")
            fake_response.__enter__.return_value = fake_response
            fake_response.__exit__.return_value = False
            responses.append(fake_response)

        with patch.dict(
            os.environ,
            {
                "REPORT_LLM_ENABLED": "true",
                "OPENAI_API_KEY": "test-key",
                "REPORT_LLM_MODEL": "gpt-5",
                "REPORT_LLM_SECTIONED_DAILY": "true",
            },
            clear=False,
        ), patch("analytics.llm_report_writer.urllib.request.urlopen", side_effect=responses) as mocked_urlopen:
            text, meta = render_report(payload, prefer_llm=True)

        self.assertTrue(meta["used_llm"])
        self.assertIn("1. 오늘의 한 줄 결론", text)
        self.assertIn("6. 내일 확인 포인트", text)
        self.assertEqual(mocked_urlopen.call_count, 3)

    def test_render_report_uses_sectioned_weekly_generation(self):
        payload = {
            "report_type": "weekly",
            "report_date": "2026-03-13",
            "summary": {"observed_days": 7, "courses_analyzed": 8, "total_slots": 100, "promo_ratio": 0.2},
            "actions": [{"course_name": "광주CC", "action": "가격 유지", "reason": "방어 우선"}],
            "evidence": {
                "metric_glossary": [{"metric": "기본 체급", "description": "설명", "interpretation": "해석"}],
                "indices": {"price_defense_index": [{"course_name": "광주CC", "value": 1.2, "label": "높음"}]},
                "strategy_profiles": [{"course_name": "광주CC"}],
            },
            "risks": [{"message": "데이터 한계"}],
            "recommendations": [{"course_name": "광주CC", "recommendation": "유지"}],
            "course_focus": [{"course_name": "광주CC", "headline": "방어"}],
        }

        responses = []
        for text in (
            "1. 주간 총평\n- 결론.\n\n2. 가격 변화 요약\n- 변화.",
            "3. 판매 흐름 요약\n- 흐름.\n\n4. 베르힐CC 집중 분석\n- 분석.",
            "5. 경쟁 골프장 비교\n- 비교.\n\n6. 핵심 운영 액션\n- 액션.",
            "7. 다음 주 확인 포인트\n- 확인.\n[보고서 종료]",
        ):
            fake_response = MagicMock()
            fake_response.read.return_value = json.dumps({"output_text": text}).encode("utf-8")
            fake_response.__enter__.return_value = fake_response
            fake_response.__exit__.return_value = False
            responses.append(fake_response)

        with patch.dict(
            os.environ,
            {
                "REPORT_LLM_ENABLED": "true",
                "OPENAI_API_KEY": "test-key",
                "REPORT_LLM_MODEL_WEEKLY": "gpt-5.2-pro",
                "REPORT_LLM_SECTIONED_WEEKLY": "true",
            },
            clear=False,
        ), patch("analytics.llm_report_writer.urllib.request.urlopen", side_effect=responses) as mocked_urlopen:
            text, meta = render_report(payload, prefer_llm=True)

        self.assertTrue(meta["used_llm"])
        self.assertEqual(meta["model"], "gpt-5.2-pro")
        self.assertIn("1. 주간 총평", text)
        self.assertIn("6. 핵심 운영 액션", text)
        self.assertEqual(mocked_urlopen.call_count, 4)


if __name__ == "__main__":
    unittest.main()
