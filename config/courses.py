# 카카오골프 검색어 목록 (표시 이름 그대로)
COURSES = [
    "광주CC",
    "르오네뜨",
    "어등산",
    "베르힐",
    "푸른솔장성",
    "해피니스",
    "골드레이크",
    "무등산",
]

# ─────────────────────────────────────────────────────────────────
# 골프장 상세 프로필
# - type: 대중제 / 회원제 / 혼합(회원제+대중제)
# - member_count: 회원권 수 (None = 미확인, 추후 기입)
# - note: 특이사항
# ─────────────────────────────────────────────────────────────────
COURSE_PROFILES = {
    "광주CC": {
        "type": "대중제",
        "member_count": None,
        "holes": 27,
        "sub_courses": ["동악", "설산", "섬진"],
        "tee_interval_min": 7,
        "operating_hours": [6, 16],
        "cart_fee_team": 100000,
        "cart_fee_person": 25000,
        "member_avg_weekday": 60757,
        "member_avg_weekend": 73426,
        "note": "1983년 개장, 전남 최초 골프장",
    },
    "르오네뜨": {
        "type": "대중제",
        "member_count": None,
        "holes": 18,
        "sub_courses": ["IN", "OUT"],
        "tee_interval_min": 7,
        "operating_hours": [6, 16],
        "cart_fee_team": 100000,
        "cart_fee_person": 25000,
        "member_avg_weekday": None,
        "member_avg_weekend": None,
        "note": "2023년 개장, 소수 지분 분양 특수구조",
    },
    "무등산": {
        "type": "대중제",
        "member_count": None,
        "holes": 27,
        "sub_courses": ["인왕봉", "지왕봉", "천왕봉"],
        "tee_interval_min": 7,
        "operating_hours": [6, 16],
        "cart_fee_team": 100000,
        "cart_fee_person": 25000,
        "member_avg_weekday": None,
        "member_avg_weekend": None,
        "note": "2010년 개장, 2016년 회원제→퍼블릭 전환",
    },
    "베르힐": {
        "type": "대중제",
        "member_count": None,
        "holes": 27,
        "sub_courses": ["Lake", "Sky", "Verthill"],
        "tee_interval_min": 7,
        "operating_hours": [6, 16],
        "cart_fee_team": 100000,
        "cart_fee_person": 25000,
        "member_avg_weekday": None,
        "member_avg_weekend": None,
        "note": "2023년 개장, 함평 소재",
    },
    "어등산": {
        "type": "혼합",
        "member_count": None,
        "holes": 27,
        "member_holes": 18,
        "public_holes": 9,
        "sub_courses": ["어등", "송정", "하남"],
        "member_subs": None,
        "public_subs": None,
        "tee_interval_min": 7,
        "operating_hours": [6, 16],
        "cart_fee_team": 100000,
        "cart_fee_person": 25000,
        "member_avg_weekday": None,
        "member_avg_weekend": None,
        "note": "회원제 18홀 + 대중제 9홀, 코스 구분 미확인",
    },
    "푸른솔장성": {
        "type": "대중제",
        "member_count": None,
        "holes": 27,
        "sub_courses": ["레이크", "마운틴", "힐"],
        "tee_interval_min": 7,
        "operating_hours": [6, 16],
        "cart_fee_team": 100000,
        "cart_fee_person": 25000,
        "member_avg_weekday": None,
        "member_avg_weekend": None,
        "note": "",
    },
    "골드레이크": {
        "type": "혼합",
        "member_count": None,
        "holes": 36,
        "member_holes": 18,
        "public_holes": 18,
        "sub_courses": ["밸리", "힐", "골드", "레이크"],
        "member_subs": ["골드(회원제)", "레이크(회원제)"],
        "public_subs": ["밸리(대중제)", "힐(대중제)"],
        "tee_interval_min": 7,
        "operating_hours": [6, 16],
        "cart_fee_team": 80000,
        "cart_fee_person": 20000,
        "member_avg_weekday": 102505,
        "member_avg_weekend": 121499,
        "note": "카카오골프에서 회원/대중 태그 구분됨",
    },
    "해피니스": {
        "type": "혼합",
        "member_count": None,
        "holes": 45,
        "member_holes": 18,
        "public_holes": 27,
        "sub_courses": ["하트", "히든", "힐링", "해피", "휴먼"],
        "member_subs": ["해피(회원제)", "휴먼(회원제)"],
        "public_subs": ["하트(대중제)", "히든(대중제)", "힐링(대중제)"],
        "tee_interval_min": 7,
        "operating_hours": [6, 16],
        "cart_fee_team": 70000,
        "cart_fee_person": 17500,
        "member_avg_weekday": 78247,
        "member_avg_weekend": 95030,
        "note": "카카오골프에서 회원/대중 태그 구분됨",
    },
}

# ─────────────────────────────────────────────────────────────────
# 회원제·대중제 sub-course 구분 (카카오골프 데이터에서 태그 있는 골프장)
# ─────────────────────────────────────────────────────────────────
MEMBER_COURSES = {
    "골드레이크": {
        "대중제": ["밸리(대중제)", "힐(대중제)"],
        "회원제": ["골드(회원제)", "레이크(회원제)"],
    },
    "해피니스": {
        "대중제": ["하트(대중제)", "힐링(대중제)", "히든(대중제)"],
        "회원제": ["해피(회원제)", "휴먼(회원제)"],
    },
}

# ─────────────────────────────────────────────────────────────────
# 코스별 9홀 단위 수 (슬롯/9홀 정규화용)
# ─────────────────────────────────────────────────────────────────
COURSE_HOLES = {
    "광주CC":     {"units": 3},                              # 동악/설산/섬진
    "르오네뜨":   {"units": 2},                              # IN/OUT
    "무등산":     {"units": 3},                              # 인왕/지왕/천왕
    "베르힐":     {"units": 3},                              # Lake/Sky/Verthill
    "어등산":     {"units": 3},                              # 송정/어등/하남
    "푸른솔장성": {"units": 3},                              # 레이크/마운틴/힐
    "골드레이크": {"units": 4, "대중제": 2, "회원제": 2},    # 밸리/힐 + 골드/레이크
    "해피니스":   {"units": 5, "대중제": 3, "회원제": 2},    # 하트/히든/힐링 + 해피/휴먼
}

# 월별 9홀당 최대 팀수 (일조시간/계절 반영)
MONTHLY_MAX_TEAMS_PER_9H = {
    1: 58, 2: 65, 3: 74, 4: 83, 5: 91, 6: 95,
    7: 93, 8: 87, 9: 78, 10: 69, 11: 61, 12: 56,
}

# 빈 티 분류 비율 (초기 가정값)
GROUP_RATIO = {
    "weekday": 0.30,  # 평일 단체 비율
    "weekend": 0.10,  # 주말 단체 비율
}
GROUP_DISCOUNT = 15000  # 단체 할인액 (비회원가 - 이 값)

def get_daily_max_teams(course_name, month):
    """골프장의 해당 월 하루 최대 팀수."""
    units = get_hole_units(course_name)
    max_per_9h = MONTHLY_MAX_TEAMS_PER_9H.get(month, 74)
    return units * max_per_9h

def get_hole_units(course_name: str, membership_type: str = None) -> int:
    """9홀 단위 수 반환. 회원제 코스는 membership_type별 분리 가능."""
    info = COURSE_HOLES.get(course_name, {"units": 1})
    if membership_type and membership_type in info:
        return info[membership_type]
    return info["units"]


def is_member_sub(course_name: str, course_sub: str) -> bool:
    """해당 course_sub가 회원제 슬롯인지 반환"""
    info = MEMBER_COURSES.get(course_name)
    if not info or not course_sub:
        return False
    return course_sub in info.get("회원제", [])

def has_member_tier(course_name: str) -> bool:
    """회원제/대중제 구분이 있는 골프장인지 반환"""
    return course_name in MEMBER_COURSES

def get_season(month: int) -> str:
    if month in (3, 4, 5):   return "봄"
    if month in (6, 7, 8):   return "여름"
    if month in (9, 10, 11): return "가을"
    return "겨울"

def get_weekday_type(weekday: int) -> str:
    # 0=월 ~ 6=일
    if weekday == 5: return "토요일"
    if weekday == 6: return "일요일"
    return "평일"

def get_part_type(hour: int) -> str:
    if hour < 11: return "1부"
    if hour < 14: return "2부"
    return "오후"
