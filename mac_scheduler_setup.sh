#!/bin/bash
# 카카오골프 수집봇 - Mac 자동 실행 스케줄러 설치

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python"
RUN_AS_USER="$(id -un)"
RUN_AS_GROUP="$(id -gn)"
PLIST_LABEL="com.kakao.golf.scraper"
PLIST_PATH="/Library/LaunchDaemons/$PLIST_LABEL.plist"
LEGACY_AGENT_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
WEEKLY_LABEL="com.kakao.golf.report.weekly"
WEEKLY_PLIST="/Library/LaunchDaemons/$WEEKLY_LABEL.plist"
LEGACY_WEEKLY_PLIST="$HOME/Library/LaunchAgents/$WEEKLY_LABEL.plist"
MONTHLY_LABEL="com.kakao.golf.report.monthly"
MONTHLY_PLIST="/Library/LaunchDaemons/$MONTHLY_LABEL.plist"
LEGACY_MONTHLY_PLIST="$HOME/Library/LaunchAgents/$MONTHLY_LABEL.plist"
YEARLY_LABEL="com.kakao.golf.report.yearly"
YEARLY_PLIST="/Library/LaunchDaemons/$YEARLY_LABEL.plist"
LEGACY_YEARLY_PLIST="$HOME/Library/LaunchAgents/$YEARLY_LABEL.plist"
LOG_DIR="$SCRIPT_DIR/logs"
ENV_PATH="$SCRIPT_DIR/.env"

get_env_bool() {
    local key="$1"
    local default_value="$2"
    if [ ! -f "$ENV_PATH" ]; then
        echo "$default_value"
        return
    fi
    local line
    line=$(grep -E "^${key}=" "$ENV_PATH" 2>/dev/null | tail -n 1 || true)
    if [ -z "$line" ]; then
        echo "$default_value"
        return
    fi
    local value="${line#*=}"
    value=$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')
    if [ "$value" = "true" ]; then
        echo "true"
    else
        echo "false"
    fi
}

REPORTS_ENABLED="$(get_env_bool REPORTS_ENABLED true)"

echo "🏌️ 카카오골프 수집/보고서 전체 스케줄 설치"
echo "================================================"
echo "폴더: $SCRIPT_DIR"
if [ "$REPORTS_ENABLED" != "true" ]; then
    echo "보고서 기능: 비활성화"
fi

# venv 확인
if [ ! -f "$PYTHON" ]; then
    echo "❌ venv가 없습니다. 먼저 ./setup.sh 를 실행하세요."
    exit 1
fi

# 필요한 폴더 생성
mkdir -p "$LOG_DIR"
mkdir -p "$HOME/Library/LaunchAgents"
sudo mkdir -p "/Library/LaunchDaemons"

# ────────────────────────────────────────
# 1단계: 수집봇 실행 시간 설정
# ────────────────────────────────────────
echo ""
echo "[ 1단계 ] 수집봇 실행 시간 설정"
echo "  매일 몇 시에 수집할까요? (숫자만 입력, 기본값: 7)"
printf "  입력 > "
read HOUR_INPUT
HOUR=$(echo "$HOUR_INPUT" | tr -dc '0-9' | head -c 2)
if [ -z "$HOUR" ] || [ "$HOUR" -lt 0 ] || [ "$HOUR" -gt 23 ] 2>/dev/null; then
    HOUR=7
fi

WAKE_HOUR=$(( HOUR == 0 ? 23 : HOUR - 1 ))
WAKE_MIN=50
WEEKLY_HOUR=$HOUR
WEEKLY_MIN=55
REPORT_HOUR_PLUS_ONE=$(( (HOUR + 1) % 24 ))
MONTHLY_HOUR=$REPORT_HOUR_PLUS_ONE
MONTHLY_MIN=5
YEARLY_HOUR=$REPORT_HOUR_PLUS_ONE
YEARLY_MIN=15
SLEEP_HOUR=$(( (HOUR + 1) % 24 ))
SLEEP_MIN=10

# plist 파일 생성
TMP_PLIST="$(mktemp)"
cat > "$TMP_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT_DIR}/run.py</string>
    </array>
    <key>UserName</key>
    <string>${RUN_AS_USER}</string>
    <key>GroupName</key>
    <string>${RUN_AS_GROUP}</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${HOUR}</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/scheduler_out.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/scheduler_err.log</string>
</dict>
</plist>
PLIST

sudo install -o root -g wheel -m 644 "$TMP_PLIST" "$PLIST_PATH"
rm -f "$TMP_PLIST"

launchctl unload "$LEGACY_AGENT_PATH" 2>/dev/null || true
sudo launchctl bootout system/$PLIST_LABEL 2>/dev/null || true
sudo launchctl bootstrap system "$PLIST_PATH"
sudo launchctl enable system/$PLIST_LABEL
echo "  ✅ 수집봇 스케줄 등록 완료 (LaunchDaemon, 매일 ${HOUR}:00)"

if [ "$REPORTS_ENABLED" = "true" ]; then
    # ────────────────────────────────────────
    # 1-1단계: 보고서 자동 생성 스케줄 등록
    # ────────────────────────────────────────
    TMP_WEEKLY_PLIST="$(mktemp)"
    cat > "$TMP_WEEKLY_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${WEEKLY_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT_DIR}/run.py</string>
        <string>--mode</string>
        <string>report</string>
        <string>--report-type</string>
        <string>weekly</string>
    </array>
    <key>UserName</key>
    <string>${RUN_AS_USER}</string>
    <key>GroupName</key>
    <string>${RUN_AS_GROUP}</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>2</integer>
        <key>Hour</key>
        <integer>${WEEKLY_HOUR}</integer>
        <key>Minute</key>
        <integer>${WEEKLY_MIN}</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/weekly_report_out.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/weekly_report_err.log</string>
</dict>
</plist>
PLIST
    sudo install -o root -g wheel -m 644 "$TMP_WEEKLY_PLIST" "$WEEKLY_PLIST"
    rm -f "$TMP_WEEKLY_PLIST"

    TMP_MONTHLY_PLIST="$(mktemp)"
    cat > "$TMP_MONTHLY_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${MONTHLY_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT_DIR}/run.py</string>
        <string>--mode</string>
        <string>report</string>
        <string>--report-type</string>
        <string>monthly</string>
    </array>
    <key>UserName</key>
    <string>${RUN_AS_USER}</string>
    <key>GroupName</key>
    <string>${RUN_AS_GROUP}</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>${MONTHLY_HOUR}</integer>
        <key>Minute</key>
        <integer>${MONTHLY_MIN}</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/monthly_report_out.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/monthly_report_err.log</string>
</dict>
</plist>
PLIST
    sudo install -o root -g wheel -m 644 "$TMP_MONTHLY_PLIST" "$MONTHLY_PLIST"
    rm -f "$TMP_MONTHLY_PLIST"

    TMP_YEARLY_PLIST="$(mktemp)"
    cat > "$TMP_YEARLY_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${YEARLY_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT_DIR}/run.py</string>
        <string>--mode</string>
        <string>report</string>
        <string>--report-type</string>
        <string>yearly</string>
    </array>
    <key>UserName</key>
    <string>${RUN_AS_USER}</string>
    <key>GroupName</key>
    <string>${RUN_AS_GROUP}</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Month</key>
        <integer>1</integer>
        <key>Day</key>
        <integer>2</integer>
        <key>Hour</key>
        <integer>${YEARLY_HOUR}</integer>
        <key>Minute</key>
        <integer>${YEARLY_MIN}</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/yearly_report_out.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/yearly_report_err.log</string>
</dict>
</plist>
PLIST
    sudo install -o root -g wheel -m 644 "$TMP_YEARLY_PLIST" "$YEARLY_PLIST"
    rm -f "$TMP_YEARLY_PLIST"

    launchctl unload "$LEGACY_WEEKLY_PLIST" 2>/dev/null || true
    launchctl unload "$LEGACY_MONTHLY_PLIST" 2>/dev/null || true
    launchctl unload "$LEGACY_YEARLY_PLIST" 2>/dev/null || true
    sudo launchctl bootout system/$WEEKLY_LABEL 2>/dev/null || true
    sudo launchctl bootout system/$MONTHLY_LABEL 2>/dev/null || true
    sudo launchctl bootout system/$YEARLY_LABEL 2>/dev/null || true
    sudo launchctl bootstrap system "$WEEKLY_PLIST"
    sudo launchctl bootstrap system "$MONTHLY_PLIST"
    sudo launchctl bootstrap system "$YEARLY_PLIST"
    sudo launchctl enable system/$WEEKLY_LABEL
    sudo launchctl enable system/$MONTHLY_LABEL
    sudo launchctl enable system/$YEARLY_LABEL

    echo ""
    echo "[ 1-1단계 ] 보고서 스케줄 등록"
    printf "  주간 보고서: 매주 월요일 %02d:%02d\n" $WEEKLY_HOUR $WEEKLY_MIN
    printf "  월간 보고서: 매월 1일 %02d:%02d\n" $MONTHLY_HOUR $MONTHLY_MIN
    printf "  연간 보고서: 매년 1월 2일 %02d:%02d\n" $YEARLY_HOUR $YEARLY_MIN
    echo "  ✅ 보고서 스케줄 등록 완료"
else
    launchctl unload "$LEGACY_WEEKLY_PLIST" 2>/dev/null || true
    launchctl unload "$LEGACY_MONTHLY_PLIST" 2>/dev/null || true
    launchctl unload "$LEGACY_YEARLY_PLIST" 2>/dev/null || true
    sudo launchctl bootout system/$WEEKLY_LABEL 2>/dev/null || true
    sudo launchctl bootout system/$MONTHLY_LABEL 2>/dev/null || true
    sudo launchctl bootout system/$YEARLY_LABEL 2>/dev/null || true
    echo ""
    echo "[ 1-1단계 ] 보고서 스케줄 비활성화"
    echo "  REPORTS_ENABLED=false 이므로 주간/월간/연간 보고서 잡을 등록하지 않습니다."
fi

# ────────────────────────────────────────
# 2단계: 맥 기상/전원 켜기 (wakeorpoweron)
# ────────────────────────────────────────
echo ""
echo "[ 2단계 ] 맥 기상/전원 켜기 설정"
printf "  전원 이벤트: 매일 %02d:%02d (수집 10분 전)\n" $WAKE_HOUR $WAKE_MIN
echo "  참고: 완전 종료보다 절전 유지가 더 안정적입니다."
echo "  ⚠️  맥 로그인 비밀번호를 입력하세요:"

sudo pmset repeat \
    wakeorpoweron MTWRFSU $(printf '%02d:%02d:00' $WAKE_HOUR $WAKE_MIN)

echo "  ✅ 맥 기상/전원 켜기 설정 완료"

# ────────────────────────────────────────
# 3단계: 안전 절전 스크립트 (5분 전 경고 + 사용중이면 취소)
# ────────────────────────────────────────
SLEEP_LABEL="com.kakao.golf.safe-sleep"
SLEEP_PLIST="/Library/LaunchDaemons/$SLEEP_LABEL.plist"
LEGACY_SHUTDOWN_LABEL="com.kakao.golf.safe-shutdown"
LEGACY_SHUTDOWN_PLIST="/Library/LaunchDaemons/$LEGACY_SHUTDOWN_LABEL.plist"

echo ""
echo "[ 3단계 ] 안전 절전 스케줄 등록"
printf "  절전 시도: 매일 %02d:%02d (사용중이면 자동 취소)\n" $SLEEP_HOUR $SLEEP_MIN

TMP_SLEEP_PLIST="$(mktemp)"
cat > "$TMP_SLEEP_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${SLEEP_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/safe_sleep.sh</string>
    </array>
    <key>UserName</key>
    <string>root</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${SLEEP_HOUR}</integer>
        <key>Minute</key>
        <integer>${SLEEP_MIN}</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/sleep_daemon_out.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/sleep_daemon_err.log</string>
</dict>
</plist>
PLIST

sudo install -o root -g wheel -m 644 "$TMP_SLEEP_PLIST" "$SLEEP_PLIST"
rm -f "$TMP_SLEEP_PLIST"

sudo launchctl bootout system/$LEGACY_SHUTDOWN_LABEL 2>/dev/null || true
sudo rm -f "$LEGACY_SHUTDOWN_PLIST"
sudo launchctl bootout system/$SLEEP_LABEL 2>/dev/null || true
sudo launchctl bootstrap system "$SLEEP_PLIST"
sudo launchctl enable system/$SLEEP_LABEL
echo "  ✅ 안전 절전 스케줄 등록 완료"

# ────────────────────────────────────────
# 완료
# ────────────────────────────────────────
echo ""
echo "================================================"
echo "🎉 설정 완료!"
echo ""
printf "  %02d:%02d  맥 기상 또는 전원 켜기 (pmset wakeorpoweron)\n" $WAKE_HOUR $WAKE_MIN
printf "  %02d:00  수집봇 자동 실행 (로그인 없이 동작)\n" $HOUR
if [ "$REPORTS_ENABLED" = "true" ]; then
    printf "  %02d:%02d  주간 보고서 자동 생성 (월요일)\n" $WEEKLY_HOUR $WEEKLY_MIN
    printf "  %02d:%02d  월간 보고서 자동 생성 (매월 1일)\n" $MONTHLY_HOUR $MONTHLY_MIN
    printf "  %02d:%02d  연간 보고서 자동 생성 (매년 1월 2일)\n" $YEARLY_HOUR $YEARLY_MIN
else
    echo "  보고서 자동 생성 비활성화"
fi
printf "  %02d:%02d  안전 절전 시도 (사용중이면 취소, 5분전 경고)\n" $SLEEP_HOUR $SLEEP_MIN
echo ""
echo "  지금 바로 테스트: sudo launchctl kickstart -k system/$PLIST_LABEL"
echo "  절전 테스트:     sudo launchctl kickstart -k system/$SLEEP_LABEL"
if [ "$REPORTS_ENABLED" = "true" ]; then
    echo "  주간 보고서 테스트: sudo launchctl kickstart -k system/$WEEKLY_LABEL"
fi
echo "================================================"
