#!/bin/bash
# 카카오골프 티타임 수집봇 - Mac 초기 세팅 스크립트
# 실행: chmod +x setup.sh && ./setup.sh

set -e

echo "🏌️ 카카오골프 수집봇 환경 세팅 시작"
echo "================================================"

# 1. Python 버전 확인
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Python이 설치되어 있지 않습니다."
    echo "   brew install python3 으로 설치해주세요."
    exit 1
fi

PY_VERSION=$($PYTHON_CMD --version 2>&1)
echo "✅ Python: $PY_VERSION"

# 2. venv 생성
if [ ! -d "venv" ]; then
    echo "📦 가상환경 생성 중..."
    $PYTHON_CMD -m venv venv
    echo "✅ venv 생성 완료"
else
    echo "✅ venv 이미 존재"
fi

# 3. 활성화 & 패키지 설치
source venv/bin/activate
echo "📦 패키지 설치 중..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ 패키지 설치 완료"

# 4. Playwright 브라우저 설치
echo "🌐 Playwright Chromium 설치 중 (약 1~2분)..."
playwright install chromium
echo "✅ Chromium 설치 완료"

# 5. 폴더 구조 확인
mkdir -p data logs
echo "✅ 폴더 구조 확인 완료"

echo ""
echo "================================================"
echo "🎉 세팅 완료! 아래 명령어로 실행하세요:"
echo ""
echo "   source venv/bin/activate"
echo "   python run.py"
echo ""
echo "   headless=False로 설정되어 있어 브라우저 창이 뜹니다."
echo "================================================"
