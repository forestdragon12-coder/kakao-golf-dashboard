#!/bin/bash
# ──────────────────────────────────────────────
# 골프 대시보드 자동 파이프라인
# 크롤링 후 실행하면: 데이터 생성 → 빌드 → GitHub Pages 배포
#
# 사용법:
#   bash auto_deploy.sh          # 빌드 + 배포만
#   bash auto_deploy.sh --crawl  # 크롤링부터 전체 실행
#
# crontab 자동화 (매일 오전 6시):
#   0 6 * * * cd ~/Desktop/kakao_golf && bash auto_deploy.sh --crawl >> logs/auto_deploy.log 2>&1
# ──────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏌️ 골프 대시보드 자동 파이프라인"
echo "   $TIMESTAMP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1) 크롤링 (옵션) ──
if [[ "$1" == "--crawl" ]]; then
    echo ""
    echo "📡 [1/4] 크롤링 시작..."
    python3 run.py 2>&1 | tee "$LOG_DIR/crawl_$(date '+%Y%m%d_%H%M').log"
    if [ $? -ne 0 ]; then
        echo "❌ 크롤링 실패!"
        exit 1
    fi
    echo "✅ 크롤링 완료"
else
    echo ""
    echo "⏭️  [1/4] 크롤링 스킵 (--crawl 옵션으로 포함 가능)"
fi

# ── 2) 대시보드 데이터 생성 ──
echo ""
echo "📊 [2/4] 대시보드 데이터 생성..."
python3 generate_dashboard_data.py
echo "✅ 데이터 생성 완료"

# ── 3) HTML 빌드 ──
echo ""
echo "🔨 [3/4] HTML 빌드..."
python3 build_dashboard.py
echo "✅ 빌드 완료"

# ── 4) GitHub Pages 배포 ──
echo ""
echo "🚀 [4/4] GitHub Pages 배포..."

# docs 폴더에 복사
mkdir -p docs
cp golf_dashboard.html docs/index.html
for f in golf_tab8_*.json; do
    [ -f "$f" ] && cp "$f" docs/
done

# git push
git add docs/
git commit -m "📊 자동 업데이트 $(date '+%m/%d %H:%M')" 2>/dev/null || { echo "(변경사항 없음)"; exit 0; }
git push origin main

GITHUB_USER=$(gh api user --jq .login 2>/dev/null || echo "forestdragon12-coder")
PAGES_URL="https://$GITHUB_USER.github.io/kakao-golf-dashboard/"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 배포 완료! ($TIMESTAMP)"
echo "🔗 $PAGES_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
