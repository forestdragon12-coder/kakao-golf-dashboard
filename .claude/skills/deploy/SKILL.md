---
name: deploy
description: 대시보드를 Firebase에 배포 (반드시 /preview 후 사용)
allowed-tools: Bash(*)
---

# Firebase 배포

사용자가 로컬 미리보기를 확인한 후 배포를 요청할 때 실행합니다.

1. **배포 전 확인**: "Firebase에 배포합니다. 진행할까요?"라고 사용자에게 확인

2. **Firebase Hosting 배포**:
   ```bash
   cd ~/kakao_golf && firebase deploy --only hosting 2>&1
   ```

3. **Firebase Storage 데이터 업로드**:
   ```bash
   cd ~/kakao_golf && source venv/bin/activate && python3 upload_dashboard_data.py 2>&1
   ```

4. 배포 결과를 사용자에게 보고
