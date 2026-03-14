# 카카오골프 핵심 지표 정의서 v1
> 장기 누적 운영 기준 | 2026-03-14

## 1. 목적

주간/월간/연간 해석이 관측일 수에 따라 흔들리지 않게 하려면
지표 정의가 먼저 고정돼야 한다.
이 문서는 장기 누적 시 왜곡을 줄이기 위한 지표 정의 기준을 정리한다.

## 2. 공통 원칙

- 지표는 `course x season x weekday_type x part_type x membership_type` 단위로 계산 가능해야 한다.
- 최소 필요 관측 수 미만이면 점수는 계산하더라도 보고서 노출은 제한한다.
- 결측은 0으로 대체하지 않는다.
- 이상치는 winsorize 또는 capped z-score 방식으로 처리한다.
- 모든 지표는 `score`, `label`, `confidence`, `sample_size`를 함께 저장한다.

## 3. 기본 체급

### 계산식

`기본 체급 = 비할인 상태 평균 소진속도 / 비교군 평균 소진속도`

권장 score:

`base_tier_score = norm(slot_velocity_non_discount_3d)`

### 입력 컬럼

- `slot_velocity_before`
- `available_slots`
- `promo_flag`
- `sale_price_krw`
- `segment_key`

### 최소 필요 관측 수

- 14 segment-day 이상
- 비할인 관측 7회 이상

### 결측 처리

- 비할인 관측이 7회 미만이면 `label = 판단보류`

### 이상치 처리

- 공급 충격일 제외
- 극단값 상하위 2.5% 절삭

### 신뢰도 계산

- sample size
- 비할인 관측 비중
- 시즌 커버리지

### 해석 시 주의사항

- 가격이 높아서 느린지, 공급이 많아서 느린지는 분리하지 못한다.
- 공급 충격 구간과 함께 읽어야 한다.

## 4. 할인 의존도

### 계산식

`discount_dependency = (할인 구간 소진속도 - 비할인 구간 소진속도) / max(할인 구간 소진속도, epsilon)`

### 입력 컬럼

- `slot_velocity_after_3d`
- `slot_velocity_before`
- `promo_flag`
- `sale_price_krw`

### 최소 필요 관측 수

- 할인 이벤트 10건 이상
- 비할인 비교군 10건 이상

### 결측 처리

- 비교군 부족 시 NULL

### 이상치 처리

- 이벤트 후 1일 내 공급 급증 구간 제외

### 신뢰도 계산

- 할인/비할인 샘플 균형성
- 비교군 매칭 성공률

### 해석 시 주의사항

- "의존도 높음"은 할인 효과가 좋다는 뜻이 아니라,
  할인 없이 유지되기 어려울 가능성이 높다는 뜻이다.

## 5. 할인 증폭력

### 계산식

`discount_amplification = 할인 이벤트 후 소진속도 - 동일 segment 경쟁군 비할인 소진속도`

### 입력 컬럼

- `slot_velocity_after_3d`
- `competitive_group_avg_velocity`
- `part_type`
- `weekday_type`

### 최소 필요 관측 수

- 할인 이벤트 8건 이상
- 경쟁군 비교 8건 이상

### 결측 처리

- 경쟁군 부족 시 계산 보류

### 이상치 처리

- 가격 변경 없는 이벤트 제외
- `delta_pct`가 극단적이면 별도 outlier bucket 분리

### 신뢰도 계산

- 경쟁군 매칭률
- 이벤트 수
- 시즌 분산

### 해석 시 주의사항

- 할인 증폭력이 높아도 장기 수익성이 좋다는 뜻은 아니다.
- 허수 할인 여부와 함께 봐야 한다.

## 6. 가격 방어력

가격 방어력은 단일값이 아니라 축별로 분리한다.

### 6.1 비할인 상태 가격 방어력

계산식:

`non_discount_defense = 비할인 상태 고가 구간 중 저잔여 유지 비율`

### 6.2 요일별 가격 방어력

계산식:

`weekday_defense = weekday_type별 non_discount_defense`

### 6.3 part별 가격 방어력

계산식:

`part_defense = part_type별 non_discount_defense`

### 6.4 시즌별 가격 방어력

계산식:

`seasonal_defense = season별 non_discount_defense`

### 6.5 경쟁군 대비 가격 방어력

계산식:

`competitive_defense = 우리 고가 유지율 - 경쟁군 고가 유지율`

### 입력 컬럼

- `avg_price_rank`
- `avg_open_slots`
- `promo_flag`
- `segment_key`

### 최소 필요 관측 수

- 축별로 10 observation 이상

### 결측 처리

- 축별 샘플 부족 시 해당 축만 `confidence=low`

### 이상치 처리

- 공급 충격일 제외
- 비정상 holiday spike 별도 플래그

### 신뢰도 계산

- 축별 sample size
- 공급 충격 제외 후 잔여 sample size

### 해석 시 주의사항

- 가격 방어력은 "안 깎아도 팔림"의 신호이지,
  곧바로 인상 가능의 신호는 아니다.

## 7. 허수 할인

허수 할인은 단일 지표로 두지 않는다.

### 7.1 할인 표기 존재 여부

계산식:

`discount_label_presence = promo_flag or promo_text or price_badge`

### 7.2 실질 가격 차감 폭

계산식:

`real_discount_depth = (normal_price_krw - sale_price_krw) / normal_price_krw`

### 7.3 할인 후 판매 반응

계산식:

`discount_response = slot_velocity_after_3d - slot_velocity_before`

### 7.4 최종 허수 할인 판정

조합 규칙:

- 할인 표기는 있음
- 실질 가격 차감 폭은 미미하거나 불명확
- 판매 반응도 약함 또는 없음

권장 score:

`false_discount_score = weighted(label_presence, shallow_discount, weak_response)`

### 입력 컬럼

- `promo_flag`
- `promo_text`
- `price_badge`
- `normal_price_krw`
- `sale_price_krw`
- `slot_velocity_before`
- `slot_velocity_after_3d`

### 최소 필요 관측 수

- 할인 이벤트 8건 이상

### 결측 처리

- `normal_price_krw` 부재 시 "표기 기반 허수 할인"까지만 계산
- 반응 데이터 부재 시 최종 판정 금지

### 이상치 처리

- 비정상 프로모션 텍스트는 사전 정규화 후 계산

### 신뢰도 계산

- 가격 기준가 존재 여부
- 반응 데이터 존재 여부
- 채널 일관성

### 해석 시 주의사항

- 허수 할인 높음은 "할인이 나쁘다"가 아니라
  할인 표기와 실제 판매 반응이 정합적이지 않다는 뜻이다.

## 8. 공급 충격

### 계산식

`supply_shock = abs(당일 공급량 - segment baseline 공급량) / baseline 공급량`

보조 항목:

- `member_open_event_count`
- `new_slot_release_count`

### 입력 컬럼

- `available_slots`
- `member_open_flag`
- `slot_status`

### 최소 필요 관측 수

- baseline 14일 이상

### 결측 처리

- baseline 부족 시 `confidence=low`

### 이상치 처리

- 휴장/기상/대회일은 별도 exclusion flag

### 신뢰도 계산

- baseline 길이
- 운영 캘린더 매칭률

### 해석 시 주의사항

- 공급 충격은 가격 정책 실패와 별개다.
- 공급 문제를 가격 문제로 오판하지 않게 분리해야 한다.

## 9. 프리미엄 허용도

### 계산식

`premium_acceptance = 고가 구간 중 저잔여 유지 비율`

경쟁군 보정형:

`premium_acceptance_adj = 우리 고가 유지율 - 경쟁군 동일 segment 평균`

### 입력 컬럼

- `avg_price_rank`
- `avg_open_slots_rank`
- `slot_velocity`

### 최소 필요 관측 수

- 고가 구간 8건 이상

### 결측 처리

- 고가 구간 부족 시 NULL

### 이상치 처리

- 프로모션 개입 구간 제외

### 신뢰도 계산

- 고가 구간 샘플 수
- 비할인 관측 비중

### 해석 시 주의사항

- 프리미엄 허용도는 인상 폭을 바로 뜻하지 않는다.
- 가격 방어력과 함께 봐야 한다.

