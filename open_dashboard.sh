#!/bin/bash
# open_dashboard.sh — 대시보드를 로컬 서버로 열기
# Tab 8 과거 날짜 JSON을 fetch하려면 http:// 프로토콜이 필요
# 사용법: ./open_dashboard.sh

cd "$(dirname "$0")"
PORT=8484

# 이미 사용 중인 포트 체크
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "포트 $PORT 이미 사용 중 — 기존 서버에 연결합니다."
    open "http://localhost:$PORT/golf_dashboard.html"
    exit 0
fi

echo "대시보드 서버 시작: http://localhost:$PORT/golf_dashboard.html"
python3 -m http.server $PORT --bind 127.0.0.1 &
SERVER_PID=$!
sleep 1
open "http://localhost:$PORT/golf_dashboard.html"

echo "Ctrl+C로 서버를 종료합니다."
trap "kill $SERVER_PID 2>/dev/null; echo '서버 종료'" EXIT
wait $SERVER_PID
