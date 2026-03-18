"""
기상 데이터 수집기
기상청 단기예보 API → weather_observations / weather_forecasts 테이블
"""
import os
import json
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "golf.db"
API_KEY = os.environ.get("KMA_API_KEY", "")

# .env에서 로드
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists() and not API_KEY:
    for line in _env_path.read_text().splitlines():
        if line.startswith("KMA_API_KEY="):
            API_KEY = line.split("=", 1)[1].strip()

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.weather import COURSE_WEATHER_GRID

BASE_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"


def _api_call(endpoint, params):
    """기상청 API 호출."""
    params["serviceKey"] = API_KEY
    params["dataType"] = "JSON"
    params["numOfRows"] = "1000"
    params["pageNo"] = "1"
    url = f"{BASE_URL}/{endpoint}?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            return items if isinstance(items, list) else []
    except Exception as e:
        print(f"  기상청 API 오류: {e}")
        return []


def _ensure_tables(conn):
    """기상 테이블 생성."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS weather_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_date TEXT NOT NULL,
            course_name TEXT NOT NULL,
            temperature REAL,
            rainfall REAL,
            humidity REAL,
            wind_speed REAL,
            precip_type INTEGER,
            sky_condition INTEGER,
            observed_at TEXT,
            UNIQUE(collected_date, course_name)
        );
        CREATE TABLE IF NOT EXISTS weather_forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            forecast_date TEXT NOT NULL,
            play_date TEXT NOT NULL,
            course_name TEXT NOT NULL,
            rain_prob INTEGER,
            temperature_high REAL,
            temperature_low REAL,
            precip_type INTEGER,
            sky_condition INTEGER,
            prev_rain_prob INTEGER,
            forecast_changed TEXT,
            UNIQUE(forecast_date, play_date, course_name)
        );
    """)


def collect_weather(report_date=None):
    """기상 실황 + 단기예보 수집.

    report_date: 수집 기준일 (기본: 오늘)
    """
    if not API_KEY:
        print("KMA_API_KEY 미설정 → 기상 수집 스킵")
        return 0

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)

    if not report_date:
        report_date = datetime.now().strftime("%Y-%m-%d")

    now = datetime.now()
    base_date = report_date.replace("-", "")
    # 가장 가까운 발표 시간 (0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300)
    hour = now.hour
    announce_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    base_time = max([h for h in announce_hours if h <= hour], default=23)
    base_time_str = f"{base_time:02d}00"

    total_records = 0

    for course_name, grid in COURSE_WEATHER_GRID.items():
        nx, ny = grid["nx"], grid["ny"]

        # ── 1. 초단기실황 (현재 날씨) ──
        items = _api_call("getUltraSrtNcst", {
            "base_date": base_date,
            "base_time": f"{hour:02d}00",
            "nx": nx, "ny": ny,
        })
        obs = {}
        for item in items:
            cat = item.get("category")
            val = item.get("obsrValue")
            if cat == "T1H": obs["temperature"] = float(val)
            elif cat == "RN1": obs["rainfall"] = float(val)
            elif cat == "REH": obs["humidity"] = float(val)
            elif cat == "WSD": obs["wind_speed"] = float(val)
            elif cat == "PTY": obs["precip_type"] = int(float(val))

        if obs:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO weather_observations
                    (collected_date, course_name, temperature, rainfall, humidity,
                     wind_speed, precip_type, observed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (report_date, course_name,
                      obs.get("temperature"), obs.get("rainfall"),
                      obs.get("humidity"), obs.get("wind_speed"),
                      obs.get("precip_type"), now.isoformat()))
                total_records += 1
            except Exception as e:
                print(f"  {course_name} 실황 저장 오류: {e}")

        # ── 2. 단기예보 (향후 7일 경기일) ──
        items = _api_call("getVilageFcst", {
            "base_date": base_date,
            "base_time": base_time_str,
            "nx": nx, "ny": ny,
        })

        # 예보를 날짜별로 그룹핑
        fc_by_date = {}
        for item in items:
            fc_date = item.get("fcstDate", "")
            cat = item.get("category", "")
            val = item.get("fcstValue", "")
            if fc_date not in fc_by_date:
                fc_by_date[fc_date] = {}
            if cat == "POP": fc_by_date[fc_date]["rain_prob"] = int(val)
            elif cat == "TMX": fc_by_date[fc_date]["temp_high"] = float(val)
            elif cat == "TMN": fc_by_date[fc_date]["temp_low"] = float(val)
            elif cat == "PTY":
                # 가장 높은 강수형태 유지
                cur = fc_by_date[fc_date].get("precip_type", 0)
                fc_by_date[fc_date]["precip_type"] = max(cur, int(val))
            elif cat == "SKY":
                cur = fc_by_date[fc_date].get("sky_condition", 1)
                fc_by_date[fc_date]["sky_condition"] = max(cur, int(val))

        for fc_date, fc in fc_by_date.items():
            play_date = f"{fc_date[:4]}-{fc_date[4:6]}-{fc_date[6:]}"

            # 전일 예보 조회 (예보 변화 감지)
            cursor = conn.execute(
                "SELECT rain_prob FROM weather_forecasts WHERE play_date=? AND course_name=? ORDER BY forecast_date DESC LIMIT 1",
                (play_date, course_name))
            prev = cursor.fetchone()
            prev_rain = prev["rain_prob"] if prev else None

            # 예보 변화 판정
            changed = "유지"
            if prev_rain is not None and fc.get("rain_prob") is not None:
                diff = fc["rain_prob"] - prev_rain
                if diff >= 20: changed = "악화"
                elif diff <= -20: changed = "호전"

            try:
                conn.execute("""
                    INSERT OR REPLACE INTO weather_forecasts
                    (forecast_date, play_date, course_name, rain_prob,
                     temperature_high, temperature_low, precip_type, sky_condition,
                     prev_rain_prob, forecast_changed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (report_date, play_date, course_name,
                      fc.get("rain_prob"), fc.get("temp_high"), fc.get("temp_low"),
                      fc.get("precip_type", 0), fc.get("sky_condition", 1),
                      prev_rain, changed))
                total_records += 1
            except Exception as e:
                print(f"  {course_name} 예보 저장 오류: {e}")

    conn.commit()
    conn.close()
    return total_records


if __name__ == "__main__":
    n = collect_weather()
    print(f"기상 수집 완료: {n}건")
