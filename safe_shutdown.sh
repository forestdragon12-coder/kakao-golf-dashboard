#!/bin/bash
# ──────────────────────────────────────────────
# 안전 종료 스크립트 v2
#
# 판단 기준 (3단계 복합 체크):
#   1. 화면 잠금 상태 → 잠겨있으면 미사용
#   2. 유저 앱 실행 여부 → Safari/Chrome/Word 등 열려있으면 사용 중
#   3. 2분 간격 2회 입력 샘플링 → 1회 터치는 무시, 지속 활동만 감지
#
# 결과:
#   - 사용 중 → 종료 취소
#   - 미사용 → 5분 전 경고 팝업 → 종료
# ──────────────────────────────────────────────

LOG_DIR="$(cd "$(dirname "$0")" && pwd)/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/shutdown.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') | $1" >> "$LOG"; }

CONSOLE_USER=$(stat -f '%Su' /dev/console 2>/dev/null || echo "")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 체크 1: 화면 잠금 상태
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCREEN_LOCKED=$(python3 -c "
import subprocess, sys
r = subprocess.run(['ioreg', '-n', 'Root', '-d1', '-w0'], capture_output=True, text=True)
if 'CGSSessionScreenIsLocked' in r.stdout:
    # 잠금 화면 키워드가 있으면 잠김
    print('locked')
else:
    # CGSession으로 추가 확인
    r2 = subprocess.run(['/usr/bin/python3', '-c', '''
import Quartz
session = Quartz.CGSessionCopyCurrentDictionary()
if session:
    locked = session.get(\"CGSSessionScreenIsLocked\", 0)
    print(\"locked\" if locked else \"unlocked\")
else:
    print(\"unknown\")
'''], capture_output=True, text=True)
    print(r2.stdout.strip() if r2.stdout.strip() else 'unlocked')
" 2>/dev/null)

# 잠금 상태 판별 실패시 대체: loginwindow가 foreground인지 확인
if [ "$SCREEN_LOCKED" != "locked" ] && [ "$SCREEN_LOCKED" != "unlocked" ]; then
    FRONT_APP=$(osascript -e 'tell application "System Events" to get name of first application process whose frontmost is true' 2>/dev/null)
    if [ "$FRONT_APP" = "loginwindow" ] || [ "$FRONT_APP" = "ScreenSaverEngine" ]; then
        SCREEN_LOCKED="locked"
    else
        SCREEN_LOCKED="unlocked"
    fi
fi

log "CHECK1: 화면=${SCREEN_LOCKED}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 체크 2: 유저 앱 실행 여부
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 실제 작업용 앱이 열려있으면 사용 중으로 판단
USER_APPS=$(osascript -e '
tell application "System Events"
    set appNames to name of every application process whose background only is false
    set output to ""
    repeat with a in appNames
        set output to output & a & ","
    end repeat
    return output
end tell
' 2>/dev/null)

# 작업용 앱 패턴 (Finder/Dock/SystemUI 등 시스템 앱은 제외)
WORK_APP_FOUND=false
WORK_APPS="Safari|Chrome|Firefox|Arc|Word|Excel|PowerPoint|Pages|Numbers|Keynote|Code|Terminal|iTerm|Xcode|Slack|KakaoTalk|카카오톡|Notion|Figma|Photoshop|Preview|Mail"

if echo "$USER_APPS" | grep -qiE "$WORK_APPS"; then
    WORK_APP_FOUND=true
fi

log "CHECK2: 작업앱=${WORK_APP_FOUND} (${USER_APPS})"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 체크 3: 2분 간격 2회 입력 샘플링
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
get_idle_sec() {
    local ns=$(ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print $NF; exit}')
    echo $((ns / 1000000000))
}

IDLE1=$(get_idle_sec)
log "CHECK3: 1차 유휴=${IDLE1}초, 2분 후 재측정..."
sleep 120
IDLE2=$(get_idle_sec)
log "CHECK3: 2차 유휴=${IDLE2}초"

# 2차 유휴가 120초 미만 = 2분 대기 중에 입력이 있었음 = 지속 사용 중
SUSTAINED_ACTIVITY=false
if [ "$IDLE2" -lt 120 ]; then
    SUSTAINED_ACTIVITY=true
fi

log "CHECK3: 지속활동=${SUSTAINED_ACTIVITY}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 종합 판단
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사용 중 판단: 아래 중 하나라도 해당하면 종료 취소
#   - 화면 잠금 해제 + 작업앱 실행 중
#   - 화면 잠금 해제 + 2분 내 지속 입력

ACTIVE=false
REASON=""

if [ "$SCREEN_LOCKED" = "unlocked" ] && [ "$WORK_APP_FOUND" = "true" ] && [ "$SUSTAINED_ACTIVITY" = "true" ]; then
    ACTIVE=true
    REASON="화면잠금해제 + 작업앱실행 + 지속입력"
elif [ "$SCREEN_LOCKED" = "unlocked" ] && [ "$SUSTAINED_ACTIVITY" = "true" ]; then
    ACTIVE=true
    REASON="화면잠금해제 + 지속입력"
elif [ "$SCREEN_LOCKED" = "unlocked" ] && [ "$WORK_APP_FOUND" = "true" ] && [ "$IDLE2" -lt 600 ]; then
    ACTIVE=true
    REASON="화면잠금해제 + 작업앱실행 + 10분내입력"
fi

if [ "$ACTIVE" = "true" ]; then
    log "SKIP: 사용 중 (${REASON}). 종료 취소."
    exit 0
fi

log "PROCEED: 미사용 판단 → 종료 프로세스 시작"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5분 전 경고 팝업
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if [ -n "$CONSOLE_USER" ] && [ "$CONSOLE_USER" != "root" ]; then
    sudo -u "$CONSOLE_USER" osascript -e '
        display dialog "⚠️ 5분 후 Mac이 자동으로 종료됩니다." & return & return & "작업 중이면 [취소]를 눌러주세요." buttons {"종료 진행", "취소"} default button "종료 진행" with title "⏰ 자동 종료 예고" with icon caution giving up after 290
    ' 2>/dev/null
    RESULT=$?

    if [ $RESULT -ne 0 ]; then
        log "CANCEL: 사용자가 종료를 취소함"
        exit 0
    fi
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5분 대기 + 최종 확인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log "WAITING: 5분 대기 중..."
sleep 300

IDLE_FINAL=$(get_idle_sec)
log "FINAL: 최종 유휴=${IDLE_FINAL}초"

if [ "$IDLE_FINAL" -lt 120 ]; then
    log "CANCEL: 대기 중 사용자 활동 감지. 종료 취소."
    if [ -n "$CONSOLE_USER" ] && [ "$CONSOLE_USER" != "root" ]; then
        sudo -u "$CONSOLE_USER" osascript -e '
            display notification "사용자 활동 감지로 자동 종료가 취소되었습니다." with title "자동 종료 취소" sound name "Glass"
        ' 2>/dev/null
    fi
    exit 0
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 종료 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log "SHUTDOWN: 종료 실행"
/sbin/shutdown -h now
