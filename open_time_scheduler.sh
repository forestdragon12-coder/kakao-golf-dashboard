#!/bin/bash
# 카카오골프 통합 스케줄러 설치
# - 매일 05:00 전체 수집 + 분석 + 배포
# - 2시간마다 전체 수집 + 분석 + 배포
# - 티오픈 시간별 수집 + 분석 + 배포 (골프장별 오픈 직후)
# - 기본 스크래퍼: API 응답 가로채기

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python"
RUN_AS_USER="$(id -un)"
RUN_AS_GROUP="$(id -gn)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "🏌️ 카카오골프 통합 스케줄러 설치"
echo "================================================"
echo "스크립트: $SCRIPT_DIR"
echo "스크래퍼: API 응답 가로채기 (기본)"
echo ""

# ─── 헬퍼: plist 생성 + 로드 ───
install_daemon() {
    local LABEL="$1"
    local PLIST_PATH="/Library/LaunchDaemons/$LABEL.plist"
    local PLIST_CONTENT="$2"

    echo "$PLIST_CONTENT" | sudo tee "$PLIST_PATH" > /dev/null
    sudo launchctl bootout system/"$LABEL" 2>/dev/null || true
    sudo launchctl bootstrap system "$PLIST_PATH"
}

# ═══════════════════════════════════════════
# 0. 매일 04:00 보존 정책 (오래된 시간별 데이터 정리)
# ═══════════════════════════════════════════
LABEL_RETENTION="com.kakao.golf.retention"
install_daemon "$LABEL_RETENTION" "$(cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL_RETENTION</string>
    <key>UserName</key><string>$RUN_AS_USER</string>
    <key>GroupName</key><string>$RUN_AS_GROUP</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/db/retention.py</string>
    </array>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>4</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>$LOG_DIR/retention_out.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/retention_err.log</string>
</dict>
</plist>
PLIST
)"
echo "✅ 매일 04:00 보존 정책"

# ═══════════════════════════════════════════
# 1. 매일 05:00 전체 수집 + 분석 + 배포
# ═══════════════════════════════════════════
LABEL_DAILY="com.kakao.golf.daily"
install_daemon "$LABEL_DAILY" "$(cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL_DAILY</string>
    <key>UserName</key><string>$RUN_AS_USER</string>
    <key>GroupName</key><string>$RUN_AS_GROUP</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/run.py</string>
    </array>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>5</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>$LOG_DIR/daily_out.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/daily_err.log</string>
</dict>
</plist>
PLIST
)"
echo "✅ 매일 05:00 전체 수집 + 분석 + 배포"

# ═══════════════════════════════════════════
# 2. 2시간마다 전체 수집 + 분석 + 배포
#    2시간 간격 실행 (05시는 daily와 겹칠 수 있지만 중복 데이터는 hash_key로 무시됨)
# ═══════════════════════════════════════════
LABEL_HOURLY="com.kakao.golf.hourly"
install_daemon "$LABEL_HOURLY" "$(cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL_HOURLY</string>
    <key>UserName</key><string>$RUN_AS_USER</string>
    <key>GroupName</key><string>$RUN_AS_GROUP</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/run.py</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
    <key>StartInterval</key>
    <integer>7200</integer>
    <key>StandardOutPath</key><string>$LOG_DIR/hourly_out.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/hourly_err.log</string>
</dict>
</plist>
PLIST
)"
echo "✅ 2시간마다 전체 8개 골프장 수집 + 분석 + 배포"

# ═══════════════════════════════════════════
# 3. 티오픈 시간 수집 (골프장별 오픈 직후)
# ═══════════════════════════════════════════

# 3-1. 매일 09:00 광주CC + 골드레이크
LABEL_0900="com.kakao.golf.open.0900"
install_daemon "$LABEL_0900" "$(cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL_0900</string>
    <key>UserName</key><string>$RUN_AS_USER</string>
    <key>GroupName</key><string>$RUN_AS_GROUP</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/run.py</string>
        <string>--courses</string>
        <string>광주CC</string>
        <string>골드레이크</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>9</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>$LOG_DIR/open_0900_out.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/open_0900_err.log</string>
</dict>
</plist>
PLIST
)"
echo "✅ 매일 09:00 광주CC, 골드레이크"

# 3-2. 월요일 08:30 어등산
LABEL_MON_0830="com.kakao.golf.open.mon.0830"
install_daemon "$LABEL_MON_0830" "$(cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL_MON_0830</string>
    <key>UserName</key><string>$RUN_AS_USER</string>
    <key>GroupName</key><string>$RUN_AS_GROUP</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/run.py</string>
        <string>--courses</string>
        <string>어등산</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>8</integer>
        <key>Minute</key><integer>30</integer>
    </dict>
    <key>StandardOutPath</key><string>$LOG_DIR/open_mon_0830_out.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/open_mon_0830_err.log</string>
</dict>
</plist>
PLIST
)"
echo "✅ 월요일 08:30 어등산"

# 3-3. 월요일 10:00 베르힐 + 무등산
LABEL_MON_1000="com.kakao.golf.open.mon.1000"
install_daemon "$LABEL_MON_1000" "$(cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL_MON_1000</string>
    <key>UserName</key><string>$RUN_AS_USER</string>
    <key>GroupName</key><string>$RUN_AS_GROUP</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/run.py</string>
        <string>--courses</string>
        <string>베르힐</string>
        <string>무등산</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>10</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>$LOG_DIR/open_mon_1000_out.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/open_mon_1000_err.log</string>
</dict>
</plist>
PLIST
)"
echo "✅ 월요일 10:00 베르힐, 무등산"

# 3-4. 화요일 09:00 푸른솔장성
LABEL_TUE_0900="com.kakao.golf.open.tue.0900"
install_daemon "$LABEL_TUE_0900" "$(cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL_TUE_0900</string>
    <key>UserName</key><string>$RUN_AS_USER</string>
    <key>GroupName</key><string>$RUN_AS_GROUP</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/run.py</string>
        <string>--courses</string>
        <string>푸른솔장성</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>2</integer>
        <key>Hour</key><integer>9</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>$LOG_DIR/open_tue_0900_out.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/open_tue_0900_err.log</string>
</dict>
</plist>
PLIST
)"
echo "✅ 화요일 09:00 푸른솔장성"

# 3-5. 화요일 10:00 해피니스 + 르오네뜨
LABEL_TUE_1000="com.kakao.golf.open.tue.1000"
install_daemon "$LABEL_TUE_1000" "$(cat << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL_TUE_1000</string>
    <key>UserName</key><string>$RUN_AS_USER</string>
    <key>GroupName</key><string>$RUN_AS_GROUP</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/run.py</string>
        <string>--courses</string>
        <string>해피니스</string>
        <string>르오네뜨</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>2</integer>
        <key>Hour</key><integer>10</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>$LOG_DIR/open_tue_1000_out.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/open_tue_1000_err.log</string>
</dict>
</plist>
PLIST
)"
echo "✅ 화요일 10:00 해피니스, 르오네뜨"

# ═══════════════════════════════════════════
# 기존 전원관리 스케줄 제거
# ═══════════════════════════════════════════
for OLD_LABEL in "com.kakao.golf.safe-sleep" "com.kakao.golf.safe-shutdown" "com.kakao.golf.scraper"; do
    sudo launchctl bootout system/"$OLD_LABEL" 2>/dev/null || true
    sudo rm -f "/Library/LaunchDaemons/$OLD_LABEL.plist" 2>/dev/null || true
done
# pmset 반복 이벤트 제거
sudo pmset repeat cancel 2>/dev/null || true
echo ""
echo "✅ 기존 전원관리/절전 스케줄 제거 완료"

# ═══════════════════════════════════════════
echo ""
echo "================================================"
echo "🎯 설치 완료! 스케줄 요약:"
echo ""
echo "  [04:00]   보존 정책 (오래된 시간별 데이터 정리)"
echo "  [2시간]   전체 8개 골프장 수집 + 분석 + 배포"
echo "  [05:00]   전체 수집 + 분석 + 대시보드 배포"
echo ""
echo "  [티오픈 시간 수집]"
echo "  매일 09:00  광주CC, 골드레이크"
echo "  월   08:30  어등산"
echo "  월   10:00  베르힐, 무등산"
echo "  화   09:00  푸른솔장성"
echo "  화   10:00  해피니스, 르오네뜨"
echo ""
echo "  테스트: sudo launchctl kickstart -k system/$LABEL_HOURLY"
echo "================================================"
