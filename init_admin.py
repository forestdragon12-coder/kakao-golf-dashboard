"""
Verhill Radar — 초기 관리자(admin) 계정 등록
Firebase Admin SDK로 Firestore에 직접 등록

사용법:
  pip install firebase-admin
  python init_admin.py your-email@gmail.com "관리자이름"
"""
import sys
import json
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("사용법: python init_admin.py <이메일> <이름>")
        print("예시:   python init_admin.py admin@gmail.com 홍길동")
        sys.exit(1)

    email = sys.argv[1]
    name = sys.argv[2]

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        print("firebase-admin 설치 필요:")
        print("  pip install firebase-admin")
        sys.exit(1)

    # 서비스 계정 키 파일 확인
    key_path = Path(__file__).parent / "service-account-key.json"
    if not key_path.exists():
        print(f"\n서비스 계정 키 파일이 필요합니다: {key_path}")
        print("\n발급 방법:")
        print("1. Firebase 콘솔 → 프로젝트 설정 (톱니바퀴)")
        print("2. '서비스 계정' 탭")
        print("3. '새 비공개 키 생성' 클릭")
        print(f"4. 다운로드된 JSON 파일을 {key_path} 로 저장")
        sys.exit(1)

    # Firebase 초기화
    cred = credentials.Certificate(str(key_path))
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    # admin 등록
    db.collection('approved_users').document(email).set({
        'email': email,
        'self_name': name,
        'admin_name': name,
        'role': 'admin',
        'active': True,
        'approved_at': firestore.SERVER_TIMESTAMP,
        'approved_by': 'system_init',
    })

    print(f"✅ 관리자 등록 완료: {email} ({name})")
    print(f"   등급: admin")
    print(f"   이제 대시보드에서 구글 로그인하면 바로 접속됩니다.")

    # 기본 설정 등록
    db.collection('settings').document('security').set({
        'session_durations': {'admin': 0, 'manager': 72, 'viewer': 24, 'guest': 6},
        'guest_allowed_tabs': [0, 3],
        'watermark_opacity': {'manager': 0.08, 'viewer': 0.20, 'guest': 0.20},
    })
    print(f"✅ 보안 설정 초기화 완료")


if __name__ == "__main__":
    main()
