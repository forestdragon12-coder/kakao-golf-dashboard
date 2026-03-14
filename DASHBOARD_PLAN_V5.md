# 카카오골프 인터랙티브 대시보드 기획서 v5.0
> 2026-03-15 | V4.1 → V5 전면 개편: 타임머신 탐색 + AI 진단 아카이브 + LLM 자동화 + 스케줄링 정비

---

## V4 → V5 주요 변경 사항

| # | 항목 | V4 | V5 |
|---|------|----|----|
| 1 | 날짜 탐색 | "최근 N일" 상대 필터 | **기준일 앵커 + 범위** (과거 아카이브 탐색) |
| 2 | AI 진단 | 빌드 시 1회 계산 | **매일 DB 저장 → 날짜별 아카이브 로드** |
| 3 | LLM | 보고서 전용 (비활성) | **진단 파이프라인에 OpenAI 통합** |
| 4 | 스케줄링 | 스크래핑 + 보고서 4종 | **스크래핑 1종만 유지**, 보고서 폐기 |
| 5 | 디자인 | V2 혼합 스타일 | **V1 다크 프리미엄 테마 복원** |
| 6 | Tab 설명 | 없음 | **각 탭 상단 1~2줄 평문 설명** |
| 7 | 용어 | "서브코스" | **"코스"** (9홀 단위) |
| 8 | 03-13 데이터 | 포함 (오류) | **제거** |
| 9 | Tab 8 로딩 | fetch (file:// 실패) | **날짜별 분할 JSON + 당일 임베드** |
| 10 | 데이터 구조 | 전체 기간 집계 1벌 | **날짜 키 구조화** (탭별 날짜 인덱싱) |

---

## 0. 설계 전제

### 데이터 특성
- 매일 07:00 수집, D+1~D+30 경기일 대상, 8개 골프장
- 03-13 데이터는 course_sub 명명 불일치로 **전량 제거** (03-14부터 유효)
- 매진 슬롯은 카카오 페이지에서 제거됨 → 잔여 COUNT = available_slots
- 슬롯 소진 = 전일 대비 slot_identity_key 집합 차이로 계산
- 카카오골프 = 해당 골프장의 전체 예약 채널로 간주

### 핵심 보정 사항 9건 (V4 동일)

| # | 문제 | 해법 |
|---|------|------|
| 1 | 스크래퍼 장애 시 전량 소진으로 오판 | 전일 대비 70%+ 급감 = scraper_failure_flag, 소진 계산 제외 |
| 2 | Yield 기준가로 최초 관측가 사용 불가 | 세그먼트 기대가격(비할인 슬롯 중앙값) + 계단식 폴백 |
| 3 | 비할인 비교군 부재 | D-day 곡선 잔차법으로 할인 효과 추정 |
| 4 | course_sub 불안정 | course_variant 정규화 사전 적용 |
| 5 | 순소진 vs 총소진 혼동 | slot_identity_key 매칭: gross_consumed + gross_new 분리 |
| 6 | 취소 재등장과 신규 오픈 구분 불가 | 이력 기반 4상태 분류 (신규/재등장/소진/미오픈) |
| 7 | 날씨 교란으로 소진/할인 분석 왜곡 | 악천후 유형별(우천/폭염/강풍/한파/심각) 분리 처리 |
| 8 | 회원제 미오픈 기간이 전 지표 오염 | NOT_OPEN 상태 분리 + 전 분석 영역에서 제외 |
| 9 | 폭염 영향이 시간대별로 다름 | affected_parts 필드로 1부/2부 분리 보정 |

### 가격 표기 원칙
- **만원 단위**: 13.8만, 0.5만 (k 표기 사용하지 않음)
- 인상 이벤트: 인하보다 상세하게 표기 (감지일시, 경기일, 시간대, 코스, D-day)

### 용어 변경
- ~~서브코스~~ → **코스** (각 코스는 9홀 단위)
- 예: 베르힐의 Sky/Lake/Verthill은 각각 9홀 코스

### 세그먼트 기대가격 폴백 체인 (V4 동일)
```
1순위: 현재 세그먼트 비할인 슬롯 중앙값 (표본 5건+)
2순위: 직전 7일 동일 세그먼트 비할인 중앙값
3순위: 직전 30일 동일 세그먼트 비할인 중앙값
4순위: 동일 시즌 + 동일 요일유형 전체 기간 비할인 중앙값
5순위: 계산 불가 → "기준가 미확정" 표기, 관련 지표 회색 처리
```

### 회원제 슬롯 미오픈 처리 원칙 (V4 동일)
- 적용 대상: 골드레이크, 해피니스
- NOT_OPEN 상태 = 전 분석 영역에서 제외
- 오픈 감지 시 "회원제 오픈" 이벤트 마커 표시

### 악천후 유형별 처리 원칙 (V4 동일)
| 유형 | 영향 시간대 | Tab 1 경보 |
|------|-----------|-----------|
| 우천 | 전 시간대 | "강수 예보 — 취소 증가 대비" |
| 폭염 | 오후 2부 집중 | "폭염 예보 — 오후 2부 소진 둔화 예상" |
| 강풍 | 전 시간대 | "강풍 예보 — 전 시간대 위축" |
| 한파 | 새벽·오전 1부 | "한파 예보 — 1부 소진 약화 예상" |
| 심각 | 전 시간대 | "심각 기상 — 당일 전량 소진 분석 제외" |

---

## 1. 설정 (Settings)

### 1.1 기준 골프장 ("우리 골프장")
- 8개 중 단일 선택 → 전체 대시보드 관점 전환
- Tab 7 AI 진단: "우리" 최상단, 상세 표시
- 차트: "우리" = 강조색, 경쟁 = 회색 계열
- 설정값: localStorage 저장

### 1.2 경쟁 그룹 (선택)
- 비교 대상 골프장 지정 (기본: 나머지 전체)

---

## 2. 탭 구조 (9개)

```
Tab 1  오늘의 브리핑        — "우리" 중심, 어제 대비 변화 + 경보 + 액션
Tab 2  슬롯 생애주기        — 경기일 선택 → 슬롯별 가격/소진 타임라인
Tab 3  소진 패턴 매트릭스   — 요일 x 시간대 히트맵, 평일/주말 분리
Tab 4  가격 흐름 분석       — D-day x 가격 트렌드, 산개도
Tab 5A 할인 반응 분석       — D-day 보정 리프트 + 증분 소진 + 매출 환산
Tab 5B 수익 구조 분석       — Yield, 할인 비용, 소진 달성률
Tab 6  코스 x 회원제        — 9홀별 현황, 회원제/대중제 분리
Tab 7  AI 진단              — LLM 기반 서술형 진단 + 액션 추천
Tab 8  티타임 상세          — 슬롯 단위 전체 데이터
```

### 탭 설명 (각 탭 상단 고정 표시)

| 탭 | 설명 |
|----|------|
| Tab 1 | 오늘 수집된 8개 골프장의 가격, 잔여 티타임, 특가 현황을 한눈에 보여줍니다. |
| Tab 2 | 티타임 가격이 경기일이 가까워질수록 어떻게 변하는지 추적합니다. 어떤 골프장이 일찍 가격을 내리는지, 끝까지 버티는지 비교할 수 있습니다. |
| Tab 3 | 어떤 시간대의 티타임이 잘 팔리고, 어떤 시간대가 남는지 히트맵으로 보여줍니다. |
| Tab 4 | 실제로 가격이 바뀐 모든 이벤트를 보여줍니다. 인상인지 인하인지, 얼마나 바뀌었는지, 경기일까지 며칠 남았을 때 바뀌었는지 확인합니다. |
| Tab 5A | 특가나 할인이 붙은 뒤 실제로 예약이 늘었는지 추적합니다. 할인이 효과가 있었는지 데이터로 판단합니다. |
| Tab 5B | 정가 대비 실제 판매가가 몇 %인지 측정합니다. 수율이 높을수록 제값 받고 파는 것, 낮을수록 할인에 의존하는 것입니다. |
| Tab 6 | 각 골프장의 9홀 코스별 가격 차이와 회원제 오픈 현황을 비교합니다. |
| Tab 7 | 수집된 모든 데이터를 종합해 각 골프장의 가격 전략, 리스크, 운영 권고사항을 AI가 진단합니다. |
| Tab 8 | 개별 티타임 슬롯의 가격, 상태, 예약 여부를 날짜별로 확인합니다. |

설명 UI: `#1E293B` 배경, 좌측 `i` 아이콘, 폰트 11px, 색상 `#94A3B8`. 고정 영역.

---

## 3. 공통 UI 컴포넌트

### 3.1 날짜 탐색 시스템 (V5 신규 — V4 대비 전면 개편)

**V4의 한계**: "최근 N일" 상대 필터는 항상 오늘 기준. 과거 데이터 재탐색 불가.

**V5 개편**: 기준일 앵커 + 범위 선택 → 과거 어떤 시점이든 돌아갈 수 있는 타임머신 구조.

#### 구성 요소

```
┌─────────────────────────────────────────────────────────┐
│ 📅 기준일: [<] 2026-03-25 [>]   범위: [당일] [±3일] [±7일] [전체] │
│                                  ↑ 수집일 기준 (탭에 따라 변동)    │
└─────────────────────────────────────────────────────────┘
```

- **기준일 선택기**: 달력 팝업 또는 좌우 화살표(±1일). 기본값 = 오늘.
- **범위 확장**: 기준일 중심으로 앞뒤 확장. `[당일] [±3일] [±7일] [전체]`
  - 코드값 매핑: 당일=`"1d"`, ±3일=`"3d"`, ±7일=`"7d"`, 전체=`"all"`
- **시간 축 표시**: 탭 전환 시 `수집일 기준` 또는 `경기일 기준` 동적 표시.
- **데이터 빈 날짜 처리**: 스크래핑 장애 등으로 데이터가 없는 날짜를 선택한 경우:
  - 날짜 선택기에 유효 날짜만 활성화 (데이터 있는 날짜에 점 마커 표시)
  - 빈 날짜 선택 시 "해당 날짜의 수집 데이터가 없습니다" 메시지 + 가장 가까운 유효 날짜 링크
  - 범위 선택(±3일 등)에서 빈 날짜는 건너뛰고 존재하는 데이터만 사용

#### 탭별 시간 축 매핑

| 탭 | 주축 | 기준일의 의미 |
|----|------|-------------|
| Tab 1 (오늘 브리핑) | 수집일 | "그 날 수집한 현황" 재현 |
| Tab 2 (생애주기) | 경기일 | "그 경기일의 가격 변화 추적" |
| Tab 3 (소진 패턴) | 수집일 | "그 기간의 평균 소진 히트맵" |
| Tab 4 (가격 흐름) | 경기일 | "그 기간의 가격 변동 이벤트" |
| Tab 5A (할인 반응) | 경기일 | "그 기간의 할인 효과" |
| Tab 5B (수율 분석) | 경기일 | "그 기간의 수율 측정" |
| Tab 6 (코스·회원제) | 수집일 | "그 날의 코스별 현황" |
| Tab 7 (AI 진단) | 진단 실행일 | "그 날의 AI 진단 기록" |
| Tab 8 (상세 슬롯) | 수집일 | "그 날 수집된 슬롯 원시 데이터" |

#### SettingsContext 확장

```javascript
SettingsContext = {
  baseCourse: "골드레이크",      // 기준 골프장
  competitors: [...],            // 경쟁 그룹
  weekdayMode: "all",            // 전체/평일/주말
  anchorDate: "2026-03-25",      // 기준일 (V5 신규)
  rangeMode: "7d",               // "1d"=당일 / "3d"=±3일 / "7d"=±7일 / "all"=전체 (V5 신규)
}
```

### 3.2 글로벌 필터 (V4 계승)
- 골프장 선택 (멀티, 기준 골프장 기본 선택)
- 코스 선택 (선택된 골프장 기준 동적)
- 일정 유형: [전체] [평일] [주말]
- 파트 (1부/2부)
- 회원구분 (대중제/회원제/전체)
- 할인 상태 (할인/비할인/전체)

### 3.3 데이터 축적 대응 전략

| 축적 기간 | 표현 방식 |
|-----------|-----------|
| ~7일 | 일별 포인트 그래프, 테이블 중심 |
| 7~30일 | 일별 라인차트 + 주간 요약 KPI |
| 30~90일 | 주간 집계 라인 + 월간 요약 |
| 90일+ | 월간 집계, 시즌 비교, YoY |

차트 최적화:
- X축 날짜 14개 이상: interval 자동 조정 (매 2일 또는 매 주)
- 범위 내 날짜 14개 이상: dot 비활성화
- 가격 Y축: 항상 만원 단위

### 3.4 평일/주말 구조적 분리 (V4 동일)

| 구분 | 평일 (월~금) | 주말 (토~일) |
|------|-------------|-------------|
| 핵심 과제 | 안 팔리는 걸 파는 싸움 | 팔리는 걸 더 비싸게 파는 싸움 |
| 할인 의미 | 소진 자체가 목표 | 불필요한 할인 = 순수 손실 |
| 프리미엄 여력 | 낮음 | 높음 (특히 토 오전 1부) |

---

## 4. 날씨 데이터 연동 (V4 동일)

골프장별 기상청 단기예보 수집. 상세는 V4 §4 참조.
(COURSE_LOCATIONS, 악천후 분류, 예보 변동 추적 모두 그대로 유지)

---

## 5. 취소(재등장) 슬롯 구분 (V4 동일)

3상태 분류 (first_seen / reappeared / consumed) + NOT_OPEN. 상세는 V4 §5 참조.

---

## 6. Tab 1 ~ Tab 6 상세 (V4 계승)

Tab 1~6의 구성, 시각화, 로직은 **DASHBOARD_PLAN_V4.md §6~§12를 정본**으로 사용.
V4 문서는 삭제하지 않으며, 구현 시 V4+V5를 함께 참조한다.

V5 공통 변경이 모든 탭에 적용됨 (V4 내용을 덮어씌움):

- "서브코스" → "코스" 용어 변경
- 기준일 앵커 + 범위로 날짜 필터 교체
- v1 다크 프리미엄 테마 적용 (§10 참조)
- 탭 상단 설명 추가

### 탭 내부 레이아웃 원칙

V1(`golf_price_dashboard.jsx`)의 grid 구조를 기본으로 따른다:
- 2열 그리드: `gridTemplateColumns: "1fr 1fr"` (차트 2개 나란히)
- 풀 너비: `gridColumn: "1/-1"` (넓은 차트, 테이블)
- 카드 그리드: `gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))"` (코스 카드)
- KPI 카드: `display: flex, gap: 10, flexWrap: wrap` (가로 나열)
- 날짜 탐색기와 탭 설명은 각 탭 최상단에 추가

반응형: 화면 너비 768px 미만 시 단일 열로 전환 (`minmax(320px, 1fr)`).

---

## 7. Tab 7 — AI 진단 (V5 전면 개편)

### V4 → V5 변경 핵심

V4: 빌드 시 룰 엔진(A~J) 결과를 JSX에 나열. 1회성 정적 진단.
V5: 매일 스크래핑 후 룰 엔진 + LLM → DB 저장 → 날짜별 아카이브 로드.

### 7.1 진단 파이프라인

```
매일 07:00 스크래핑 완료
    |
    v
[analytics/diagnostics.py]
    |-- rule_engine.py 룰 A~J 실행 (결정론적)
    |-- strategy_profile.py 코스별 전략 유형 판별
    |-- 룰 결과 + DB 수치 → LLM 프롬프트 구성
    |-- OpenAI API 호출 (gpt-5.2) → 서술형 진단 생성
    |-- ai_diagnostics 테이블에 INSERT
    |-- (LLM 실패 시) 룰 엔진 결과 + 템플릿 텍스트로 fallback 저장
    |
    v
텔레그램 알림 (진단 요약 포함)
```

### 7.2 진단 룰 (V4 동일)

| 룰 | 조건 | 진단 | 제안 액션 |
|----|------|------|-----------|
| A | promo_flag=0 + 소진 빠름 | 가격 유지 여력 | 현 가격 유지 |
| B | 동일 세그먼트 반복 특가 | 할인 의존 | 할인 축소 테스트 |
| C | 인하 후 소진 가속 (lift>20%) | 할인 효과 있음 | 타이밍 최적화 |
| D | 인하 후 반응 미미 (lift<10%) | 할인 무효 | 할인 중단 검토 |
| E | 고가 + 비할인 + 빠른 소진 | 프리미엄 구간 | 인상 검토 |
| F | pax '3인 이상' 반복 | 특가 의존 | 4인 정가 전환 검토 |
| G | 대중제 한정 비교 | 공정 비교 전제 | — |
| H | 회원제 오픈 감지 | 공급 변화 | 가격 모니터링 |
| I | 악천후 + 잔여 과잉 | 날씨 리스크 | 선제 인하 또는 대기 |
| J | 취소 급증 감지 | 취소 리스크 | 재판매 가격 전략 검토 |

### 7.3 LLM 연동 상세

#### API 사양

기존 `llm_report_writer.py`가 **OpenAI Responses API** (`/v1/responses`)를 사용 중.
diagnostics.py도 동일 API를 사용한다. `_call_openai_responses_api()` 함수를 재활용.

```
엔드포인트: https://api.openai.com/v1/responses
인증: Bearer {OPENAI_API_KEY}
요청 구조: { "model": "gpt-5.2", "instructions": "...", "input": "...", "max_output_tokens": 6000 }
```

#### 프롬프트 설계

**시스템 프롬프트 (instructions)**:
```
당신은 광주/전남 지역 8개 골프장의 가격 전략을 분석하는 운영 컨설턴트입니다.
아래 데이터를 기반으로 두 가지 출력을 생성합니다.

[출력 1: 종합 브리핑]
- 2~3문단, 서술형
- 시장 전체 동향 요약 → 주요 이상 징후 → 핵심 액션 권고
- 숫자는 반드시 포함하되, 해석을 붙여 맥락을 제공

[출력 2: 코스별 전략 진단 (8개)]
각 코스에 대해 JSON 객체로:
{
  "course": "골드레이크",
  "strategy": "수요 강세형 (인상 기조)",
  "risk": "중간",
  "summary": "1~2문장 핵심",
  "details": "3~4문장 상세 분석",
  "recommendation": "1문장 권고",
  "alerts": [{"severity": "warning", "title": "...", "message": "...", "action": "..."}]
}

규칙:
- 가격은 만원 단위 (13.8만, 0.5만)
- 인하/인상 건수, 평균 변동률, D-day 구간 등 수치를 근거로 제시
- 추측이나 일반론 금지. 데이터에 없는 판단은 하지 않음
- 경쟁사 대비 맥락을 반드시 포함
```

**유저 프롬프트 (input)**:
Python이 자동 생성하는 구조화된 데이터 블록:
```
[분석일: 2026-03-15]
[데이터 범위: 수집일 2026-03-14~15, 경기일 2026-03-15~04-13]

== 룰 엔진 결과 ==
골드레이크: 룰A(가격유지여력) 통과, 룰E(프리미엄) 통과
어등산: 룰D(할인무효) 해당, 룰I(날씨리스크) 해당
...

== 코스별 핵심 수치 ==
골드레이크: 인상 150건, 인하 10건, 평균 +7.3%, D1~3 +7.6%, 가격범위 8만~22만
어등산: 인상 1건, 인하 80건, 평균 -8.8%, D14+ -10.6%, 가격범위 6.5만~17.5만
...

== 시장 전체 ==
총 변동 536건, 인하 311건(58%), 인상 225건(42%)
전일 대비 변화: 인하 +12건, 인상 -3건
```

#### 출력 파싱

LLM 응답을 파싱하여 ai_diagnostics 테이블에 분리 저장:
- `[출력 1]` → diagnosis_type='briefing', course_name='전체'
- `[출력 2]` JSON 파싱 → 코스별 diagnosis_type='strategy' + alerts

#### Fallback 텍스트 템플릿 (LLM 실패 시)

`report_generator.py`의 기존 로직을 재활용하여 결정론적 텍스트 생성:
```python
def fallback_diagnosis(course, rule_results, metrics):
    lines = [f"[{course}] 전략: {metrics['strategy_type']}"]
    for rule in rule_results:
        lines.append(f"  - 룰 {rule['code']}: {rule['label']} ({rule['detail']})")
    lines.append(f"  권고: {rule_results[0]['recommendation']}")
    return "\n".join(lines)
```

### 7.4 DB 저장 구조

```sql
CREATE TABLE ai_diagnostics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date   TEXT NOT NULL,          -- 진단 실행일 (2026-03-14)
    course_name     TEXT NOT NULL,          -- 골프장명 또는 "전체" (종합 브리핑)
    diagnosis_type  TEXT NOT NULL,          -- briefing / alert / strategy / action
    severity        TEXT,                   -- error / warning / info / NULL
    title           TEXT,                   -- 진단 제목
    content         TEXT NOT NULL,          -- 진단 본문 (서술형)
    details         TEXT,                   -- 상세 분석 (JSON)
    recommendation  TEXT,                   -- 권고사항
    rule_codes      TEXT,                   -- 적용된 룰 코드 (A,C,E 등)
    metrics         TEXT,                   -- 근거 수치 (JSON)
    llm_generated   BOOLEAN DEFAULT 0,     -- LLM 생성 여부 (0=fallback, 1=LLM)
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_diag_date ON ai_diagnostics(analysis_date);
CREATE INDEX idx_diag_course ON ai_diagnostics(course_name, analysis_date);
```

### 7.5 대시보드 로드 방식

`generate_dashboard_data.py`의 `get_tab7()`이 ai_diagnostics 테이블에서 날짜별 SELECT:

```python
def get_tab7(db):
    """날짜별 AI 진단 아카이브 로드"""
    rows = db.execute("""
        SELECT analysis_date, course_name, diagnosis_type,
               severity, title, content, details,
               recommendation, rule_codes, metrics, llm_generated
        FROM ai_diagnostics
        ORDER BY analysis_date DESC, course_name
    """).fetchall()

    # 날짜 키로 구조화
    result = {}
    for row in rows:
        date = row['analysis_date']
        if date not in result:
            result[date] = {
                'briefing': None,
                'alerts': [],
                'course_diagnosis': [],
                'actions': []
            }
        # diagnosis_type에 따라 분류
        ...
    return result
```

JSX에서 anchorDate에 해당하는 키의 진단을 표시. 없는 날짜는 "해당 날짜의 진단 기록이 없습니다" 표시.

### 7.6 Tab 7 UI 구성 (V1 스타일 복원)

**상단: 종합 AI 브리핑**
- 그라디언트 배경 카드 (`linear-gradient(135deg, #1E1B4B, #1E293B)`)
- 2~3문단 서술형 요약
- "8개 코스 중 n개에서 이상 징후 감지" 핵심 문장

**중단: 긴급 경보 카드** (severity=error/warning)
- 좌측 4px 색상 바 + 코스 뱃지 + 제목 + 설명 + 조치사항
- error=빨강, warning=주황, info=파랑

**하단: 코스별 전략 진단 카드** (클릭 확장형)
- 접힌 상태: 코스명 + 전략 유형 + 리스크 등급
- 펼친 상태: 상세 분석 + 권고 + 핵심 수치
- "내 골프장" = 상단 고정 + 하이라이트 보더

**사이드: 운영 우선순위 액션**
- 긴급/중요/검토/점검 뱃지 + 대상 코스 + 액션 1줄

### 7.7 Fallback 전략

| 상황 | 대응 |
|------|------|
| LLM 정상 응답 | 서술형 진단 저장 (llm_generated=1) |
| LLM 타임아웃/오류 | 룰 엔진 결과 + 템플릿 텍스트 저장 (llm_generated=0) |
| API 키 만료 | 에러 로그 + fallback 저장 + 텔레그램 경고 알림 |
| DB 저장 실패 | 파이프라인 전체를 죽이지 않음 (try/except) |

---

## 8. Tab 8 — 티타임 상세 (V5 개편)

### 30일 대응: 날짜별 분할 로드

문제: 30일 x 8,000슬롯/일 = 240,000행. 단일 JSON 60MB+.

해결:
- **당일 데이터**: `window.__GOLF_TAB8_TODAY__`로 HTML 임베드 (file:// 호환)
- **과거 데이터**: 날짜별 분할 JSON (`golf_tab8_20260314.json` 등)
- Tab 8 진입 시 기본 "오늘"만 표시
- 기준일 변경 시 해당 날짜 JSON 로드

빌드 시:
```python
def build_tab8_files(db):
    dates = get_all_collected_dates(db)
    for date in dates:
        slots = get_slots_by_date(db, date)
        write_json(f"golf_tab8_{date}.json", slots)

    # 최신 날짜는 HTML 임베드
    today_slots = get_slots_by_date(db, dates[-1])
    return today_slots  # window.__GOLF_TAB8_TODAY__ 에 삽입
```

### 필터
- 골프장, 코스, 경기일, 수집일, 시간대, 가격범위, 할인여부, 슬롯 상태

### 테이블 컬럼
- 골프장, 코스, 경기일, 티타임, 가격(만원), 할인여부, 프로모텍스트, D-day, 파트, 요일, 슬롯상태, 날씨

### 페이지네이션: 50건/페이지

---

## 9. 데이터 구조 — 날짜 키 인덱싱 (V5 신규)

### 기존 (V4): 전체 기간 집계 1벌
```javascript
window.__GOLF_DATA__ = {
  tab1: { kpi: {...}, events: [...] },    // 집계 1벌
  tab4: { scatter: [...], histogram: [...] },
  ...
}
```

### 개편 (V5): 날짜 키 구조화
```javascript
window.__GOLF_DATA__ = {
  tab1: {
    "2026-03-14": { kpi: {...}, events: [...] },
    "2026-03-15": { kpi: {...}, events: [...] },
    ...
  },
  tab3: {
    "2026-03-14": { heatmap: [...] },
    ...
  },
  tab4: [...],       // 이벤트 데이터는 이미 날짜 필드 포함 → 클라이언트 필터
  tab7: {
    "2026-03-14": { briefing: "...", alerts: [...], ... },
    "2026-03-15": { briefing: "...", alerts: [...], ... },
    ...
  },
  ...
}
```

JSX에서 anchorDate ± range에 해당하는 키들만 필터링 + 동적 집계.

### JSON 크기 추정 (30일)

| 탭 | V4 (집계) | V5 (30일 날짜별) |
|----|-----------|-----------------|
| Tab 1 | ~50KB | ~1.5MB |
| Tab 2 | ~30KB | ~30KB (이미 날짜별) |
| Tab 3 | ~20KB | ~600KB |
| Tab 4 | ~80KB | ~80KB (클라이언트 필터) |
| Tab 5A/5B | ~30KB | ~60KB |
| Tab 6 | ~20KB | ~600KB |
| Tab 7 | ~15KB | ~60KB |
| **합계** | **~478KB** | **~3MB** |

HTML 파일 약 4MB. 브라우저에서 문제없이 로드 가능.
Tab 8만 외부 JSON 분할(날짜별).

---

## 10. 디자인 시스템 — V1 다크 프리미엄 복원

### 색상 팔레트

```
배경 최심부:      #0F172A
카드 배경:        #1E293B
보조 배경:        #334155
텍스트 메인:      #E2E8F0
텍스트 보조:      #94A3B8
텍스트 약함:      #64748B
텍스트 강조:      #F1F5F9
강조 기본:        #4F46E5
AI 그라디언트:    linear-gradient(135deg, #1E1B4B, #1E293B)
```

### 코스 색상 (V1 확정)

```javascript
COURSE_COLORS = {
  "골드레이크": "#6366F1",
  "광주CC":    "#0EA5E9",
  "르오네뜨":   "#10B981",
  "무등산":    "#F59E0B",
  "베르힐":    "#EF4444",
  "어등산":    "#8B5CF6",
  "푸른솔장성": "#EC4899",
  "해피니스":   "#14B8A6"
}
```

### 이벤트/상태 색상

```javascript
EVENT_COLORS = { "인하": "#EF4444", "인상": "#10B981", "특가부착": "#F59E0B", "특가해제": "#6B7280" }
RISK_COLORS  = { "높음": "#EF4444", "중간": "#F59E0B", "낮음": "#10B981" }
PRIORITY_COLORS = { "긴급": "#EF4444", "중요": "#F59E0B", "검토": "#6366F1", "점검": "#94A3B8" }
```

### 컴포넌트 스타일

**KPI 카드**: `#1E293B` 배경, `borderRadius:12`, `borderLeft:4px solid ${color}`, 패딩 16px 20px

**차트 카드**: `#1E293B` 배경, `borderRadius:12`, 패딩 18px
- CartesianGrid: `stroke="#334155"`, `strokeDasharray="3 3"`
- Axis tick: `fill="#94A3B8"`, `fontSize:10`
- Tooltip: `#0F172A` 배경, `border:1px solid #334155`

**경보 카드**: `#0F172A` 배경, `borderLeft:4px solid ${severity_color}`, `borderRadius:10`

**탭 버튼**: pill 스타일 `borderRadius:20`
- active: `background:#4F46E5`, `color:#fff`
- inactive: `background:#1E293B`, `color:#94A3B8`, `border:1px solid #334155`

**헤더**: `font-size:20px`, `font-weight:800`, 우측 "LIVE" 뱃지

---

## 11. 스케줄링 시스템 (V5 전면 개편)

### 폐기 대상

| 작업 | plist ID | 상태 |
|------|----------|------|
| 주간보고서 | com.kakao.golf.report.weekly | **폐기** |
| 월간보고서 | com.kakao.golf.report.monthly | **폐기** |
| 연간보고서 | com.kakao.golf.report.yearly | **폐기** |

### 유지

| 작업 | plist ID | 주기 |
|------|----------|------|
| 스크래핑 + AI 진단 | com.kakao.golf.scraper | 매일 07:00 |

### 파이프라인 흐름 (run.py --mode collect)

```
[기존]
스크래핑 → DB저장 → price_change 감지 → daily_aggregator → 텔레그램

[V5 개편]
스크래핑 → DB저장 → price_change 감지 → daily_aggregator
    → AI 진단 생성/저장 (diagnostics.py)
    → 대시보드 빌드 (build_dashboard.py)
    → 텔레그램 (진단 요약 포함)
```

**중복 호출 방지**: run.py에서 이미 `evaluate_rules()`와 `build_daily_strategy_profiles()`를 호출한다.
diagnostics.py는 이 결과를 인자로 전달받아 재활용한다 (재호출하지 않음):
```python
# run.py 내부
diag_result = await run_diagnostics(
    rule_summary=rule_summary,            # 이미 계산됨
    strategy_profile=strategy_profile,    # 이미 계산됨
    change_summary=change_summary,        # 이미 계산됨
    agg_summary=agg_summary,              # 이미 계산됨
)
```

### .env 변경

```env
# ── 보고서 (폐기) ──
REPORTS_ENABLED=false
REPORT_LLM_ENABLED=false

# ── AI 진단 (V5 신규) ──
DIAGNOSTICS_ENABLED=true
DIAGNOSTICS_LLM_ENABLED=true
OPENAI_API_KEY=sk-proj-...(기존 키 유지)
DIAGNOSTICS_LLM_MODEL=gpt-5.2
DIAGNOSTICS_LLM_TIMEOUT_SEC=90
DIAGNOSTICS_LLM_MAX_TOKENS=6000
```

기존 보고서 관련 세분화 설정 20줄 → 불필요, 정리 대상.

### mac_scheduler_setup.sh 변경
- 보고서 plist 3개 생성 코드 제거
- 기존 등록된 plist unload 코드 추가
- 스크래퍼 plist만 유지

### 비용 추정
- 매일 1회 OpenAI 호출: ~7,000토큰/일
- gpt-5.2 기준: 약 $0.02~0.05/일, **월 $1~1.5**

---

## 12. 아키텍처 (V4 계승 + V5 확장)

**현재: A안 (Python → JSON → JSX 임베드)**

```
[매일 07:00]
run.py --mode collect
    → kakao_scraper.py (스크래핑)
    → database.py (DB 저장)
    → price_change_detector.py (변동 감지)
    → daily_aggregator.py (일별 집계)
    → diagnostics.py (AI 진단 → DB 저장)     ← V5 신규
    → build_dashboard.py (HTML + Tab8 JSON)  ← V5 신규
    → telegram_bot.py (알림)

[대시보드 빌드 (수동 또는 자동)]
generate_dashboard_data.py
    → 각 탭 데이터 날짜 키 구조화               ← V5 변경
    → ai_diagnostics 테이블에서 진단 로드       ← V5 신규
build_dashboard.py
    → golf_dashboard.html (React+Recharts 임베드, ~4MB)
    → golf_tab8_YYYYMMDD.json (날짜별 분할)    ← V5 변경
```

**90일+ 시 B안 전환 검토**: FastAPI 백엔드 + React 프론트

### 대시보드 빌드 자동화

대시보드 HTML은 데이터 수집 후 **자동 빌드**한다. 수동 실행하지 않는다.

```
run.py --mode collect 파이프라인:
  스크래핑 → DB저장 → 분석 → AI 진단 → 대시보드 빌드 → 텔레그램
```

run.py에 빌드 단계 추가:
```python
# 분석 파이프라인 끝, 텔레그램 전송 직전
try:
    from build_dashboard import build_all
    build_all()  # golf_dashboard.html + golf_tab8_*.json 생성
    logger.info("대시보드 빌드 완료")
except Exception as e:
    logger.error(f"대시보드 빌드 오류: {e}")
    # 빌드 실패해도 파이프라인은 계속 진행
```

### Tab 8 과거 데이터 file:// 프로토콜 대응

**문제**: 당일 데이터는 HTML 임베드로 file:// 호환이 되지만, 과거 날짜 JSON은 fetch로 로드해야 하며 file:// 에서 fetch가 차단된다.

**해결: 로컬 HTTP 서버 래퍼 스크립트**

```bash
#!/bin/bash
# open_dashboard.sh — 대시보드를 로컬 서버로 열기
cd "$(dirname "$0")"
PORT=8484
echo "대시보드 서버 시작: http://localhost:$PORT/golf_dashboard.html"
python3 -m http.server $PORT --bind 127.0.0.1 &
SERVER_PID=$!
sleep 1
open "http://localhost:$PORT/golf_dashboard.html"
# Ctrl+C로 종료
trap "kill $SERVER_PID 2>/dev/null" EXIT
wait $SERVER_PID
```

- Mac에서 `./open_dashboard.sh` 실행하면 로컬 서버가 뜨고 브라우저가 열림
- file:// 대신 http://localhost:8484 에서 동작 → fetch 정상 작동
- 당일 데이터는 여전히 HTML 임베드 (서버 없이도 최소 동작 보장)
- Tab 8에서 과거 날짜 선택 시 fetch 실패하면 "로컬 서버 모드에서 열어주세요" 안내 표시

### V4 문서 보존 원칙

V5의 §6에서 Tab 1~6 상세를 "V4 §6~§12 참조"로 위임한다. 따라서:
- **DASHBOARD_PLAN_V4.md는 삭제하지 않는다** — Tab 1~6 구현의 정본
- V5 공통 변경(용어, 날짜 탐색, 테마, 탭 설명)은 V4 내용을 덮어씌움
- 충돌 시 V5가 우선

---

## 13. 03-13 데이터 정비 (삭제 → 리매핑으로 변경)

### 원인
03-13 수집은 스크래퍼 초기 실행으로 course_sub 명명이 불안정:
- 르오네뜨: "그린피" → 실제는 IN/OUT (100% 불일치)
- 베르힐: None → 실제는 Sky/Lake/Verthill
- 골드레이크: "그린피" → 실제는 밸리/힐/골드/레이크
- 해피니스: None → 실제는 하트/힐링/히든/해피/휴먼

### 처리 (실행 완료)

전량 삭제 대신 course_sub 리매핑으로 데이터 보존:

| 골프장 | 03-13 course_sub | 처리 | 사유 |
|--------|-----------------|------|------|
| 광주CC | 동악/설산/섬진 | **유지** | 03-14와 동일 명명 |
| 무등산 | 인왕봉/지왕봉/천왕봉/선결제 | **유지** | 03-14와 동일 명명 |
| 어등산 | 송정/어등/하남 | **유지** | 03-14와 동일 명명 |
| 푸른솔장성 | 레이크/마운틴/None(85건) | **None→힐 리매핑** | 03-14에 힐 존재, 유일 누락 코스 |
| 골드레이크 | 그린피(418)/None(2) | **03-14 비율 분배** | 골드97/레이크107/밸리110/힐106 |
| 르오네뜨 | 그린피(299)/None(25) | **03-14 비율 분배** | IN167/OUT157 |
| 베르힐 | None(442) | **03-14 비율 분배** | Lake142/Sky139/Verthill161 |
| 해피니스 | None(485) | **03-14 비율 분배** | 하트137/해피44/휴먼35/히든147/힐링122 |

- **daily_summary**: course_sub 컬럼 없음 → 전량 유지 (코스 단위 집계는 정상)
- **분배 원칙**: 03-13 미분류 행을 03-14의 코스별 비율로 랜덤 배분 (seed=42 고정, 재현 가능)
- 백업: `data/golf_backup_20260315.db`

---

## 14. 변경 파일 목록

### 신규 생성

| 파일 | 설명 |
|------|------|
| `analytics/diagnostics.py` | AI 진단 오케스트레이터 (룰 엔진 → LLM → DB 저장) |
| `open_dashboard.sh` | 로컬 HTTP 서버 + 브라우저 오픈 래퍼 스크립트 |
| `DASHBOARD_PLAN_V5.md` | 본 기획서 |

### 수정

| 파일 | 변경 내용 |
|------|-----------|
| `run.py` | collect 파이프라인 끝에 diagnostics 호출 + build_dashboard 호출 추가 |
| `db/database.py` | ai_diagnostics 테이블 CREATE + INSERT 함수 |
| `.env` | DIAGNOSTICS_* 설정 추가, 보고서 설정 비활성화 |
| `mac_scheduler_setup.sh` | 보고서 plist 제거, 정리 코드 추가 |
| `generate_dashboard_data.py` | 날짜 키 구조화, get_tab7() ai_diagnostics SELECT |
| `build_dashboard.py` | Tab 8 날짜별 분할, 당일 임베드 |
| `golf_price_dashboard_v2.jsx` | V1 다크 테마 복원, 날짜 탐색 시스템, 탭 설명, 용어 변경 |

### 비활성화 (삭제하지 않음)

| 파일 | 상태 |
|------|------|
| `analytics/llm_report_writer.py` | 보고서 전용 → 비활성. diagnostics.py가 OpenAI 호출 코드 재활용 |
| `analytics/report_generator.py` | fallback 템플릿용으로 일부 재활용 |
| `analytics/report_payload_builder.py` | 비활성 |

---

## 15. 구현 우선순위

```
Phase 0 (즉시): 데이터 정비 + 인프라
  - 03-13 데이터 제거 (tee_time_snapshots 3950행 + daily_summary 225행)
  - ai_diagnostics 테이블 생성
  - .env 설정 변경 (DIAGNOSTICS_* 추가)
  - 보고서 LaunchDaemon 3개 unload
  - open_dashboard.sh 스크립트 생성

Phase 1: 핵심 파이프라인
  - diagnostics.py 작성 (룰 엔진 + LLM 프롬프트 + DB 저장 + fallback)
  - run.py 파이프라인 연결 (진단 + 대시보드 빌드 + 텔레그램)
  - 수동 실행으로 첫 진단 생성 검증
  - LLM 프롬프트 튜닝 (출력 품질 검수)

Phase 2: 대시보드 기반 개편
  - generate_dashboard_data.py 날짜 키 구조화
  - build_dashboard.py Tab 8 날짜별 분할 + 당일 임베드
  - JSX: 날짜 탐색 시스템 (anchorDate + range + 빈 날짜 처리)
  - JSX: V1 다크 테마 복원 (§10 색상/컴포넌트 전체 적용)
  - JSX: 탭 설명 추가 + "코스" 용어 변경
  - JSX: 탭 내부 레이아웃 (V1 grid 구조 기반)

Phase 3: Tab 7 AI 진단 UI
  - V1 스타일 서술형 UI (브리핑 + 경보 + 전략 카드)
  - 날짜별 아카이브 로드
  - 진단 없는 날짜 안내 메시지

Phase 4: 30일 데이터 최적화
  - 차트 interval 자동 조정
  - Tab 8 과거 JSON fetch (http://localhost 모드)
  - 축적 기간별 grain 자동 전환

Phase 5 (데이터 축적 후):
  - Tab 2 생애주기 (slot_observation_history 필요)
  - Tab 5A/5B (baseline_models 필요)
  - 날씨 데이터 연동 (기상청 API)
```

---

## 16. 미결 사항

| 항목 | 상태 | 메모 |
|------|------|------|
| course_variant 정규화 사전 | 대기 | 데이터 축적 후 확정 |
| 비할인 비교군 부재 코스 확정 | 대기 | 14일+ 데이터로 판단 |
| 기상청 API 키 발급 | 필요 | 공공데이터포털 신청 |
| nx·ny 격자 좌표 최종 확정 | 필요 | 기상청 격자변환기로 검증 |
| 악천후 전용 소진 기준선 | 대기 | 60일+ 후 구축 |
| 스크래퍼 course_sub 안정성 확인 | 대기 | 03-14 이후 데이터 검증 |
| OpenAI API 잔액/한도 확인 | 필요 | 월 $1~1.5 소요 예상 |
| 기존 LaunchDaemon 보고서 plist unload | Phase 0 | Mac에서 직접 실행 |

---

> 이 문서는 V4.1을 전면 개편한 V5 확정본이다.
> "시작" 신호 이후 Phase 0부터 순차 구현한다.
