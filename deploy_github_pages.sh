#!/bin/bash
# ──────────────────────────────────────────────
# 골프 대시보드 → GitHub Pages 자동 배포
# Mac 터미널에서 실행: bash deploy_github_pages.sh
# ──────────────────────────────────────────────

set -e

# ── 설정 ──
REPO_NAME="kakao-golf-dashboard"
BRANCH="main"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🏌️ 골프 대시보드 GitHub Pages 배포"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1) gh CLI 확인
if ! command -v gh &> /dev/null; then
    echo "⚠️  gh CLI가 없습니다. 설치 중..."
    if command -v brew &> /dev/null; then
        brew install gh
    else
        echo "❌ Homebrew가 없습니다. 먼저 설치하세요:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo "   brew install gh"
        exit 1
    fi
fi

# 2) GitHub 로그인 확인
if ! gh auth status &> /dev/null; then
    echo "🔑 GitHub 로그인이 필요합니다..."
    gh auth login
fi

GITHUB_USER=$(gh api user --jq .login)
echo "✅ GitHub 계정: $GITHUB_USER"

# 3) docs 폴더 준비 (GitHub Pages용)
DOCS_DIR="$SCRIPT_DIR/docs"
mkdir -p "$DOCS_DIR"

echo "📦 파일 복사 중..."
cp "$SCRIPT_DIR/golf_dashboard.html" "$DOCS_DIR/index.html"

# tab8 JSON 파일도 복사
for f in "$SCRIPT_DIR"/golf_tab8_*.json; do
    [ -f "$f" ] && cp "$f" "$DOCS_DIR/"
done

echo "   → docs/index.html ($(du -h "$DOCS_DIR/index.html" | cut -f1))"

# 4) Git 초기화 (처음만)
cd "$SCRIPT_DIR"
if [ ! -d ".git" ]; then
    echo "🔧 Git 저장소 초기화..."
    git init
    git branch -M "$BRANCH"

    # .gitignore
    cat > .gitignore << 'GITIGNORE'
__pycache__/
*.pyc
*.db
*.db-journal
node_modules/
.DS_Store
GITIGNORE
fi

# 5) GitHub 리포 생성 (없으면)
if ! gh repo view "$GITHUB_USER/$REPO_NAME" &> /dev/null; then
    echo "🆕 GitHub 리포 생성: $REPO_NAME"
    gh repo create "$REPO_NAME" --public --source=. --remote=origin --push
else
    echo "✅ 리포 존재: $GITHUB_USER/$REPO_NAME"
    # remote 설정 확인
    if ! git remote get-url origin &> /dev/null; then
        git remote add origin "https://github.com/$GITHUB_USER/$REPO_NAME.git"
    fi
fi

# 6) 커밋 & 푸시
echo "📤 배포 중..."
git add docs/
git add -A --ignore-errors 2>/dev/null || true
git commit -m "📊 대시보드 업데이트 $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || echo "(변경사항 없음)"
git push -u origin "$BRANCH" 2>/dev/null || git push origin "$BRANCH"

# 7) GitHub Pages 활성화
echo "🌐 GitHub Pages 설정..."
gh api -X PUT "repos/$GITHUB_USER/$REPO_NAME/pages" \
    -f "source[branch]=$BRANCH" \
    -f "source[path]=/docs" 2>/dev/null \
|| gh api -X POST "repos/$GITHUB_USER/$REPO_NAME/pages" \
    -f "source[branch]=$BRANCH" \
    -f "source[path]=/docs" 2>/dev/null \
|| echo "(Pages 이미 설정됨)"

PAGES_URL="https://$GITHUB_USER.github.io/$REPO_NAME/"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 배포 완료!"
echo ""
echo "🔗 URL: $PAGES_URL"
echo ""
echo "📱 폰에서 이 URL을 열면 대시보드가 보입니다."
echo "   (처음 배포 시 1~2분 후 접속 가능)"
echo ""
echo "🔄 다음에 업데이트할 때는 이 스크립트를 다시 실행하면 됩니다:"
echo "   bash deploy_github_pages.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
