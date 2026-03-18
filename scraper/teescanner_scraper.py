"""
티스캐너(골프존) API 스크래퍼
- Playwright 불필요 (순수 HTTP API 호출)
- 카카오골프 스크래퍼와 동일 포맷으로 DB 저장
- foapi.teescanner.com REST API 사용
"""
import asyncio
import json
import ssl
import urllib.request
from datetime import date, timedelta, datetime
from html import unescape
from loguru import logger

from config.courses import COURSES, get_season, get_weekday_type, get_part_type
from db.database import (
    make_hash,
    make_slot_identity_key,
    make_slot_key,
    make_slot_observation_key,
    normalize_course_variant,
)

API_BASE = "https://foapi.teescanner.com/v1"
COLLECT_DAYS = 30
SOURCE_CHANNEL = "teescanner"

# SSL 우회 (macOS 인증서 이슈)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _api_post(endpoint: str, fields: dict) -> dict:
    """multipart/form-data POST 요청"""
    boundary = "----WebKitFormBoundary7MA4YWxk"
    body = ""
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
    body += f"--{boundary}--\r\n"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.teescanner.com/",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "x-client-version": "2.0.0",
        "x-client-build": "1",
    }
    req = urllib.request.Request(
        f"{API_BASE}/{endpoint}", data=body.encode(), headers=headers, method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=20, context=_SSL_CTX)
    return json.loads(resp.read())


def _clean(s):
    """HTML 엔티티 정리"""
    if not s:
        return s
    return unescape(str(s)).replace("&gt;", ">").replace("&lt;", "<").replace("&#40;", "(").replace("&#41;", ")")


class TeescannerScraper:
    """티스캐너 API 기반 스크래퍼 (카카오 스크래퍼 호환)"""

    def __init__(self):
        self.course_map = {}  # golfclub_name → golfclub_seq

    def fetch_all_courses(self) -> list:
        """전체 골프장 목록 조회 (369+개)"""
        data = _api_post("booking/getGolfclubListByGolfclub", {
            "page": "1", "page_size": "500", "orderType": "distance",
            "roundDay": date.today().strftime("%Y-%m-%d"),
            "userLatitude": "35.1", "userLongitude": "126.9",
            "tab": "golfcourse", "isScroll": "N",
        })
        courses = data.get("data", {}).get("golfclubList", [])
        for c in courses:
            c["golfclub_name"] = _clean(c.get("golfclub_name", ""))
            self.course_map[c["golfclub_name"]] = c
        logger.info(f"[티스캐너] 전체 {len(courses)}개 골프장 로드")
        return courses

    def fetch_teetimes(self, play_date: str, page_size: int = 9999) -> list:
        """특정 날짜의 전체 티타임 조회"""
        data = _api_post("booking/getGolfclubListByTeetime", {
            "page": "1", "page_size": str(page_size), "orderType": "distance",
            "roundDay": play_date,
            "userLatitude": "35.1", "userLongitude": "126.9",
            "tab": "teetime", "isScroll": "N",
        })
        teetimes = data.get("data", {}).get("golfclubList", [])
        # HTML 엔티티 정리
        for t in teetimes:
            t["golfclub_name"] = _clean(t.get("golfclub_name", ""))
            t["course_name"] = _clean(t.get("course_name", ""))
            t["area_name"] = _clean(t.get("area_name", ""))
        return teetimes

    def collect_courses(self, target_courses: list = None) -> list:
        """
        기존 카카오 스크래퍼와 동일 포맷의 row 리스트 반환.
        target_courses: 수집 대상 골프장명 리스트 (None이면 config.COURSES)
        """
        targets = set(target_courses or COURSES)
        collected_date = date.today().strftime("%Y-%m-%d")
        all_rows = []

        logger.info(f"[티스캐너] {len(targets)}개 골프장 × {COLLECT_DAYS}일 수집 시작")

        for d_day in range(1, COLLECT_DAYS + 1):
            play_dt = date.today() + timedelta(days=d_day)
            play_date = play_dt.strftime("%Y-%m-%d")
            weekday_type = get_weekday_type(play_dt)
            season = get_season(play_dt)

            try:
                teetimes = self.fetch_teetimes(play_date)
            except Exception as e:
                logger.warning(f"[티스캐너] {play_date} 조회 실패: {e}")
                continue

            day_count = 0
            for tt in teetimes:
                course_name = tt["golfclub_name"]
                if course_name not in targets:
                    continue

                tee_time_raw = tt.get("teetime_time", "")
                # "0647" → "06:47"
                if len(tee_time_raw) == 4:
                    tee_time = f"{tee_time_raw[:2]}:{tee_time_raw[2:]}"
                else:
                    tee_time = tee_time_raw

                hour = int(tee_time_raw[:2]) if tee_time_raw and len(tee_time_raw) >= 2 else 0
                part_type = get_part_type(hour)

                price = tt.get("price") or tt.get("offline_cost") or 0
                base_cost = tt.get("base_cost") or price
                discount_cost = tt.get("discount_cost") or 0
                promo_flag = 1 if tt.get("discount_yn") == "Y" or tt.get("secret_discount_yn") == "Y" else 0
                promo_text = _clean(tt.get("discount_nm") or tt.get("secret_discount_name") or "")
                course_sub = tt.get("course_name", "")  # 서브코스명
                pax = tt.get("offline_cost_for_4_people", 0)

                # 카카오 스크래퍼와 동일 포맷
                row = {
                    "course_name": course_name,
                    "collected_date": collected_date,
                    "play_date": play_date,
                    "tee_time": tee_time,
                    "price_krw": price,
                    "course_sub": course_sub,
                    "membership_type": "",
                    "promo_flag": promo_flag,
                    "promo_text": promo_text,
                    "pax_condition": f"{tt.get('visitor_cnt', 4)}인" if tt.get("visitor_cnt") else "4인",
                    "price_type": promo_text if promo_flag else "정상가",
                    "d_day": d_day,
                    "part_type": part_type,
                    "season": season,
                    "weekday_type": weekday_type,
                    "source_channel": SOURCE_CHANNEL,
                    "course_variant": normalize_course_variant(course_name),
                    "listed_price_krw": base_cost,
                    "normal_price_krw": base_cost,
                    "sale_price_krw": price if promo_flag else None,
                    "price_badge": tt.get("product_tag_nm", ""),
                }

                # 키 생성 (카카오 스크래퍼 호환)
                collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row["slot_identity_key"] = make_slot_identity_key(
                    0, play_date, tee_time, part_type, row["course_variant"], SOURCE_CHANNEL
                )
                row["slot_observation_key"] = make_slot_observation_key(
                    row["slot_identity_key"], collected_at
                )
                row["hash_key"] = make_hash(
                    course_name, collected_at, play_date, tee_time, course_sub
                )

                all_rows.append(row)
                day_count += 1

            if day_count > 0:
                logger.debug(f"  D-{d_day} ({play_date}): {day_count}건")

        logger.info(f"[티스캐너] 수집 완료: {len(all_rows)}건")
        return all_rows

    def get_course_info(self, course_name: str) -> dict:
        """골프장 부가 정보 (평점, 지역, 가격대 등)"""
        if not self.course_map:
            self.fetch_all_courses()
        info = self.course_map.get(course_name, {})
        return {
            "name": course_name,
            "region": _clean(info.get("area_name", "")),
            "rating": info.get("avg_grade"),
            "base_price": info.get("base_cost"),
            "min_price": info.get("price"),
            "distance_km": info.get("distance"),
            "golfclub_code": info.get("golfclub_code"),
            "golfclub_seq": info.get("golfclub_seq"),
        }
