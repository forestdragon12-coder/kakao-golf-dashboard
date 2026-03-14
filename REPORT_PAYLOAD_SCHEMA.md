# 카카오골프 리포트 Payload 스키마
> 구현 직전 상세 설계 | 2026-03-13

## 1. 목적

이 문서는 LLM 및 deterministic renderer에 전달할
구조화 payload 형식을 정의한다.

원칙:
- raw snapshot을 직접 전달하지 않는다
- 숫자/비율/우선순위는 모두 코드에서 계산한다
- LLM은 payload를 해석하고 문장화만 한다

---

## 2. 공통 Top-level 구조

모든 보고서는 아래 최상위 구조를 사용한다.

```json
{
  "report_type": "daily|weekly|monthly|yearly",
  "report_date": "2026-03-13",
  "generated_at": "2026-03-13T22:00:00+09:00",
  "data_window": {
    "start_date": "2026-03-01",
    "end_date": "2026-03-13",
    "observed_days": 13,
    "is_partial_window": true
  },
  "data_quality": {
    "coverage_score": 0.82,
    "missing_days": 2,
    "missing_courses": ["광주CC"],
    "confidence_note": "반응 분석은 누적 데이터 부족"
  },
  "summary": {},
  "actions": [],
  "evidence": {},
  "risks": [],
  "recommendations": [],
  "course_focus": [],
  "llm_constraints": []
}
```

---

## 3. 공통 필드 정의

### 3.1 summary

보고서의 핵심 수치 및 핵심 해석 전 단계 요약.

```json
{
  "total_courses": 8,
  "total_slots": 3950,
  "promo_slots": 884,
  "promo_ratio": 0.22,
  "price_change_events": 4,
  "price_response_events": 2,
  "member_open_events": 1,
  "top_signals": [
    "푸른솔장성 2부 약세",
    "베르힐 가격 방어 양호",
    "해피니스 회원제 공급 증가"
  ]
}
```

### 3.2 actions

운영자가 바로 볼 액션 리스트. 우선순위 기준 내림차순 정렬 필수.

```json
[
  {
    "priority_rank": 1,
    "priority_score": 87,
    "severity": "high",
    "action": "추가할인검토",
    "course_name": "푸른솔장성",
    "play_date": "2026-03-18",
    "part_type": "2부",
    "course_sub": "힐",
    "reason": "특가 반복에도 잔여 해소 미진",
    "evidence": {
      "open_slots": 11,
      "promo_ratio": 0.82,
      "response_grade": "없음",
      "repeated_weakness_score": 0.77
    }
  }
]
```

### 3.3 risks

시스템/데이터/해석상 주의점.

```json
[
  {
    "risk_type": "data_shortage",
    "severity": "medium",
    "message": "할인 반응 평가는 3일 누적 이상부터 신뢰도 상승"
  }
]
```

### 3.4 recommendations

코드 기반 권고 항목. LLM은 문장만 다듬을 수 있다.

```json
[
  {
    "type": "pricing",
    "course_name": "베르힐",
    "recommendation": "가격유지",
    "basis": "무특가 저잔여가 반복 관측됨"
  }
]
```

### 3.5 course_focus

골프장별 핵심 포인트. 모든 보고서에서 사용.

```json
[
  {
    "course_name": "해피니스",
    "headline": "대중제/회원제 모두 특가 집중",
    "signals": ["promo_heavy", "member_open"],
    "key_metrics": {
      "total_slots": 489,
      "promo_ratio": 1.0,
      "member_open_events": 1
    }
  }
]
```

---

## 4. 일간 보고서 payload

### 4.1 목적

오늘 즉시 실행할 액션 중심.

### 4.2 필수 블록

```json
{
  "report_type": "daily",
  "summary": {
    "total_slots": 3950,
    "promo_ratio": 0.22,
    "price_change_events": 0,
    "price_response_events": 0,
    "member_open_events": 0,
    "top_signals": []
  },
  "actions": [],
  "evidence": {
    "price_change_watch": {
      "total": 0,
      "by_type": {"인하": 0, "인상": 0, "특가부착": 0, "특가해제": 0},
      "largest_cut": null
    },
    "discount_response": {
      "strong_count": 0,
      "weak_count": 0,
      "none_count": 0
    },
    "member_open_signals": [],
    "course_board": []
  },
  "risks": [],
  "recommendations": [],
  "course_focus": []
}
```

### 4.3 course_board 구조

```json
[
  {
    "course_name": "베르힐",
    "total_slots": 442,
    "promo_slots": 0,
    "promo_ratio": 0.0,
    "min_price_krw": 110000,
    "defense_signals": 3,
    "weakness_signals": 0,
    "member_open_flag": null
  }
]
```

---

## 5. 주간 보고서 payload

### 5.1 목적

반복 패턴과 다음 주 조정 포인트 제공.

### 5.2 필수 블록

```json
{
  "report_type": "weekly",
  "summary": {
    "observed_days": 7,
    "courses_analyzed": 8,
    "repeat_weak_slots": 9,
    "repeat_discount_slots": 6,
    "effective_discounts": 3,
    "ineffective_discounts": 4
  },
  "actions": [],
  "evidence": {
    "repeated_weak_slots": [],
    "discount_efficiency": [],
    "competitive_position": [],
    "member_supply_changes": []
  },
  "risks": [],
  "recommendations": [],
  "course_focus": []
}
```

### 5.3 repeated_weak_slots 구조

```json
[
  {
    "course_name": "푸른솔장성",
    "weekday_type": "평일",
    "part_type": "2부",
    "course_sub": "힐",
    "days_observed": 5,
    "weak_days": 4,
    "repeated_weakness_score": 0.8,
    "avg_open_slots": 8.4,
    "avg_promo_ratio": 0.71
  }
]
```

### 5.4 competitive_position 구조

```json
[
  {
    "course_name": "베르힐",
    "segment": "주말 1부",
    "avg_price_rank": 2,
    "defense_rank": 1,
    "discount_dependency_rank": 6,
    "position_label": "고가 방어형"
  }
]
```

---

## 6. 월간 보고서 payload

### 6.1 목적

정책/구조 수준 판단.

### 6.2 필수 블록

```json
{
  "report_type": "monthly",
  "summary": {
    "observed_days": 30,
    "courses_analyzed": 8,
    "market_type": "혼합",
    "high_risk_structural_slots": 14,
    "premium_windows": 9
  },
  "actions": [],
  "evidence": {
    "indices": {
      "price_defense_index": [],
      "discount_dependency_index": [],
      "false_discount_rate": [],
      "premium_acceptance_score": [],
      "supply_shock_score": []
    },
    "structural_weakness_map": [],
    "subcourse_dispersion": []
  },
  "risks": [],
  "recommendations": [],
  "course_focus": []
}
```

### 6.3 indices 구조

```json
[
  {
    "course_name": "베르힐",
    "value": 0.81,
    "grade": "strong",
    "label": "가격 방어 우수"
  }
]
```

---

## 7. 연간 보고서 payload

### 7.1 목적

다음 해 전략 설계용.

### 7.2 필수 블록

```json
{
  "report_type": "yearly",
  "summary": {
    "observed_months": 12,
    "courses_analyzed": 8,
    "dominant_market_pattern": "할인 의존 혼합형",
    "structural_weak_zones": 28,
    "premium_zones": 16
  },
  "actions": [],
  "evidence": {
    "seasonal_elasticity": [],
    "annual_price_policy_review": [],
    "discount_failure_analysis": [],
    "supply_strategy_review": [],
    "next_year_strategy_inputs": []
  },
  "risks": [],
  "recommendations": [],
  "course_focus": []
}
```

---

## 8. llm_constraints 기본값

모든 payload에는 아래 제약을 포함한다.

```json
[
  "수치를 변경하지 말 것",
  "action/severity/priority_score를 바꾸지 말 것",
  "payload에 없는 사실을 추가하지 말 것",
  "과장 표현을 쓰지 말 것",
  "데이터 부족 시 판단 보류를 명시할 것"
]
```

---

## 9. 구현 메모

- `report_payload_builder.py`는 이 문서를 기준으로 구현한다.
- 일간 payload부터 먼저 구현한다.
- LLM 비활성 상태에서도 동일 payload를 deterministic renderer가 사용할 수 있어야 한다.
