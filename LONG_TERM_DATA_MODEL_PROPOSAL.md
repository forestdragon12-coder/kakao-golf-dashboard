# 카카오골프 장기 운영 기준 데이터 모델 개선안
> v1 | 2026-03-14

## 1. 목적

현재 주간 보고서는 관측일이 2일 수준이라 문장 품질보다 구조 설계가 우선이다.
이 문서는 시간이 지날수록 더 정확해지는 데이터 모델로 전환하기 위한 기준안을 정의한다.

핵심 목표는 3가지다.

- 동일 티타임을 장기적으로 안정 추적한다.
- 가격 변화와 판매 흐름을 직접 연결한다.
- 할인 표기와 실제 가격 변화, 공급 상태 변화를 분리 기록한다.

## 2. 현재 구조의 핵심 한계

- `slot_group_key`가 `course_name + play_date + tee_time + course_sub` 수준이라, 파트 재배치, 서브코스 표기 흔들림, 채널 차이를 충분히 흡수하지 못한다.
- 현재 스냅샷은 "보였다/안 보였다" 위주라 `sold_out`, `not_open`, `hidden`, `removed_or_unknown`를 구분하지 못한다.
- `price_krw`, `promo_flag`, `promo_text`만으로는 할인 표기와 실질 가격 차감을 분리하기 어렵다.
- 가격 변화 전후 판매 반응은 `discount_response_metrics`에 일부 들어가지만, 가격 변경 단위와 직접 연결된 중간 테이블이 약하다.
- 공급 이슈와 가격 이슈가 같은 액션으로 섞이기 쉬운 구조다.

## 3. 설계 원칙

- 원시 스냅샷은 최대한 보존한다.
- 파생 판단은 별도 중간 집계 테이블에서 수행한다.
- "보이지 않음"은 하나의 상태로 뭉치지 않는다.
- 가격 이벤트와 판매 반응 이벤트는 동일한 이벤트 키로 연결 가능해야 한다.
- 보고서용 payload는 최종 해석층이며, 판단 근거는 DB 계층에서 먼저 구조화한다.

## 4. 안정적인 티타임 추적 키 재설계

### 4.1 권장 키 계층

1. `slot_identity_key`
- 목적: 동일 상품/동일 티타임의 장기 추적
- 구성: `course_id + play_date + tee_time + part_type + course_variant + source_channel`
- 비고: 사람이 읽는 `course_name` 대신 내부 `course_id` 사용

2. `slot_observation_key`
- 목적: 같은 슬롯의 특정 수집 시점 기록
- 구성: `slot_identity_key + collected_at`

3. `slot_group_key_legacy`
- 목적: 기존 로직 호환용
- 단계적 폐기 대상

### 4.2 새 필드 정의

- `course_variant`
  설명: `course_sub`, `membership_type`, `price_type`를 표준화한 내부 식별값
  예: `verthill_public`, `gold_member`, `hill_public`

- `source_channel`
  설명: 카카오골프 내 노출 채널 또는 수집 페이지 구분
  예: `kakao_mobile`, `kakao_promo`, `kakao_member`

- `slot_identity_version`
  설명: 키 생성 규칙 버전
  목적: 파서 변경 후 키 흔들림 추적

### 4.3 키 충돌 방지 규칙

- `course_sub` 원문을 직접 키에 넣지 말고 정규화 사전을 거친 `course_variant`를 사용한다.
- `membership_type`이 NULL인 코스도 `single_structure` 같은 표준값으로 채운다.
- `source_channel`이 불명확한 경우 `unknown_channel`로 채우되 NULL은 금지한다.
- 파서가 코스명 표기를 바꿔도 `course_id`는 동일해야 한다.

### 4.4 권장 검증 쿼리

- 동일 `slot_identity_key`에 하루 2개 이상 상이한 가격/상태가 생기면 중복 수집 또는 파싱 충돌 의심
- 같은 `play_date + tee_time`에 `course_variant`가 하루 단위로 바뀌면 키 흔들림 경보

## 5. 상태값 분리 모델

현재 "안 보임"을 매진으로 읽는 오류를 막기 위해 상태를 아래처럼 분리한다.

### 5.1 제안 상태

- `available`
- `sold_out`
- `hidden`
- `not_open`
- `removed_or_unknown`

### 5.2 판정 규칙

- `available`
  현재 수집 시점에 슬롯이 노출되고 예약 가능

- `sold_out`
  직전까지 노출되던 슬롯이 동일 영업일 내 명시적 매진 신호와 함께 사라짐

- `hidden`
  슬롯 자체는 유지될 가능성이 있으나 UI 필터, 접기, 로딩 이슈로 미노출

- `not_open`
  해당 `play_date` 구간 자체가 아직 오픈되지 않았다고 판단

- `removed_or_unknown`
  위 4개로 구분 불가능한 상태

### 5.3 구현 원칙

- `sold_out`은 "이전 관측에 있었고, 같은 오픈 윈도우 내 공급 총량은 유지되는데 해당 슬롯만 사라진 경우"로 제한한다.
- `not_open`은 해당 날짜군 전체가 미오픈일 때만 사용한다.
- `hidden`과 `removed_or_unknown`는 보고서에서 직접 매진 신호로 사용하지 않는다.

## 6. 가격 이력 필드 보강안

### 6.1 원시 가격 필드

- `listed_price_krw`
- `normal_price_krw`
- `sale_price_krw`
- `promo_flag`
- `promo_text`
- `price_badge`

### 6.2 파생 가격 필드

- `previous_price_krw`
- `price_changed_flag`
- `price_change_delta_krw`
- `price_change_delta_pct`
- `price_change_count_7d`
- `first_discount_dday`

### 6.3 의미

- `listed_price_krw`
  UI에 보이는 현재 노출가

- `normal_price_krw`
  정가 또는 기준가로 인식되는 값
  없으면 NULL 유지

- `sale_price_krw`
  실질 할인 가격
  정가와 분리 가능한 경우만 채움

- `price_badge`
  `특가`, `카카오골프특가`, `타임특가`, `3인특가` 등 표기 유형

- `first_discount_dday`
  특정 `slot_identity_key`가 처음 할인 상태가 된 시점의 `d_day`

### 6.4 저장 규칙

- `promo_flag = 1`이어도 `sale_price_krw`가 `listed_price_krw`와 구분되지 않으면 "표기 할인"로만 저장
- `normal_price_krw`가 없을 때는 허수 할인 판정에 직접 쓰지 않는다

## 7. 신규/확장 테이블 제안

### 7.1 `slot_status_history`

목적:
스냅샷 상태 변화 추적

주요 컬럼:

- `slot_identity_key`
- `collected_at`
- `slot_status`
- `status_reason`
- `visible_flag`
- `inventory_observed_flag`

### 7.2 `price_change_facts`

목적:
가격이 언제 얼마나 바뀌었는지 이벤트 단위 저장

주요 컬럼:

- `price_change_event_id`
- `slot_identity_key`
- `course_id`
- `play_date`
- `part_type`
- `source_channel`
- `change_detected_at`
- `previous_price_krw`
- `current_price_krw`
- `delta_krw`
- `delta_pct`
- `change_type`
- `promo_flag_before`
- `promo_flag_after`
- `price_badge_before`
- `price_badge_after`
- `price_change_count_7d`

### 7.3 `slot_velocity_facts`

목적:
가격 변화 전후 판매 속도 비교

주요 컬럼:

- `price_change_event_id`
- `before_change_open_slots`
- `after_change_open_slots_1d`
- `after_change_open_slots_3d`
- `after_change_open_slots_7d`
- `slot_velocity_before`
- `slot_velocity_after_1d`
- `slot_velocity_after_3d`
- `slot_velocity_after_7d`
- `discount_response_grade`
- `response_confidence`

### 7.4 `course_segment_daily_facts`

목적:
주간/월간/연간 지표의 공통 기준 테이블

권장 grain:

- `course_id`
- `report_date`
- `play_date`
- `weekday_type`
- `part_type`
- `season`
- `membership_type`
- `source_channel`

주요 컬럼:

- `available_slots`
- `sold_out_slots`
- `hidden_slots`
- `not_open_slots`
- `removed_or_unknown_slots`
- `listed_avg_price_krw`
- `normal_avg_price_krw`
- `sale_avg_price_krw`
- `promo_slot_count`
- `real_discount_slot_count`
- `price_change_event_count`
- `member_open_flag`

### 7.5 `competitive_segment_facts`

목적:
경쟁군 대비 가격/판매력 비교

주요 컬럼:

- `comparison_group_id`
- `course_id`
- `segment_key`
- `avg_price_rank`
- `avg_open_slots_rank`
- `price_position`
- `defense_position`
- `competitive_gap_score`

## 8. 중간 집계 구조 설계

아래 질문에 답하기 위한 중간 집계층을 고정한다.

- 가격이 언제 바뀌었는가
- 얼마나 바뀌었는가
- 바뀐 뒤 판매 속도가 빨라졌는가
- 할인했는데도 반응이 약한가
- 할인 없이도 잘 팔리는가

### 8.1 `weekly_change_section_source`

역할:
이번 기간에 발생한 변화만 요약

주요 컬럼:

- `course_id`
- `change_event_count`
- `price_down_count`
- `promo_attach_count`
- `promo_detach_count`
- `largest_cut_krw`
- `largest_cut_pct`
- `response_after_cut_grade`

### 8.2 `current_structure_section_source`

역할:
현재 구조 상태 요약

주요 컬럼:

- `current_price_defense_score`
- `current_discount_dependency_score`
- `current_false_discount_score`
- `current_supply_shock_score`
- `current_premium_acceptance_score`

## 9. 구현 우선순위

### Phase 1

- `slot_identity_key` 재설계
- 상태값 분리
- 가격 이력 필드 확장
- `price_change_facts`, `slot_velocity_facts` 추가

### Phase 2

- `course_segment_daily_facts` 도입
- 경쟁군 비교 테이블 추가
- 허수 할인 3단 분리 지표 구현

### Phase 3

- 보고서 payload를 `weekly_change_section` / `current_structure_section` 이원 구조로 전환
- 액션 로직을 원인 축 기반으로 재구성

## 10. 마이그레이션 원칙

- 기존 `tee_time_snapshots`는 유지하고, 신규 컬럼은 nullable로 단계적 추가
- 신규 지표는 과거 데이터 backfill이 가능한 것부터 적용
- 과거 데이터로 재구성 불가능한 필드는 "도입일 이후 유효"로 명시
- 보고서는 최소 2주간 구구조/신구조 병행 검증 후 전환

