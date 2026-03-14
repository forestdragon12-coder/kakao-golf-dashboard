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
# 회원제·대중제 sub-course 구분이 있는 골프장
# - membership_type 컬럼이 있을 때만 적용 (나머지 6개는 단일 구조)
# - 회원제 슬롯은 오픈 여부가 날에 따라 다름 → member_open_flag 별도 판단
# ─────────────────────────────────────────────────────────────────
MEMBER_COURSES = {
    "골드레이크": {
        "대중제": ["밸리(대중제)", "힐(대중제)"],
        "회원제": ["골드(회원제)", "레이크(회원제)"],
        # 회원제 특징: 특가 없음, 정가 유지, 100,000~160,000원
        # 대중제 특징: 특가 산발적, 80,000~140,000원
    },
    "해피니스": {
        "대중제": ["하트(대중제)", "힐링(대중제)"],
        "회원제": ["해피(회원제)", "휴먼(회원제)"],
        # 회원제 특징: 오픈 시 전부 특가, 60,000~105,500원
        # 대중제 특징: 전부 특가, 40,500~65,000원
    },
}

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
