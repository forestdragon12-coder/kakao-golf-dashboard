# 카카오골프 Rule Engine 출력 규격
> 구현 직전 상세 설계 | 2026-03-13

## 1. 목적

이 문서는 `rule_engine.py`가 반환해야 하는 표준 구조와
액션/우선순위 계산 규칙을 정의한다.

---

## 2. Top-level 구조

```json
{
  "date": "2026-03-13",
  "actions": [],
  "signals": {
    "high_defense": [],
    "repeat_discount": [],
    "price_response": [],
    "premium_candidates": [],
    "member_open_alerts": []
  },
  "summary_counts": {
    "high_defense": 3,
    "repeat_discount": 5,
    "price_response": 2,
    "premium_candidates": 1,
    "member_open_alerts": 1
  },
  "risks": []
}
```

---

## 3. Action 객체 규격

```json
{
  "priority_rank": 1,
  "priority_score": 87,
  "severity": "high",
  "action": "추가할인검토",
  "course_name": "푸른솔장성",
  "play_date": "2026-03-18",
  "part_type": "2부",
  "course_sub": "힐",
  "membership_type": "대중제",
  "reason": "특가 반복에도 잔여 해소 미진",
  "source_signal": "repeat_discount",
  "evidence": {
    "open_slots": 11,
    "promo_ratio": 0.82,
    "response_grade": "없음",
    "repeated_weakness_score": 0.77,
    "avg_price_krw": 50000
  }
}
```

---

## 4. 액션 분류 규칙

### 4.1 가격유지

조건:
- 무특가
- 잔여 적음
- 평균 대비 가격 높거나 유지 수준

### 4.2 추가할인검토

조건:
- 특가/인하 이후에도 잔여 많음
- 할인 반응 약함 또는 없음
- 반복 약세 패턴 존재

### 4.3 관망

조건:
- 신호는 있으나 데이터 부족
- 1회성 이상치 가능성 큼

### 4.4 티수조정검토

조건:
- 동일 요일/파트/서브코스 반복 약세
- 할인에도 반응 약함
- 장기 누적 기준 구조적 약세

### 4.5 공급증가주의

조건:
- 회원제 신규 오픈
- 회원제 오픈과 대중제 약세가 동반

---

## 5. Priority Score 규칙

범위:
- 0~100

기본 점수 구성:
- 잔여 과다: 최대 +30
- 특가 비중 높음: 최대 +20
- 할인 반응 약함: 최대 +25
- 반복 약세도 높음: 최대 +15
- 회원제 공급 충격: 최대 +10

가격 유지 계열 점수:
- 무특가 저잔여: +35
- 평균보다 높은 가격: +20
- 반복 가격 방어: +20

보정:
- 데이터 부족 시 -15
- membership_type 혼재 해석 불명확 시 -10

severity 기준:
- `high`: 75 이상
- `medium`: 45 이상 74 이하
- `low`: 44 이하

---

## 6. source_signal 매핑

- `high_defense` → 주로 `가격유지`
- `repeat_discount` → 주로 `추가할인검토` 또는 `티수조정검토`
- `price_response` → `추가할인검토` 또는 `관망`
- `premium_candidates` → `가격유지`
- `member_open_alerts` → `공급증가주의`

---

## 7. Risks 출력 규격

```json
[
  {
    "risk_type": "insufficient_history",
    "severity": "medium",
    "message": "반복 약세 판정은 3회 이상 누적 이후 신뢰도 상승"
  }
]
```

---

## 8. 구현 순서

1. 기존 signal 결과 유지
2. signal → action 변환 레이어 추가
3. priority score 계산 함수 추가
4. risks 생성 추가
5. report_payload_builder에서 actions 중심으로 사용
