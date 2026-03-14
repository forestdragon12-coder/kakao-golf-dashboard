# 카카오골프 리포트 아키텍처 설계
> 운영 보고서 + LLM 개입 구조 설계 | 2026-03-13

## 1. 목적

이 문서는 카카오골프 데이터 기반 운영 보고서를
일간 / 주간 / 월간 / 연간 단위로 설계하고,
LLM이 개입해야 하는 정확한 위치를 정의한다.

핵심 원칙은 다음과 같다.

- 수치 계산은 코드가 한다
- 운영 판정은 룰 엔진이 한다
- LLM은 문장화와 해석 보조만 한다
- 보고서는 항상 `요약 → 액션 → 근거 → 리스크 → 제안` 순서로 구성한다

---

## 2. 전체 아키텍처

```text
tee_time_snapshots
  ↓
price_change_detector / price_response_detector / daily_aggregator
  ↓
rule_engine
  ↓
report_payload_builder
  ↓
LLM summarizer / explainer
  ↓
renderers (telegram / email / pdf / console)
```

### 역할 분리

#### A. 계산 계층
- 가격 변동
- 할인 반응
- 잔여 슬롯
- 특가 비중
- 회원제 오픈
- 반복 약세
- 프리미엄 허용도

이 계층은 deterministic 해야 한다.

#### B. 판단 계층
- 가격유지
- 추가할인검토
- 관망
- 티수조정검토
- 공급증가주의

이 계층도 deterministic 해야 한다.

#### C. 문장화 계층
- 운영자용 보고서
- 대표용 요약
- 이메일용 서술형 버전
- 텔레그램용 짧은 버전

이 계층에서만 LLM을 사용한다.

---

## 3. LLM 개입 원칙

### LLM을 사용하는 곳

1. 일간 요약 문장 생성
2. 주간 패턴 해석 문장 생성
3. 월간/연간 전략 서술 초안 생성
4. 같은 payload를 채널별 문체로 변환
5. 리스크/기회 설명 보강

### LLM을 사용하지 않는 곳

1. 가격변동 감지
2. 할인 반응 계산
3. 잔여/가격/특가 비율 계산
4. 우선순위 점수 계산
5. 액션 판정
6. 경고/주의 기준선 계산

### LLM 제약 조건

- 숫자를 바꾸지 말 것
- 액션 판정을 뒤집지 말 것
- 입력되지 않은 사실을 추론하지 말 것
- 과장 표현을 쓰지 말 것
- 데이터 부족 시 "판단 보류"를 명확히 표기할 것

---

## 4. 보고서 체계

### 4.1 일간 기본 보고서

목적:
- 오늘 즉시 대응할 운영 액션 결정

핵심 질문:
- 오늘 가장 위험한 슬롯은 어디인가
- 오늘 가격 유지 가능한 구간은 어디인가
- 오늘 새롭게 생긴 공급/할인 신호는 무엇인가

구성:
1. Executive Summary
2. Immediate Actions
3. Price Change Watch
4. Discount Response
5. Member Open Signals
6. Course Focus

LLM 역할:
- 전체 요약 3~5문장 생성
- 액션을 자연어로 정리
- 텔레그램용 짧은 문체로 압축

### 4.2 주간 중기 보고서

목적:
- 다음 주 가격/티 운영 조정

핵심 질문:
- 반복적으로 약한 요일/파트는 어디인가
- 어떤 할인은 먹히고 어떤 할인은 헛도는가
- 다음 주 선제 조정이 필요한 골프장은 어디인가

구성:
1. Weekly Summary
2. Repeated Weak Slots
3. Discount Efficiency
4. Competitive Position
5. Next Week Actions

LLM 역할:
- 반복 패턴을 서술형으로 해석
- 운영자가 읽기 쉬운 실행 제안 문장 생성

### 4.3 월간 장기 보고서

목적:
- 운영 구조와 가격 정책의 월간 성과 평가

핵심 질문:
- 어떤 약세가 일시적이 아니라 구조적인가
- 어떤 가격 정책이 실제로 효과 있었는가
- 어떤 구간은 더 비싸게 받아도 되는가

구성:
1. Monthly Overview
2. Price Defense Index
3. Discount Dependency Index
4. Structural Weakness Map
5. Course/Sub-course Insights
6. Policy Recommendations

LLM 역할:
- 인사이트 요약
- 정책 변경 제안 초안
- 경영자용 월간 해석 문장 생성

### 4.4 연간 최종 보고서

목적:
- 연간 운영 체질 평가와 다음 연도 전략 수립

핵심 질문:
- 올해 어떤 전략이 통했고 무엇이 실패했는가
- 우리 골프장은 가격 방어형인가 할인 의존형인가
- 내년 어떤 시간대/코스 구조를 수정해야 하는가

구성:
1. Annual Executive Review
2. Seasonal Elasticity
3. Premium Window Analysis
4. Discount Failure Analysis
5. Supply Strategy Review
6. Next-Year Strategy

LLM 역할:
- 연간 narrative 생성
- 전략 보고서 문장화
- 경영진용 핵심 메시지 압축

---

## 5. 공통 출력 구조

모든 보고서는 아래 5개 블록을 가진다.

1. summary
2. actions
3. evidence
4. risks
5. recommendations

이 순서는 고정한다.

---

## 6. 운영자 관점 차별화 지표

### 6.1 Price Defense Index

정의:
- 무특가 상태에서 잔여가 빠르게 줄어드는 정도

의미:
- 굳이 할인하지 않아도 되는 슬롯을 식별

### 6.2 Discount Efficiency Index

정의:
- 할인 후 D+1 / D+3 / D+5 내 슬롯 소진 반응

의미:
- 할인이 실제로 먹혔는지 판정

### 6.3 False Discount Rate

정의:
- 할인했지만 반응이 없었던 비율

의미:
- 관성적 할인 구간 식별

### 6.4 Repeated Weakness Score

정의:
- 동일 요일/파트/서브코스에서 잔여 과다가 반복된 정도

의미:
- 구조적 약세 시간대 탐지

### 6.5 Premium Acceptance Score

정의:
- 평균보다 비싼데도 잔여가 적은 비율

의미:
- 가격 인상 여지 식별

### 6.6 Supply Shock Score

정의:
- 회원제 오픈 시 대중제 잔여/특가 구조 변화

의미:
- 공급 증가 압력 해석

### 6.7 Sub-course Dispersion Score

정의:
- 같은 골프장 안에서도 코스별 소진력 차이

의미:
- 코스별 운영 차별화 근거

### 6.8 Timeband Fitness Score

정의:
- 1부 / 2부 / 오후별 반복 강약

의미:
- 티수 배치 조정 근거

---

## 7. 액션 분류

모든 운영 판단은 다음 다섯 가지 중 하나로 정규화한다.

- 가격유지
- 추가할인검토
- 관망
- 티수조정검토
- 공급증가주의

각 액션은 아래 필드를 가진다.

```json
{
  "severity": "high|medium|low",
  "action": "추가할인검토",
  "priority_score": 87,
  "reason": "특가 반복에도 잔여 해소 미진",
  "evidence": {
    "open_slots": 11,
    "promo_ratio": 0.82,
    "response_grade": "없음"
  }
}
```

---

## 8. 주기별 payload 설계 원칙

LLM에는 raw data를 주지 않고 payload만 준다.

payload는 아래 원칙을 따라야 한다.

- 숫자/비율은 모두 사전 계산해서 전달
- 액션과 우선순위는 이미 결정된 상태로 전달
- 해석이 필요한 맥락만 텍스트로 추가
- 데이터 부족 여부를 명시

주기별 payload는 다음 단계에서 별도 정의한다.

---

## 9. LLM 연동 설계

### 9.1 연동 위치

LLM은 다음 위치에만 연결한다.

```text
rule_engine
  ↓
report_payload_builder
  ↓
llm_report_writer
  ↓
renderers
```

즉, LLM은 `rule_engine` 뒤, `renderer` 앞에 위치한다.

다음 단계에는 절대 직접 연결하지 않는다.

- scraper
- price_change_detector
- price_response_detector
- daily_aggregator
- baseline 계산
- priority score 계산

### 9.2 모듈 분리 원칙

LLM 연동은 아래 세 모듈로 분리한다.

1. `report_payload_builder.py`
- 보고서용 구조화 데이터 생성
- 숫자, 비교, 액션, 우선순위, 리스크를 모두 코드로 확정

2. `llm_report_writer.py`
- payload를 입력받아 자연어 보고서 초안 생성
- 보고서 종류별 프롬프트 선택
- 모델 호출 실패 시 deterministic fallback 사용

3. `renderers`
- 텔레그램용 짧은 버전
- 이메일용 중간 버전
- PDF/문서용 긴 버전

### 9.3 주기별 연동 범위

#### 일간 보고서

LLM 개입:
- Executive Summary 3~5문장
- Immediate Actions 자연어 정리
- 데이터 부족 시 주의 문구 요약

코드 고정:
- 가격 변동 수치
- 액션 우선순위
- 위험 슬롯 선정
- 회원제 오픈 판정

운영 원칙:
- 일간은 속도와 일관성이 우선이므로 LLM 개입을 최소화한다.
- LLM 실패 시에도 deterministic 텍스트 보고서가 반드시 생성되어야 한다.

#### 주간 보고서

LLM 개입:
- 반복 패턴 해석
- 할인 효율 요약
- 다음 주 운영 포인트 3~5문장

코드 고정:
- 반복 약세 구간 추출
- 할인 효율 지표
- 경쟁 비교 수치
- 액션 후보 리스트

#### 월간 보고서

LLM 개입:
- 월간 운영 체질 해석
- 정책 효과 설명
- 가격 전략/할인 전략 변화 서술

코드 고정:
- Price Defense Index
- Discount Dependency Index
- False Discount Rate
- Premium Acceptance Score
- Structural Weakness Map

#### 연간 보고서

LLM 개입:
- 연간 narrative
- 시즌별 해석
- 내년 전략 초안
- 경영진용 요약문

코드 고정:
- 시즌별 지표
- 연간 누적 비교
- 연간 강약 구간
- 전략 근거 수치

### 9.4 LLM 출력 제약

모든 LLM 호출에는 아래 제약을 포함한다.

- 입력 숫자를 변경하지 말 것
- 액션 이름을 바꾸지 말 것
- 우선순위를 재정렬하지 말 것
- payload에 없는 사실을 추가하지 말 것
- 과장/광고성 표현 금지
- 데이터 부족 시 판단 보류를 명시할 것

### 9.5 실패 대응

LLM 호출 실패 시 아래 순서로 처리한다.

1. deterministic renderer로 즉시 fallback
2. 실패 로그 저장
3. 다음 보고 주기에는 재시도 가능

즉, LLM은 보고서 품질 향상 요소이지, 시스템 필수 경로가 아니다.

### 9.6 향후 설정 항목

추후 실제 연동 시 필요한 설정:

- `OPENAI_API_KEY`
- `REPORT_LLM_MODEL`
- `REPORT_LLM_ENABLED`
- `REPORT_LLM_TIMEOUT_SEC`
- `REPORT_LLM_MAX_TOKENS`

권장 정책:
- 기본값은 `REPORT_LLM_ENABLED=false`
- 일간은 짧은 토큰 제한
- 월간/연간만 상대적으로 큰 토큰 허용

### 9.7 구현 우선순위

1. `report_payload_builder.py`
2. deterministic renderer 유지
3. `llm_report_writer.py`
4. 일간 보고서 LLM 요약 연결
5. 주간/월간/연간 순차 확장

---

## 10. 구현 순서

1. report_payload_builder 추가
2. rule_engine 출력에 severity/action/priority_score/evidence 추가
3. 일간 보고서 text renderer 개편
4. 주간 payload/renderer 추가
5. 월간 payload/renderer 추가
6. 연간 payload/renderer 추가
7. LLM 연동 모듈 추가

---

## 11. 현재 상태와 다음 단계

현재 구현 완료:
- 일간 집계
- 가격 변동 감지
- 할인 반응 측정
- 회원제 오픈 감지
- 기본 브리핑 생성

다음 작업:
- payload 스키마 구체화
- 일간/주간/월간/연간 프롬프트 설계
- report_generator를 payload 기반 구조로 개편

참조 문서:
- `REPORT_PAYLOAD_SCHEMA.md`
- `REPORT_PROMPTS.md`
- `RULE_ENGINE_SPEC.md`
- `METRIC_DEFINITIONS.md`
- `RENDERING_POLICY.md`
