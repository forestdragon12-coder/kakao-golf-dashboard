"""
Verhill Radar — 대시보드 데이터를 Firebase Storage에 업로드
스크래퍼 완료 후 자동 실행됨

사용법:
  python upload_dashboard_data.py
"""
import json
from pathlib import Path

def main():
    try:
        import firebase_admin
        from firebase_admin import credentials, storage
    except ImportError:
        print("firebase-admin 필요: pip install firebase-admin")
        return

    key_path = Path(__file__).parent / "service-account-key.json"
    if not key_path.exists():
        print(f"서비스 계정 키 없음: {key_path}")
        return

    # Firebase 초기화 (이미 초기화된 경우 재사용)
    try:
        app = firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(str(key_path))
        app = firebase_admin.initialize_app(cred, {
            "storageBucket": "verhill-radar.firebasestorage.app"
        })

    bucket = storage.bucket()
    base = Path(__file__).parent

    # 1. dashboard_data.json 업로드
    data_path = base / "dashboard_data.json"
    if data_path.exists():
        blob = bucket.blob("dashboard/dashboard_data.json")
        blob.upload_from_filename(str(data_path), content_type="application/json")
        size_kb = data_path.stat().st_size / 1024
        print(f"✅ dashboard_data.json 업로드 ({size_kb:.0f} KB)")

    # 2. tab8 날짜별 JSON 업로드
    for tab8_file in sorted(base.glob("golf_tab8_*.json")):
        blob = bucket.blob(f"dashboard/{tab8_file.name}")
        blob.upload_from_filename(str(tab8_file), content_type="application/json")
        size_kb = tab8_file.stat().st_size / 1024
        print(f"✅ {tab8_file.name} 업로드 ({size_kb:.0f} KB)")

    # 3. 최신 tab8 (오늘 데이터)
    tab8_path = base / "golf_tab8.json"
    if tab8_path.exists():
        blob = bucket.blob("dashboard/golf_tab8_today.json")
        blob.upload_from_filename(str(tab8_path), content_type="application/json")
        size_kb = tab8_path.stat().st_size / 1024
        print(f"✅ golf_tab8_today.json 업로드 ({size_kb:.0f} KB)")

    # 4. 날짜별 풀 대시보드 아카이브 업로드
    archive_dir = base / "dashboard_archive"
    if archive_dir.exists():
        for archive_file in sorted(archive_dir.glob("dashboard_data_*.json")):
            remote_path = f"dashboard/archive/{archive_file.name}"
            blob = bucket.blob(remote_path)
            # 이미 업로드된 파일은 스킵 (존재 확인)
            if blob.exists():
                continue
            blob.upload_from_filename(str(archive_file), content_type="application/json")
            size_mb = archive_file.stat().st_size / 1024 / 1024
            print(f"✅ archive/{archive_file.name} 업로드 ({size_mb:.1f} MB)")

    print("🎯 전체 업로드 완료")


if __name__ == "__main__":
    main()
