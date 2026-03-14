# 카카오골프 골프장 예약·가격 반응 운영 보고서 시스템
> 기술 기획서 v2.1 | 8개 골프장 실데이터 검증 완료 | 2026-03-13

---

## 시스템 정의

카카오골프에서 수집된 골프장별 티타임·가격·할인 이력을 기반으로,
예약 소진율 / 가격 방어력 / 할인 반응 / 반복 약세 시간대 / 경쟁 비교를 자동 분석하여
일간·주간·월간 운영 보고서를 생성하는 시스템.

**핵심 전제:**
- 카트비별도 / 골프장 회원가입 조건은 모든 코스에 이미 포함된 구조 → 가격 비교 시 별도 필터 불필요
- `membership_type`은 일부 골프장만 표기 (해피니스·골드레이크). 나머지는 단일 구조
- 가격은 표시 가격 그대로 비교 가능

---

## 이 시스템이 답해야 하는 질문

1. 우리 골프장은 어느 요일·시간대에 잘 차는가
2. 비싸도 잘 팔리는 구간이 어디인가
3. 추가할인이 반복적으로 들어가는 구간이 어디인가
4. 할인 후 실제로 예약이 빨라지는가
5. 할인해도 반응 없는 시간대가 어디인가
6. 경쟁 골프장 대비 우리 가격과 소진 속도는 어떤 위치인가
7. 운영상 가격 유지 / 할인 검토 / 티수 조정 검토가 필요한 구간은 어디인가

---

## 1. 실제 수집 가능 필드 확정 (8개 골프장 검증 완료)

### ✅ 전체 공통 수집 가능

| 필드 | 실제 값 예시 | 설명 |
|------|-------------|------|
| `tee_time` | 06:46, 13:34 | HH:MM 단독 줄. 8개 골프장 100% |
| `price_krw` | 90000, 80000 | 현재 표시 가격. 원가 미표시. 8개 100% |
| `course_sub` | 동악, Sky, OUT, 밸리(대중제) | 한글·영문 혼재. 8개 100% |
| `promo_flag` | 0 / 1 | 특가·할인 키워드 탐지. 8개 100% |
| `promo_text` | 특가, 카카오골프특가 | 프로모 원문. 있는 골프장만 |
| `pax_condition` | 4인 필수 / 3인 이상 | 8개 100%. '3인 이상' = 특가 신호 |
| `part_type` | 1부 / 2부 | 시간 기반 자동 분류. 8개 100% |
| `d_day` | 7, 14, 30 | 수집일 기준 플레이일까지 남은 일수 |
| `season` | 봄/여름/가을/겨울 | 월 기반 자동 분류 |
| `weekday_type` | 평일/토/일 | 요일 분류 |
| `slot_group_key` | MD5 hash | 날짜 간 동일 슬롯 추적키 |

### ⚠️ 골프장에 따라 수집 가능 여부 다름

| 필드 | 수집 가능 | 미수집 | 비고 |
|------|-----------|--------|------|
| `membership_type` | 해피니스, 골드레이크 | 나머지 6개 | course_sub에 `(대중제)/(회원제)` 표기 있을 때만 |
| `price_type` | 어등산, 해피니스, 골드레이크, 무등산, 르오네뜨(일부) | 광주CC, 베르힐, 푸른솔장성 | None=그린피 포함 구조로 간주 가능 |

### ❌ 수집 불가

| 항목 | 이유 | 대안 |
|------|------|------|
| `listed_price_krw` (원가) | 페이지 미표시 | price_change_events의 전일 대비 delta |
| 예약 가능 상태 | 매진 슬롯 페이지에서 제거됨 | 잔여 수 감소 추이로 소진율 역산 |
| 예약 건수 | 미노출 | baseline 대비 잔여로 예약율 추정 |
| 전체 티 수 | 미노출 | baseline_models 과거 최대값으로 기준선 |

### 골프장별 필드 현황 (실데이터 검증)

| 골프장 | 총 티 | course_sub | membership | price_type | promo |
|--------|------|-----------|------------|------------|-------|
| 광주CC | 35 | ✅ 동악/설산/섬진 | ❌ | ❌ | ✅ 전체 특가 |
| 르오네뜨 | 20 | ✅ IN/OUT | ❌ | ✅ 일부(그린피) | ✅ 카카오골프특가 |
| 어등산 | 41 | ✅ 어등/하남/송정 | ❌ | ✅ 그린피 | ❌ |
| 베르힐 | 64 | ✅ Sky/Lake/Verthill | ❌ | ❌ | ❌ |
| 푸른솔장성 | 23 | ✅ 레이크/마운틴/힐 | ❌ | ❌ | ✅ 특가 |
| 해피니스 | 34 | ✅ 하트(대중제)외 | ✅ | ✅ 카트비별도 | ✅ 전체 특가 |
| 골드레이크 | 39 | ✅ 밸리(대중제)외 | ✅ | ✅ 그린피/카트비별도 | ✅ 일부 |
| 무등산 | 21 | ✅ 인왕봉외 | ❌ | ✅ 카트비별도 | ❌ |

> **price_type=None 처리 원칙**: 카트비별도·회원가입 조건은 전 코스 포함 구조이므로 가격 직접 비교 가능. price_type NULL은 별도 필터 불필요.

---

## 2. 실제 티타임 블록 구조

### 일반 슬롯
```
08:03              ← tee_time
115,000원          ← price_krw
밸리(대중제)       ← course_sub (membership_type = 대중제)
18홀               ← 스킵
4인 필수           ← pax_condition
                   ← 빈 줄
그린피             ← price_type
```

### 특가 슬롯
```
13:34              ← tee_time
90,000원           ← price_krw (카트비 미포함)
특가               ← promo_text (promo_flag = 1)
힐(대중제)         ← course_sub
18홀               ← 스킵
3인 이상           ← pax_condition ← 특가 식별 신호
                   ← 빈 줄
(특가)+카트비별도  ← price_type ← 가격 비교 제외 or 별도 처리
```

### ⚠️ 중요 주의사항
- `그린피` = 카트 포함 전체 가격
- `(특가)+카트비별도` = 표시 가격에 카트비 미포함 → 실제 비용 다름
- 두 유형을 섞어서 최저가 비교하면 분석 왜곡
- 모든 가격 비교 쿼리: `WHERE price_type = '그린피' AND membership_type = '대중제'`

---

## 3. DB 스키마

### tee_time_snapshots (원시 수집 — 핵심)
```sql
id, crawl_run_id, course_id, course_name
collected_date, play_date, tee_time
price_krw
course_sub          -- "밸리(대중제)"
membership_type     -- "대중제" / "회원제"  ← 신규
promo_flag          -- 0 / 1
promo_text          -- "특가"               ← 신규
pax_condition       -- "4인 필수" / "3인 이상" ← 신규
price_type          -- "그린피" / "(특가)+카트비별도" ← 신규
d_day, part_type, season, weekday_type
hash_key            -- UNIQUE. course_sub 포함 (충돌 방지)
slot_group_key      -- collected_date 제외. 날짜 간 슬롯 추적용 ← 신규
```

### price_change_events (가격 변동 이력)
```sql
id, course_name, play_date, tee_time, course_sub, membership_type
detected_at
old_price_krw, new_price_krw, delta_price_krw, delta_pct
event_type          -- "인하" / "인상" / "특가부착" / "특가해제"
promo_flag_after, promo_text_after
```
> slot_group_key로 전일 동일 슬롯과 매칭하여 생성

### price_response_metrics (할인 반응)
```sql
id, course_name, play_date, tee_time, course_sub
change_detected_at
before_open_slots
after_open_slots_1d / 3d / 5d
response_speed, response_grade  -- "강함" / "보통" / "약함" / "없음"
```

### daily_course_metrics (일일 집계)
```sql
report_date, course_name, play_date
season, weekday_type, part_type, membership_type  -- 분리 집계 필수
d_day
observed_open_slots
avg_price_krw, min_price_krw, max_price_krw
promo_slot_count, pax_3plus_count
discount_event_flag
member_open_flag    -- 1=회원제 슬롯 공개, 0=미공개, NULL=단일구조(판단불가)
confidence_score
UNIQUE(course_name, report_date, play_date, part_type, membership_type)
```

### member_open_events (회원제 오픈 이력) — 신규
```sql
course_name, play_date
detected_at          -- 최초 회원제 슬롯 관측 수집일
member_slot_count    -- 관측 슬롯 수
member_sub_names     -- JSON ["골드(회원제)", "레이크(회원제)"]
min_price_krw, max_price_krw
promo_flag           -- 오픈 시 특가 여부
```
> 적용 골프장: 골드레이크, 해피니스 전용

### baseline_models (예약율 추정 기준선)
```sql
course_name, season, weekday_type, part_type, membership_type
expected_slot_count, confidence_score, updated_at
UNIQUE(course_name, season, weekday_type, part_type, membership_type)
```

---

## 4. 판단룰 엔진

| 룰 | 조건 (실제 필드 기반) | 출력 |
|----|----------------------|------|
| A | promo_flag=0 + 소진 빠름 | 가격 유지 여력 높음 |
| B | 동일(요일+시간대+course_sub) 반복 특가 탐지 | 반복 할인 의존 구간 |
| C | delta_price < 0 후 1~3일 내 잔여 감소 | 할인 효과 높음 |
| D | delta_price < 0 후 잔여 감소 미미 | 할인 효과 제한적 |
| E | 높은 가격 + promo_flag=0 + 소진 빠름 | 프리미엄 구간 가능 |
| F | pax_condition='3인 이상' 반복 탐지 | 특가 의존 구간 |
| G | membership_type='대중제' 한정 비교 | 공정 경쟁 비교 전제 |
| **H** | **member_open_flag 변화 감지** | **회원제 오픈/마감 신호** |

### 룰 H 상세 — 회원제 오픈 판단 (골드레이크·해피니스 전용)

회원제 슬롯은 항상 열려 있지 않다. 오픈 여부 자체가 시장 신호다.

| 상황 | 판정 | 의미 |
|------|------|------|
| 회원제 슬롯 갑자기 등장 | 회원제 오픈 감지 | 시장 공급 증가. 경쟁 압력 상승 가능 |
| 회원제 슬롯 빠르게 소진 | 회원제 수요 강세 | 해당 플레이일 전반적 수요 높음 |
| 회원제 슬롯 오래 잔류 | 회원제 수요 약세 | 할인 가능성 또는 공급 과잉 |
| 회원제 오픈 + 특가 동시 | 적극 할인형 오픈 | 해피니스 패턴 (회원제도 전부 특가) |
| 회원제 오픈 + 특가 없음 | 정가 오픈 | 골드레이크 패턴 (회원제 정가 유지) |

```python
# config/courses.py에서 참조
MEMBER_COURSES = {
    "골드레이크": {
        "대중제": ["밸리(대중제)", "힐(대중제)"],
        "회원제": ["골드(회원제)", "레이크(회원제)"],
    },
    "해피니스": {
        "대중제": ["하트(대중제)", "힐링(대중제)"],
        "회원제": ["해피(회원제)", "휴먼(회원제)"],
    },
}
```

**분석 시 주의:**
- 대중제 vs 회원제 가격 비교는 의미 없음 (대상 고객 다름)
- 대중제 전용 가격 추세는 대중제 슬롯만으로 집계
- 회원제 오픈 감지는 시장 공급량 변화 신호로만 활용

---

## 5. 가격 비교 전제 조건

### 유효 비교 쿼리 기본 조건
```sql
-- 카트비별도·회원가입 조건은 포함 구조이므로 price_type 필터 불필요
-- membership_type이 있는 골프장(해피니스·골드레이크)은 대중제 필터 권장
SELECT course_name, play_date, tee_time, price_krw
FROM tee_time_snapshots
WHERE collected_date = '2026-03-14'
  AND (membership_type = '대중제' OR membership_type IS NULL)
```

### 가격 비교 단순화 원칙
- 카트비·회원가입 조건은 이미 포함된 구조 → 표시 가격 그대로 비교
- membership_type이 없는 골프장(6개)은 단일 구조로 간주
- 특가 슬롯(promo_flag=1)은 비교 시 별도 표기 권장 (정상가와 구분)

---

## 6. 보고서 종류

### A. 일간 운영 브리핑 (매일 자동)
- 전일 대비 변화 / 향후 14일 소진 상황
- 가격 변경 골프장 / 반복 할인 구간
- 베르힐CC 주의 포인트
- 출력: 텔레그램 1회 분량

### B. 주간 전략 보고서
- 골프장별 예약 추세 비교
- 가격 방어력 비교 / 할인 빈도 비교
- 약한 요일/시간대 / 다음 주 액션 제안
- 출력: 이메일

### C. 월간 인사이트 보고서
- 시즌별 1부/2부 강약 / 가격 정책별 반응 패턴
- 반복 할인 구간 누적 / 티배치 조정 후보
- 출력: PDF/문서

---

## 7. 개발 로드맵

### 1단계 MVP (4주)
**목표:** 일간 브리핑 자동화
- price_change_events 생성 로직
- 대중제/그린피 필터 기반 비교
- 텔레그램 발송

### 2단계 (MVP +4주)
**목표:** 주간 비교형
- slot_group_key 기반 소진 속도 추적
- 할인 반응 측정 (price_response_metrics)
- 경쟁 골프장 비교
- 이메일 보고서

### 3단계 (2단계 +6주)
**목표:** 월간 전략형
- 반복 할인 구간 탐지
- 프리미엄 허용 구간 분류
- baseline 고도화
- PDF 보고서

---

## 8. 현재 구현 상태

### 완료
- [x] 수집봇: 8개 골프장 D+1~D+30 자동 수집
- [x] tee_time_snapshots: 신규 필드 5개 추가 (membership_type, promo_text, pax_condition, price_type, slot_group_key)
- [x] hash_key: course_sub 포함으로 충돌 버그 수정
- [x] _parse_blocks(): 힐(대중제) 1글자 버그 + price_type 우선순위 버그 수정
- [x] DB 신규 테이블 4개: price_change_events, price_response_metrics, daily_course_metrics, baseline_models
- [x] 기존 3,950건 데이터 마이그레이션 완료
- [x] Mac launchd 스케줄러: 매일 06:50 자동 기상, 07:00 수집, 07:55 주간, 08:05 월간, 08:15 연간, 09:00 종료

### 완료 (1단계 진행 중)
- [x] analytics/price_change_detector.py — slot_group_key 기반 전일 대비 가격 변동 감지
  - 이벤트 유형: 인하 / 인상 / 특가부착 / 특가해제
  - get_change_summary() 브리핑용 요약 제공
- [x] analytics/daily_aggregator.py — daily_course_metrics 집계 + member_open_events 갱신
  - 회원제 오픈 판단: 골드레이크·해피니스 전용 member_open_flag
  - get_aggregation_summary() 브리핑용 요약 제공
- [x] run.py 분석 파이프라인 통합 — 수집 완료 후 자동 실행

### 미구현 (1단계 잔여)
- [ ] rule_engine.py (판단룰 A~H: 반복할인 구간 / 소진속도 / 가격방어력 등)
- [ ] report_generator.py (집계 결과 → 텔레그램 문장화)
- [ ] telegram_bot.py (일간 브리핑 자동 발송)

---

## 9. 기술 스택

| 영역 | 현재 | 목표 |
|------|------|------|
| 수집 | Python + Playwright (async, 모바일UA) | 유지 |
| 스케줄링 | macOS launchd + pmset | n8n 또는 유지 |
| DB | SQLite + aiosqlite | Supabase (데이터 증가 후) |
| 집계/분석 | - | Python + SQL |
| 룰 엔진 | - | Python |
| 보고서 생성 | - | OpenAI API (문장화만) |
| 배포 | - | Telegram Bot + Email |

---

## 10. 수집 대상 골프장

```python
COURSES = ["광주CC", "르오네뜨", "어등산", "베르힐", "푸른솔장성", "해피니스", "골드레이크", "무등산"]
```
> 광주CC만 검색어가 다름 (카드 표시명: "광주")

---

## 파일 구조

```
kakao_golf/
├── run.py                    # 메인 실행
├── config/courses.py         # 골프장 목록, 시즌/요일/파트 분류
├── scraper/kakao_scraper.py  # 수집봇 (v2.0)
├── db/database.py            # DB 스키마 + CRUD (v2.0)
├── data/golf.db              # SQLite DB
├── logs/                     # 디버그 스크린샷/텍스트
├── mac_scheduler_setup.sh    # launchd + pmset 자동 설정
└── SYSTEM_PLAN.md            # 이 파일
```
