"""
시간별 수집 데이터 보존 정책
매일 04:00 실행 — 오래된 시간별 스냅샷을 솎아냄

정책:
  7일 이내:   전체 보관
  8~30일:     4회/일만 보관 (06, 10, 14, 18시)
  31~90일:    1회/일만 보관 (05시)
  90일 초과:  삭제
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "golf.db"

KEEP_HOURS_WARM = {'05', '06', '10', '14', '18'}  # 8~30일 보존 시간
KEEP_HOURS_COLD = {'05'}                            # 31~90일 보존 시간


def compact_hourly_snapshots(today=None):
    """보존 정책에 따라 오래된 시간별 스냅샷 삭제."""
    if today is None:
        today = datetime.now().date()

    db = sqlite3.connect(DB_PATH)

    d7 = (today - timedelta(days=7)).isoformat()
    d30 = (today - timedelta(days=30)).isoformat()
    d90 = (today - timedelta(days=90)).isoformat()

    # 90일 초과: 전부 삭제
    r1 = db.execute(
        "DELETE FROM tee_time_snapshots WHERE collected_date < ?", (d90,)
    )
    deleted_archive = r1.rowcount

    # 31~90일: 05시만 보존
    keep_cold = ",".join(f"'{h}'" for h in KEEP_HOURS_COLD)
    r2 = db.execute(f"""
        DELETE FROM tee_time_snapshots
        WHERE collected_date >= ? AND collected_date < ?
          AND collected_at IS NOT NULL
          AND substr(collected_at, 12, 2) NOT IN ({keep_cold})
    """, (d90, d30))
    deleted_cold = r2.rowcount

    # 8~30일: 06,10,14,18시만 보존
    keep_warm = ",".join(f"'{h}'" for h in KEEP_HOURS_WARM)
    r3 = db.execute(f"""
        DELETE FROM tee_time_snapshots
        WHERE collected_date >= ? AND collected_date < ?
          AND collected_at IS NOT NULL
          AND substr(collected_at, 12, 2) NOT IN ({keep_warm})
    """, (d30, d7))
    deleted_warm = r3.rowcount

    # slot_status_history도 동일 정책 (90일 초과 삭제)
    r4 = db.execute(
        "DELETE FROM slot_status_history WHERE collected_date < ?", (d90,)
    )
    deleted_ssh = r4.rowcount

    db.commit()

    total = deleted_archive + deleted_cold + deleted_warm
    print(f"[보존정책] 삭제 완료: {total:,}건")
    print(f"  90일+: {deleted_archive:,} | 31~90일: {deleted_cold:,} | 8~30일: {deleted_warm:,}")
    print(f"  slot_status_history: {deleted_ssh:,}")

    # 주 1회 VACUUM (일요일)
    if today.weekday() == 6:
        print("[보존정책] VACUUM 실행 중...")
        db.execute("VACUUM")
        print("[보존정책] VACUUM 완료")

    db.close()
    return total


if __name__ == "__main__":
    compact_hourly_snapshots()
