#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   VERHILL RADAR — 병렬 수집 (3터미널)  ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# config/courses.py에서 골프장 목록 읽기
COURSES=$(python3 -c "
from config.courses import COURSES
for c in COURSES:
    print(c)
")

# 배열로 변환
IFS=$'\n' read -r -d '' -a ARR <<< "$COURSES"
TOTAL=${#ARR[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "  ❌ 골프장이 설정되지 않았습니다. 골프장설정.command를 먼저 실행하세요."
    exit 1
fi

# 3그룹으로 분배
G1=()
G2=()
G3=()
for i in "${!ARR[@]}"; do
    case $((i % 3)) in
        0) G1+=("${ARR[$i]}") ;;
        1) G2+=("${ARR[$i]}") ;;
        2) G3+=("${ARR[$i]}") ;;
    esac
done

echo "  총 ${TOTAL}개 골프장 → 3개 터미널 병렬 수집"
echo ""
echo "  터미널1: ${G1[*]}"
echo "  터미널2: ${G2[*]}"
[ ${#G3[@]} -gt 0 ] && echo "  터미널3: ${G3[*]}"
echo ""

START=$(date +%s)

# 터미널 1: 현재 터미널에서 백그라운드
echo "  🚀 터미널1 시작..."
python3 run.py --courses ${G1[*]} --skip-analysis > /tmp/vr_collect_1.log 2>&1 &
PID1=$!

# 터미널 2
echo "  🚀 터미널2 시작..."
python3 run.py --courses ${G2[*]} --skip-analysis > /tmp/vr_collect_2.log 2>&1 &
PID2=$!

# 터미널 3 (있으면)
PID3=""
if [ ${#G3[@]} -gt 0 ]; then
    echo "  🚀 터미널3 시작..."
    python3 run.py --courses ${G3[*]} --skip-analysis > /tmp/vr_collect_3.log 2>&1 &
    PID3=$!
fi

echo ""
echo "  ⏳ 수집 중... (진행 상황은 로그 파일 참조)"
echo "     tail -f /tmp/vr_collect_1.log"
echo ""

# 완료 대기
wait $PID1
R1=$?
echo "  ✅ 터미널1 완료 (${G1[*]})"

wait $PID2
R2=$?
echo "  ✅ 터미널2 완료 (${G2[*]})"

if [ -n "$PID3" ]; then
    wait $PID3
    R3=$?
    echo "  ✅ 터미널3 완료 (${G3[*]})"
fi

END=$(date +%s)
ELAPSED=$((END - START))
MIN=$((ELAPSED / 60))
SEC=$((ELAPSED % 60))

echo ""
echo "  ════════════════════════════════════"
echo "  수집 완료! (${MIN}분 ${SEC}초)"
echo ""

# 각 터미널 결과 요약
for i in 1 2 3; do
    LOG="/tmp/vr_collect_${i}.log"
    [ -f "$LOG" ] || continue
    COUNT=$(grep -o '총 [0-9]*개' "$LOG" | tail -1 || echo "")
    echo "  터미널${i}: ${COUNT:-결과 없음}"
done

echo ""

# 분석 실행
echo "  📊 통합 분석 실행 중..."
python3 run.py --mode collect --courses ${ARR[*]} --skip-analysis 2>/dev/null

echo ""
echo "  🏗️  대시보드 빌드..."
python3 build_dashboard.py 2>&1 | tail -3

echo ""
echo "  ✅ 완료! open golf_dashboard.html 로 확인하세요"
echo "  ════════════════════════════════════"
