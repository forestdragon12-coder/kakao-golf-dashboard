# Golf Price Dashboard v5 - Complete Field Mapping Audit

## Executive Summary
- **Total Tabs Analyzed:** 8
- **Critical Mismatches:** 12 field names
- **Warning Level Issues:** 8 fields
- **Missing Structures:** 4 tabs have structural issues
- **Missing Data:** Tab 8 completely absent from data generation

---

## TAB 1: 오늘 현황 (Daily Overview)

### KPI Section
| JSX Line | JSX Expects | Data Provides | Status | Notes |
|----------|-------------|---------------|--------|-------|
| 253 | `kpi.remaining_slots` | `kpi.total_slots_today` | ❌ CRITICAL | Renamed field - total vs remaining semantic difference |
| 254 | `kpi.vs_prev_day` | `kpi.total_slots_prev` + calc | ⚠️ WARNING | Need to calculate % change from prev |
| 255 | `kpi.price_changes` | `kpi.total_price_changes` | ✓ OK | Names differ but semantic match |
| 256 | `kpi.promo_rate` | `kpi.promo_ratio` | ❌ CRITICAL | rate vs ratio - different meaning |

### Course KPI Table (lines 305-323)
| JSX Line | JSX Expects | Data Provides | Status | Fix |
|----------|-------------|---------------|--------|-----|
| 308 | `row.course` | `row.course_name` | ❌ CRITICAL | Rename course_name → course |
| 310 | `row.remaining` | `row.slots` | ❌ CRITICAL | Rename slots → remaining |
| 311 | `row.avg_price` | `row.avg_price` | ✓ OK | Match |
| 312 | `row.promo_count` | `row.promo_slots` | ❌ CRITICAL | Rename promo_slots → promo_count |
| 319 | `row.status` | NOT PRESENT | ❌ CRITICAL | Add status field (calculate from remaining/total ratio) |

### Price Changes Section (lines 337-364)
| JSX Line | JSX Expects | Data Provides | Status | Notes |
|----------|-------------|---------------|--------|-------|
| 337-346 | `price_changes.down[]` | NOT IN TAB1 | ❌ CRITICAL | Data missing completely from tab1 |
| 345 | `evt.course` | Should be course_name | ⚠️ | If added, field names will mismatch |
| 346 | `evt.slot, evt.old_price, evt.new_price` | Need mapping | ⚠️ | Field name standardization needed |

---

## TAB 3: 시간대별 소진율 (Consumption Heatmap)

### Heatmap Section (lines 500-524)
| JSX Line | JSX Expects | Data Provides | Status | Critical Issue |
|----------|-------------|---------------|--------|-----------------|
| 482 | `consumption_heatmap` | `heatmap: list[0]` | ❌ CRITICAL | Data is empty array - returns 0 rows |
| 503 | `row.weekday` | `row.weekday_type` | ❌ CRITICAL | Field rename needed |
| 506 | `row['am'], row['pm']` | Part-based rows, not columns | ❌ CRITICAL | Data structure mismatch - needs pivot transform |

### Course Consumption Section (lines 530-557)
| JSX Line | JSX Expects | Data Provides | Status | Notes |
|----------|-------------|---------------|--------|-------|
| 537-539 | `course_consumption[]` | NOT PROVIDED | ❌ CRITICAL | No course_consumption in data output |
| - | Expects array of courses | Has empty arrays | ❌ | course_patterns is empty |

### Distribution Section (line 560-573)
| JSX Line | JSX Expects | Data Provides | Status | Notes |
|----------|-------------|---------------|--------|-------|
| 560 | `distribution` | NOT PROVIDED | ❌ CRITICAL | Component tries to render but data missing |

**STRUCTURAL ISSUE:** Tab3 data exists but in wrong format. `today_distribution` has 9 rows with [weekday_type, part_type, slots, avg_price, promo_slots]. JSX expects a pivot table format (weekdays as rows, am/pm as columns).

---

## TAB 4: 가격 흐름 (Price Trends)

### Trend Chart (lines 617-628)
| JSX Line | JSX Expects | Data Provides | Status | Issue |
|----------|-------------|---------------|--------|-------|
| 617 | `dday_trend` array | `dday_trend: list[214]` | ⚠️ PARTIAL | Data exists but... |
| 623-624 | Per-course Line plots: `dataKey={course}` | Flat array, not course-keyed object | ❌ CRITICAL | Data structure: each row is one point, not course-organized |
| 623 | Expects COURSE_COLORS mapping | Has course_name field | ⚠️ | Field rename: course_name → course |

**Data structure in detail:**
```
Expected by JSX:
  {
    "골드레이크": [
      { dday: 10, price: 120, ... },
      { dday: 9, price: 119, ... }
    ],
    "광주CC": [ ... ]
  }

Actually provided:
  [
    { course_name: "골드레이크", d_day: 10, avg_price: 120, ... },
    { course_name: "광주CC", d_day: 10, avg_price: 118, ... }
  ]
```

### Scatter Chart (lines 632-645)
| JSX Line | JSX Expects | Data Provides | Status | Fix |
|----------|-------------|---------------|--------|-----|
| 641 | `s.course, s.price` | `s.course_name, s.price_krw` | ❌ CRITICAL | Two renames needed |
| 638 | YAxis dataKey="price" | price_krw exists | ⚠️ | Rename price_krw → price |

### Histogram (lines 648-661)
| JSX Line | JSX Expects | Data Provides | Status | Fix |
|----------|-------------|---------------|--------|-----|
| 652 | histogram data | histogram: list[22] ✓ | ✓ EXISTS | - |
| 654 | `dataKey="range"` | `dataKey="price_bucket"` | ❌ CRITICAL | Rename price_bucket → range |

### Price Events Table (lines 683-707)
| JSX Line | JSX Expects | Data Provides | Status | Critical Issue |
|----------|-------------|---------------|--------|-----------------|
| 690 | `evt.course` | `evt.course_name` | ⚠️ WARNING | Rename |
| 701 | `evt.price` | `evt.new_price_krw` or `evt.old_price_krw` | ❌ CRITICAL | Which price to show? data has both with _krw suffix |
| 702 | `evt.dday` | NOT PROVIDED | ❌ CRITICAL | D-day must be calculated from play_date |
| 704 | `evt.time` | `evt.tee_time` (different format) | ⚠️ WARNING | Rename and format |

---

## TAB 5A: 할인 반응 (Discount Impact)

### Course Summary Cards (lines 732-745)
| JSX Line | JSX Expects | Data Provides | Status | Critical Issue |
|----------|-------------|---------------|--------|-----------------|
| 739 | `item.course` | `item.course_name` | ⚠️ | Rename |
| 741 | `item.booking_increase` | NOT IN DATA | ❌ CRITICAL | Field completely missing from course_summary |
| - | - | Actual fields: [event_count, avg_discount_pct, total_discount_amt, max_discount_pct] | - | - |

### D-day Comparison Chart (lines 750-765)
| JSX Line | JSX Expects | Data Provides | Status | Fix |
|----------|-------------|---------------|--------|-----|
| 754 | dday_comparison data | dday_comparison: list[29] ✓ | ✓ | - |
| 760 | `dataKey="with_promo"` | `dataKey="avg_promo"` | ❌ CRITICAL | Rename avg_promo → with_promo |
| 761 | `dataKey="without_promo"` | `dataKey="avg_non_promo"` | ❌ CRITICAL | Rename avg_non_promo → without_promo |

### Discount Events Table (lines 787-806)
| JSX Line | JSX Expects | Data Provides | Status | Notes |
|----------|-------------|---------------|--------|-------|
| 790 | `evt.course` | `evt.course_name` | ⚠️ | Rename |
| - | event_type display | `evt.event_type` exists | ✓ | - |

---

## TAB 5B: 수익 구조 (Yield Analysis)

### Course Yield Summary Cards (lines 838-851)
| JSX Line | JSX Expects | Data Provides | Status | Critical Issue |
|----------|-------------|---------------|--------|-----------------|
| 829 | `course_yield_summary` | Named `course_summary` in data | ❌ CRITICAL | Variable name mismatch in structure |
| 845 | `item.course` | `item.course_name` | ⚠️ | Rename |
| 847 | `item.yield_rate` | NOT PROVIDED | ❌ CRITICAL | Field missing - should be calculated (e.g., actual_yield / baseline * 100) |
| - | - | Has: weekday_avg_yield, weekend_avg_yield | - | Unclear if these are %, need clarification |

### Yield Histogram (lines 855-869)
| JSX Line | JSX Expects | Data Provides | Status | Fix |
|----------|-------------|---------------|--------|-----|
| 860 | yield_histogram data | yield_histogram: list[16] ✓ | ✓ | - |
| 862 | `dataKey="range"` | `dataKey="yield_bucket"` | ⚠️ WARNING | Rename yield_bucket → range |

---

## TAB 6: 코스 × 회원제 (Subcourse Analysis)

### Structure Mismatch - MAJOR REFACTOR NEEDED

**JSX expects (line 884):**
```javascript
course_subcourse_data = [
  {
    course: "골드레이크",
    subcourses: [
      { name: "A코스", price: 120, member_open: true },
      { name: "B코스", price: 115, member_open: false }
    ]
  },
  ...
]
```

**Data actually provides (tab6):**
```
course_summary = {
  "골드레이크": {
    total_slots: 418,
    total_promo: 0,
    prices: [120, 115, ...],
    subcourses: [
      { name/label: "...", slots: X, promo: Y, ... }
    ],
    member_slots: 1,
    public_slots: 417
  },
  ...
}

ALSO:
subcourse_rows = [
  { course_name: "골드레이크", course_sub: "...", avg_price: 120, ... },
  ...
]
```

### Subcourse Comparison Table (lines 960-975)
| JSX Line | JSX Expects | Data Provides | Status | Notes |
|----------|-------------|---------------|--------|-------|
| 962 | `row.subcourse` | `row.course_sub` | ⚠️ | Rename |
| 963 | `row.avg_price` | `row.avg_price` | ✓ | OK |
| 964 | `row.max_price` | `row.max_price` | ✓ | OK |
| 965 | `row.min_price` | `row.min_price` | ✓ | OK |
| 967 | `row.member_open` | NOT in subcourse_rows | ❌ | Field missing or in wrong structure |

**ISSUE:** subcourse_comparison data not explicitly in output; JSX tries to render but no matching data structure provided.

---

## TAB 7: AI 진단 (Diagnostics)

### Diagnostics Display (lines 1036-1110)
| JSX Line | JSX Expects | Data Provides | Status | Critical Issue |
|----------|-------------|---------------|--------|-----------------|
| 1044 | `diag.course` | `diag.course_name` | ⚠️ | Rename |
| 1053 | `diag.overall_score` | NOT PROVIDED | ❌ CRITICAL | Field missing |
| 1060 | `diag.rules[]` | NOT PROVIDED | ❌ CRITICAL | Array of rule codes missing |
| 1093 | `diag.recommendations[]` | NOT PROVIDED | ❌ CRITICAL | Array of recommendation strings missing |
| 1103 | `diag.risks[]` | NOT PROVIDED | ❌ CRITICAL | Array of risk descriptions missing |
| - | - | Actual: [course_name, findings, severity_max, finding_count] | - | Data has findings but wrong structure |

**Data vs JSX Structure:**
```
Data:
  [
    { course_name: "골드레이크", findings: [...], severity_max: "warning", finding_count: 3 }
  ]

JSX expects:
  {
    course: "골드레이크",
    overall_score: 85,
    rules: ["A", "B", "C"],
    recommendations: ["Recommendation 1", "Recommendation 2"],
    risks: ["Risk 1"]
  }
```

---

## TAB 8: 티타임 상세 (Slot Details)

### CRITICAL: NO DATA PROVIDED
| Section | JSX Expects | Data Provides | Status |
|---------|-------------|---------------|--------|
| Tab init | `RAW_DATA.tab8` | NOT GENERATED | ❌ CRITICAL |
| Slot data | `tabData?.slots` | null/undefined | ❌ CRITICAL |
| Filters | `slot.course, slot.weekday, slot.part, slot.has_promo, slot.slot, slot.price, slot.dday, slot.status` | NO DATA | ❌ CRITICAL |

**Impact:** Tab 8 renders null state because `make_embed_data()` in `generate_dashboard_data.py` does not generate tab8 output. This is a complete data generation gap.

---

## Summary Field Mapping Table

| # | Severity | Tab | JSX Field | Data Field | Action Required |
|---|----------|-----|-----------|------------|-----------------|
| 1 | CRITICAL | 1 | kpi.remaining_slots | kpi.total_slots_today | Rename or recalculate |
| 2 | CRITICAL | 1 | kpi.promo_rate | kpi.promo_ratio | Rename |
| 3 | CRITICAL | 1 | .course | .course_name | Rename (all tabs) |
| 4 | CRITICAL | 1 | .remaining | .slots | Rename |
| 5 | CRITICAL | 1 | .promo_count | .promo_slots | Rename |
| 6 | CRITICAL | 1 | .status | NOT PRESENT | Add calculation |
| 7 | CRITICAL | 1 | price_changes | NOT IN TAB1 | Move data or add field |
| 8 | CRITICAL | 3 | consumption_heatmap | heatmap (empty) | Populate data |
| 9 | CRITICAL | 3 | row structure | weekday_type/part_type | Pivot transformation |
| 10 | CRITICAL | 4 | dday_trend object | dday_trend array | Restructure/transform |
| 11 | CRITICAL | 4 | scatter.price | scatter.price_krw | Rename |
| 12 | CRITICAL | 4 | histogram.range | histogram.price_bucket | Rename |
| 13 | WARNING | 4 | price_events.dday | NOT PROVIDED | Calculate from play_date |
| 14 | WARNING | 5A | with_promo | avg_promo | Rename |
| 15 | CRITICAL | 5B | course_yield_summary | course_summary | Rename or restructure |
| 16 | CRITICAL | 5B | .yield_rate | NOT PROVIDED | Calculate yield metric |
| 17 | CRITICAL | 6 | course_subcourse_data | course_summary (dict) | Refactor to array |
| 18 | CRITICAL | 7 | diag.rules[] | NOT PROVIDED | Extract/generate rules |
| 19 | CRITICAL | 7 | diag.overall_score | NOT PROVIDED | Calculate score |
| 20 | CRITICAL | 8 | ALL | NO DATA | Implement tab8 generation |

---

## Files Affected

**JSX Component:** `/sessions/hopeful-pensive-allen/mnt/kakao_golf/golf_price_dashboard_v5.jsx`
- Lines 240-370 (Tab1)
- Lines 475-575 (Tab3)
- Lines 580-712 (Tab4)
- Lines 715-817 (Tab5A)
- Lines 820-872 (Tab5B)
- Lines 875-981 (Tab6)
- Lines 984-1114 (Tab7)
- Lines 1116-1400+ (Tab8)

**Data Generation:** `/sessions/hopeful-pensive-allen/mnt/kakao_golf/generate_dashboard_data.py`
- `build_v5_data()` function - builds tab1-7 data
- `make_embed_data()` function - structures output
- Missing: tab8 data generation entirely

---

## Remediation Priority

### Phase 1: Critical (Blockers)
1. Implement Tab 8 data generation
2. Fix Tab 1 field names (course_name, slots, promo_slots, promo_ratio)
3. Add missing course_kpi[].status field
4. Populate Tab 3 heatmap data (currently empty)
5. Add Tab 5A booking_increase field

### Phase 2: Structure (Data Shape)
1. Transform Tab 4 dday_trend to course-keyed object
2. Refactor Tab 6 course_subcourse_data (dict vs array)
3. Restructure Tab 7 diagnostics with rules/recommendations/risks
4. Pivot Tab 3 today_distribution to weekday×part table

### Phase 3: Renames (Cosmetic but Required)
1. Global: course_name → course (Tabs 1,3,4,5A,5B,6,7)
2. Tab 4: price_krw → price, price_bucket → range
3. Tab 5A: avg_promo → with_promo, avg_non_promo → without_promo
4. Tab 6: course_sub → subcourse, yield_bucket → range
5. Add derived fields: dday (from play_date), time (from tee_time)

