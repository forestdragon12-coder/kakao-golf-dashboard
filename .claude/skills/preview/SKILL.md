---
name: preview
description: 대시보드 빌드 후 로컬 브라우저에서 미리보기
allowed-tools: Bash(*)
---

# 대시보드 로컬 미리보기

아래 순서대로 실행:

1. **빌드**: 대시보드 데이터 생성 + HTML 빌드
   ```bash
   cd ~/kakao_golf && source venv/bin/activate && python3 -c "from build_dashboard import main; main()"
   ```

2. **로컬 서버 확인 및 시작**: 8080 포트에 이미 서버가 있으면 유지, 없으면 시작
   ```bash
   cd ~/kakao_golf && lsof -ti:8080 >/dev/null 2>&1 || (python3 -m http.server 8080 &>/dev/null &)
   ```

3. **브라우저 열기**:
   ```bash
   open http://localhost:8080/golf_dashboard.html
   ```

4. 사용자에게 알림: "로컬 미리보기가 열렸습니다. 확인 후 배포하려면 `/deploy`를 입력하세요."
