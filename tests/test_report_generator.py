import unittest

from analytics.report_generator import generate_daily_brief, render_daily_text_report
from analytics.report_payload_builder import build_daily_report_payload


class ReportGeneratorTests(unittest.TestCase):
    def test_generate_daily_brief_includes_core_sections(self):
        text = generate_daily_brief(
            total_rows=123,
            change_summary={
                "total": 2,
                "by_type": {"인하": 1, "인상": 0, "특가부착": 1, "특가해제": 0},
                "biggest_cut": {
                    "course_name": "테스트CC",
                    "play_date": "2026-03-20",
                    "tee_time": "07:10",
                    "delta_price_krw": -10000,
                },
            },
            agg_summary={
                "courses": {
                    "테스트CC": {"total_slots": 10, "promo_slots": 3, "avg_price": 90000, "min_price": 80000},
                }
            },
            rule_summary={
                "high_defense": [
                    {
                        "course_name": "테스트CC",
                        "play_date": "2026-03-20",
                        "part_type": "1부",
                        "open_slots": 2,
                        "min_price_krw": 90000,
                    }
                ],
                "actions": [
                    {
                        "priority_rank": 1,
                        "priority_score": 80,
                        "severity": "high",
                        "action": "가격유지",
                        "course_name": "테스트CC",
                        "play_date": "2026-03-20",
                        "part_type": "1부",
                        "reason": "무특가 저잔여",
                    }
                ],
                "repeat_discount": [
                    {
                        "course_name": "테스트CC",
                        "play_date": "2026-03-21",
                        "part_type": "2부",
                        "signal": "당일특가집중",
                        "signal_ratio": 0.75,
                    }
                ],
                "premium_candidates": [],
                "price_response": [],
                "member_open_alerts": [
                    {
                        "course_name": "해피니스",
                        "play_date": "2026-03-22",
                        "slot_count": 4,
                        "promo_flag": 1,
                        "min_price_krw": 88000,
                        "max_price_krw": 105000,
                    }
                ],
            },
            report_date="2026-03-13",
        )

        self.assertIn("[카카오골프 일간 브리핑] 2026-03-13", text)
        self.assertIn("1. 오늘의 한 줄 결론", text)
        self.assertIn("2. 오늘의 가격 변화", text)
        self.assertIn("4. 베르힐CC 오늘 포인트", text)
        self.assertIn("6. 내일 확인 포인트", text)
        self.assertIn("[보고서 종료]", text)

    def test_render_daily_text_report_uses_payload_actions(self):
        payload = build_daily_report_payload(
            report_date="2026-03-13",
            total_rows=50,
            change_summary={"total": 0, "by_type": {}, "biggest_cut": None},
            agg_summary={"courses": {"베르힐": {"total_slots": 8, "promo_slots": 0, "avg_price": 110000, "min_price": 110000}}, "member_opens_today": []},
            prev_agg_summary={"courses": {"베르힐": {"total_slots": 8, "promo_slots": 1, "avg_price": 112000, "min_price": 108000}}, "member_opens_today": []},
            rule_summary={
                "high_defense": [{"course_name": "베르힐", "play_date": "2026-03-20", "part_type": "1부", "open_slots": 2, "min_price_krw": 110000}],
                "repeat_discount": [],
                "price_response": [],
                "premium_candidates": [],
                "member_open_alerts": [],
                "actions": [
                    {
                        "priority_rank": 1,
                        "priority_score": 76,
                        "severity": "high",
                        "action": "가격유지",
                        "course_name": "베르힐",
                        "play_date": "2026-03-20",
                        "part_type": "1부",
                        "reason": "무특가 저잔여",
                    }
                ],
                "risks": [],
            },
            prev_rule_summary={
                "actions": [
                    {
                        "priority_rank": 1,
                        "priority_score": 60,
                        "severity": "medium",
                        "action": "추가관찰",
                        "course_name": "베르힐",
                        "play_date": "2026-03-19",
                        "part_type": "1부",
                        "reason": "비교용 전일 데이터",
                    }
                ]
            },
            strategy_profile={
                "profiles": [
                    {
                        "course_name": "베르힐",
                        "base_tier": {"grade": "A", "score": 90.0},
                        "discount_dependency": {"label": "낮음", "value": 0.05},
                        "discount_amplification": {"label": "보통", "value": 40.0},
                    }
                ],
                "glossary": [{"metric": "기본 체급", "description": "설명", "interpretation": "해석"}],
            },
        )

        text = render_daily_text_report(payload)

        self.assertIn("4. 베르힐CC 오늘 포인트", text)
        self.assertIn("베르힐CC", text)
        self.assertIn("가격유지", text)
        self.assertIn("112,000원 → 110,000원", text)


if __name__ == "__main__":
    unittest.main()
