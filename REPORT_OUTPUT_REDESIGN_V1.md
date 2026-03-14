# 보고서 출력 포맷 개편안
> 장기 누적 운영 기준 | 2026-03-14

## 1. 목적

현재 보고서는 변화 보고와 현재 구조 보고가 섞이고,
같은 설명이 여러 섹션에 반복된다.
이 문서는 장기 누적 데이터에 맞는 2층 구조 보고서 포맷을 정의한다.

## 2. 개편 원칙

- 상단은 빠른 운영 판단용
- 하단은 근거 확인용
- 변화 보고와 현재 구조 보고를 분리
- 베르힐은 항상 고정 블록 유지
- 같은 설명은 한 번만 쓰고, 다른 섹션은 참조 구조로 압축

## 3. 2층 구조

### 3.1 상단 요약층

항상 아래 3개 블록을 고정한다.

- 이번 기간 한 줄 결론
- 베르힐 핵심 포인트
- 핵심 액션 3~5개

### 3.2 하단 근거층

항상 아래 3개 블록을 고정한다.

- 세부 근거
- 코스별 로그
- 데이터 한계

## 4. 변화 보고와 현재 구조 보고 분리

주간 이상 보고서는 아래 두 섹션을 분리한다.

### 4.1 `weekly_change_section`

여기에만 넣는 내용:

- 이번 기간 가격 인하/유지/특가 개입
- 가격 변화 후 판매 반응
- 할인 효과가 붙은 구간
- 할인했는데도 반응이 약한 구간

### 4.2 `current_structure_section`

여기에만 넣는 내용:

- 현재 가격 방어력
- 현재 할인 의존도
- 현재 공급 충격
- 현재 경쟁 대비 위치

금지 규칙:

- 변화 섹션에서 구조 지표를 장문 해설하지 않는다.
- 구조 섹션에서 "이번 주 가격을 몇 번 내렸다" 같은 이벤트를 반복하지 않는다.

## 5. 권장 상단 포맷

### 5.1 일간

1. 오늘의 한 줄 결론
2. 베르힐 핵심 포인트
3. 오늘의 핵심 액션

### 5.2 주간

1. 이번 주 한 줄 결론
2. 베르힐 핵심 포인트
3. 핵심 액션 3~5개
4. 다음 주 확인 포인트

## 6. 권장 하단 포맷

### 6.1 변화 보고 블록

- 가격 유지 골프장
- 가격 인하/특가 개입 골프장
- 할인 후 판매 가속 구간
- 할인 반응 약세 구간

### 6.2 현재 구조 블록

- 가격 유지형
- 할인 개입형
- 할인 의존형
- 할인 실효 낮음형

### 6.3 액션 블록

- 가격 유지 가능 구간
- 할인 검토 구간
- 할인 효과 재검토 구간
- 공급 공개/배정 점검 구간
- 프로모션 메시지 정합화 구간

## 7. 압축 규칙

현재 구조의 문제는 같은 설명을 여러 번 반복하는 것이다.
아래 압축 규칙을 고정한다.

### 규칙 1

같은 숫자 조합은 첫 등장 1회만 풀어쓴다.
이후 섹션에서는 "상단 변화 요약 참조" 형태로 줄인다.

### 규칙 2

같은 코스가 여러 액션에 걸리면
원인 축이 다를 때만 분리한다.

### 규칙 3

`관측 / 해석 / 액션 / 신뢰수준` 템플릿은 유지하되
모든 문단에 강제하지 않는다.

권장 적용:

- 상단 요약층: `관측 + 액션`
- 하단 근거층: `관측 + 해석 + 액션 + 신뢰수준`

### 규칙 4

결측 설명은 하단 `데이터 한계`로 모은다.
본문 중간에 `판단보류`, `산출 불가`를 남발하지 않는다.

## 8. 베르힐 전용 출력 블록

베르힐은 항상 별도 블록으로 고정한다.

최소 출력 항목:

- 가격 변화 추이
- 1부 판매 흐름
- 2부 판매 흐름
- 경쟁 대비 가격 위치
- 가격 유지 가능 구간
- 할인 검토 구간
- 할인 효과 재검토 구간

권장 출력 순서:

1. 이번 기간 베르힐 한 줄 결론
2. 1부
3. 2부
4. 경쟁 대비 위치
5. 운영 액션

## 9. payload 구조 개편안

```json
{
  "top_summary_section": {},
  "weekly_change_section": {},
  "current_structure_section": {},
  "berhill_focus_section": {},
  "action_section": {},
  "data_limitations_section": {}
}
```

### 9.1 `top_summary_section`

- `one_line_conclusion`
- `berhill_headline`
- `priority_actions`

### 9.2 `weekly_change_section`

- `price_change_summary`
- `discount_intervention_summary`
- `response_after_change_summary`

### 9.3 `current_structure_section`

- `course_type_map`
- `price_defense_snapshot`
- `discount_dependency_snapshot`
- `competitive_position_snapshot`

### 9.4 `berhill_focus_section`

- `price_trend`
- `part1_flow`
- `part2_flow`
- `competitive_position`
- `recommended_actions`

### 9.5 `action_section`

- `hold_segments`
- `discount_test_segments`
- `discount_recheck_segments`
- `supply_check_segments`
- `promo_alignment_segments`

### 9.6 `data_limitations_section`

- `observation_window_limit`
- `matching_limit`
- `response_data_limit`

## 10. 운영 전환 순서

1. payload를 위 6개 섹션으로 먼저 분리
2. fallback renderer를 2층 구조로 변경
3. LLM prompt를 동일 섹션 구조로 맞춤
4. 주간 보고서부터 적용
5. 월간/연간은 같은 구조로 확장

