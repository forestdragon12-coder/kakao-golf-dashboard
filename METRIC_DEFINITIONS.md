# 카카오골프 운영 지표 정의서
> 구현 직전 상세 설계 | 2026-03-13

## 1. 목적

보고서와 룰 엔진에서 사용하는 핵심 운영 지표의
정의, 계산 방식, 해석 기준을 고정한다.

---

## 2. Price Defense Index

정의:
- 무특가 상태에서 낮은 잔여로 유지된 정도

계산 개념:
```text
PDI = 무특가 저잔여 슬롯 수 / 전체 무특가 슬롯 수
```

해석:
- 0.75 이상: 강한 가격 방어
- 0.50~0.74: 보통
- 0.49 이하: 약함

---

## 3. Discount Efficiency Index

정의:
- 인하/특가부착 이후 슬롯이 얼마나 빨리 사라졌는지

계산 개념:
```text
DEI = (강함*1.0 + 보통*0.6 + 약함*0.3 + 없음*0.0) / 총 할인 이벤트 수
```

해석:
- 높을수록 할인 효과 좋음

---

## 4. False Discount Rate

정의:
- 할인은 했지만 반응이 없었던 비율

계산 개념:
```text
FDR = response_grade in ('없음', '약함') 인 할인 이벤트 수 / 총 할인 이벤트 수
```

해석:
- 높을수록 관성적 할인 가능성 높음

---

## 5. Repeated Weakness Score

정의:
- 동일 요일/파트/서브코스 조합에서 잔여 과다가 반복된 비율

계산 개념:
```text
RWS = weak_days / observed_days
```

최소 조건:
- observed_days >= 3

해석:
- 0.70 이상: 구조적 약세 가능성 큼
- 0.50~0.69: 반복 약세 주의
- 0.49 이하: 일시적 가능성

---

## 6. Premium Acceptance Score

정의:
- 평균보다 비싼데도 잔여가 적었던 비율

계산 개념:
```text
PAS = 고가 저잔여 슬롯 수 / 전체 고가 슬롯 수
```

해석:
- 높을수록 가격 인상 허용 여지 큼

---

## 7. Supply Shock Score

정의:
- 회원제 신규 오픈이 대중제 운영에 미치는 충격 정도

계산 개념:
```text
SSS = 회원제 오픈일의 대중제 잔여 증가율 + 특가 비중 증가율 + 가격 방어력 저하율
```

전제:
- 해피니스/골드레이크 전용

해석:
- 높을수록 공급 증가 압력 강함

---

## 8. Sub-course Dispersion Score

정의:
- 동일 골프장 내 서브코스별 잔여/가격/특가 편차

계산 개념:
```text
SDS = 서브코스별 평균 잔여/가격 차이의 정규화 점수
```

해석:
- 높을수록 코스별 운영 차별화 필요성 큼

---

## 9. Timeband Fitness Score

정의:
- 1부 / 2부 / 오후별 운영 체력

계산 개념:
```text
TFS = 가격 방어력 + 낮은 할인 의존도 + 낮은 반복 약세도
```

해석:
- 높을수록 해당 파트 운영 안정성 높음

---

## 10. Weekend Premium Retention

정의:
- 주말 슬롯에서 할인 없이 유지된 비율

계산 개념:
```text
WPR = 주말 무특가 저잔여 슬롯 수 / 전체 주말 슬롯 수
```

의미:
- 핵심 수익 시간대 확인

---

## 11. Data Confidence Score

정의:
- 보고서 해석의 신뢰도

구성:
- 데이터 누락 일수
- 골프장 누락 여부
- 누적 관측 일수
- 이벤트 수 부족 여부

해석:
- 낮을수록 리포트에 보수적 문구 필요

---

## 12. 구현 우선순위

1. Repeated Weakness Score
2. Discount Efficiency Index
3. False Discount Rate
4. Price Defense Index
5. Premium Acceptance Score
6. Supply Shock Score
7. Sub-course Dispersion Score
8. Timeband Fitness Score
