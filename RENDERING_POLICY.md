# 카카오골프 리포트 렌더링 정책
> 구현 직전 상세 설계 | 2026-03-13

## 1. 목적

동일 payload를 텔레그램 / 이메일 / PDF / 콘솔에 맞게
일관되게 렌더링하는 규칙을 정의한다.

---

## 2. 공통 원칙

- 내용 우선순위는 `summary → actions → evidence → risks → recommendations`
- 같은 payload라도 채널에 따라 길이만 다르게 한다
- action 순서는 priority_rank를 유지한다
- 수치는 payload 값을 그대로 사용한다

---

## 3. 텔레그램 렌더링

목적:
- 가장 짧고 빠른 운영 브리핑

제한:
- 핵심 20줄 내외
- action 최대 5개
- course_focus 최대 5개

포함 항목:
- summary
- top actions
- 핵심 price change / response / member open
- 짧은 risks

생략 가능:
- 긴 evidence 상세
- 모든 course_focus 전체

문체:
- 짧고 단단함

---

## 4. 이메일 렌더링

목적:
- 운영 회의 공유용

제한:
- 중간 길이
- action 최대 10개
- course_focus 전체 가능

포함 항목:
- summary
- actions
- evidence
- risks
- recommendations

문체:
- 서술형 + 리스트 혼합

---

## 5. PDF 렌더링

목적:
- 월간/연간 문서 보관 및 보고

제한:
- 가장 긴 형식
- 차트/표 포함 가능

포함 항목:
- 전 섹션
- 부록 지표
- 지수 비교
- 월간/연간 해석

문체:
- 정제된 보고서형

---

## 6. 콘솔 렌더링

목적:
- 실행 직후 빠른 확인

제한:
- 섹션 요약 위주
- 핵심 action과 counts만 우선

포함 항목:
- summary counts
- top actions 3~5개
- critical risks

---

## 7. 생략 규칙

### 데이터 부족 시

- 없는 섹션을 억지로 만들지 않는다
- 대신 `데이터 부족`, `누적 부족`, `판단 보류` 문구를 출력

### 섹션 우선순위

1. actions
2. risks
3. summary
4. evidence
5. recommendations
6. course_focus

채널 길이가 제한되면 뒤에서부터 생략한다.

---

## 8. 구현 메모

- `report_generator.py`는 deterministic renderer 역할을 유지한다.
- 이후 `renderers/telegram.py`, `renderers/email.py`, `renderers/pdf.py`로 분리 가능하다.
- LLM 출력도 최종적으로는 이 정책에 맞춰 재조합한다.
