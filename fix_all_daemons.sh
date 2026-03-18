#!/bin/bash
# 카카오골프 데몬 전체 수정: root→forestdragon, Desktop→home 경로 수정
set -euo pipefail

USER="forestdragon"
GROUP="staff"
BASE="/Users/forestdragon/kakao_golf"
PYTHON="$BASE/venv/bin/python"
LOG_DIR="$BASE/logs"

echo "🔧 카카오골프 데몬 전체 수정"
echo "========================================="

# 기존 데몬 전부 내리기
echo "[1] 기존 데몬 내리기..."
for label in \
    com.kakao.golf.scraper \
    com.kakao.golf.daily \
    com.kakao.golf.hourly \
    com.kakao.golf.open.0900 \
    com.kakao.golf.open.mon.0830 \
    com.kakao.golf.open.mon.1000 \
    com.kakao.golf.open.tue.0900 \
    com.kakao.golf.open.tue.1000 \
    com.kakao.golf.retention \
    com.kakao.golf.report.weekly \
    com.kakao.golf.report.monthly \
    com.kakao.golf.report.yearly \
    com.kakao.golf.safe-sleep; do
    sudo launchctl bootout system/$label 2>/dev/null || true
done
echo "  ✅ 완료"

# 07:00 scraper 제거
echo "[2] 불필요한 scraper(07:00) 제거..."
sudo rm -f /Library/LaunchDaemons/com.kakao.golf.scraper.plist
echo "  ✅ 완료"

# daily (05:00)
echo "[3] daily 데몬 수정..."
cat > /tmp/com.kakao.golf.daily.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.daily</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>5</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/daily_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/daily_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.daily.plist /Library/LaunchDaemons/
echo "  ✅ daily (매일 05:00, ${USER})"

# hourly (2시간마다)
echo "[4] hourly 데몬 수정..."
cat > /tmp/com.kakao.golf.hourly.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.hourly</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>15</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>StandardOutPath</key><string>${LOG_DIR}/hourly_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/hourly_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.hourly.plist /Library/LaunchDaemons/
echo "  ✅ hourly (07/12/15/18/21시, ${USER})"

# open.0900 (매일 09:00, 광주CC+골드레이크)
echo "[5] open 시간대 데몬 수정..."
cat > /tmp/com.kakao.golf.open.0900.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.open.0900</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--courses</string>
        <string>광주CC</string>
        <string>골드레이크</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>9</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/open_0900_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/open_0900_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.open.0900.plist /Library/LaunchDaemons/

# open.mon.0830 (월 08:30, 어등산)
cat > /tmp/com.kakao.golf.open.mon.0830.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.open.mon.0830</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--courses</string>
        <string>어등산</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>8</integer>
        <key>Minute</key><integer>30</integer>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/open_mon_0830_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/open_mon_0830_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.open.mon.0830.plist /Library/LaunchDaemons/

# open.mon.1000 (월 10:00, 베르힐+무등산)
cat > /tmp/com.kakao.golf.open.mon.1000.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.open.mon.1000</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--courses</string>
        <string>베르힐</string>
        <string>무등산</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>10</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/open_mon_1000_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/open_mon_1000_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.open.mon.1000.plist /Library/LaunchDaemons/

# open.tue.0900 (화 09:00, 푸른솔장성)
cat > /tmp/com.kakao.golf.open.tue.0900.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.open.tue.0900</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--courses</string>
        <string>푸른솔장성</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>2</integer>
        <key>Hour</key><integer>9</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/open_tue_0900_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/open_tue_0900_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.open.tue.0900.plist /Library/LaunchDaemons/

# open.tue.1000 (화 10:00, 해피니스+르오네뜨)
cat > /tmp/com.kakao.golf.open.tue.1000.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.open.tue.1000</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--courses</string>
        <string>해피니스</string>
        <string>르오네뜨</string>
        <string>--skip-ai</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>2</integer>
        <key>Hour</key><integer>10</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/open_tue_1000_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/open_tue_1000_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.open.tue.1000.plist /Library/LaunchDaemons/
echo "  ✅ open 시간대 전부 수정 완료"

# retention (04:00)
echo "[6] retention 데몬 수정..."
cat > /tmp/com.kakao.golf.retention.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.retention</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/db/retention.py</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>4</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/retention_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/retention_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.retention.plist /Library/LaunchDaemons/
echo "  ✅ retention (매일 04:00, ${USER})"

# report (weekly/monthly/yearly) - Desktop→home 경로 수정
echo "[7] report 데몬 경로 수정..."
cat > /tmp/com.kakao.golf.report.weekly.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.report.weekly</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--mode</string>
        <string>report</string>
        <string>--report-type</string>
        <string>weekly</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>7</integer>
        <key>Minute</key><integer>30</integer>
    </dict>
    <key>RunAtLoad</key><false/>
    <key>StandardOutPath</key><string>${LOG_DIR}/weekly_report_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/weekly_report_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.report.weekly.plist /Library/LaunchDaemons/

cat > /tmp/com.kakao.golf.report.monthly.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.report.monthly</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--mode</string>
        <string>report</string>
        <string>--report-type</string>
        <string>monthly</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key><integer>1</integer>
        <key>Hour</key><integer>7</integer>
        <key>Minute</key><integer>30</integer>
    </dict>
    <key>RunAtLoad</key><false/>
    <key>StandardOutPath</key><string>${LOG_DIR}/monthly_report_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/monthly_report_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.report.monthly.plist /Library/LaunchDaemons/

cat > /tmp/com.kakao.golf.report.yearly.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.kakao.golf.report.yearly</string>
    <key>UserName</key><string>${USER}</string>
    <key>GroupName</key><string>${GROUP}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/${USER}</string>
        <key>PATH</key><string>${BASE}/venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BASE}/run.py</string>
        <string>--mode</string>
        <string>report</string>
        <string>--report-type</string>
        <string>yearly</string>
    </array>
    <key>WorkingDirectory</key><string>${BASE}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Month</key><integer>1</integer>
        <key>Day</key><integer>2</integer>
        <key>Hour</key><integer>7</integer>
        <key>Minute</key><integer>30</integer>
    </dict>
    <key>RunAtLoad</key><false/>
    <key>StandardOutPath</key><string>${LOG_DIR}/yearly_report_out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/yearly_report_err.log</string>
</dict>
</plist>
PLIST
sudo install -o root -g wheel -m 644 /tmp/com.kakao.golf.report.yearly.plist /Library/LaunchDaemons/
echo "  ✅ report (weekly/monthly/yearly 경로 수정)"

# 전부 다시 등록
echo "[8] 데몬 전부 등록..."
for plist in /Library/LaunchDaemons/com.kakao.golf.*.plist; do
    label=$(basename "$plist" .plist)
    sudo launchctl bootstrap system "$plist" 2>/dev/null || true
    sudo launchctl enable system/$label 2>/dev/null || true
done
echo "  ✅ 등록 완료"

# 임시 파일 정리
rm -f /tmp/com.kakao.golf.*.plist

echo ""
echo "========================================="
echo "🎉 전체 수정 완료! 등록된 데몬:"
echo ""
echo "  04:00  retention (DB 정리)"
echo "  05:00  daily (전체 수집+분석+배포)"
echo "  07/12/15/18/21시  hourly (수집만, AI 스킵)"
echo "  09:00  open (광주CC, 골드레이크)"
echo "  월08:30 open.mon (어등산)"
echo "  월10:00 open.mon (베르힐, 무등산)"
echo "  화09:00 open.tue (푸른솔장성)"
echo "  화10:00 open.tue (해피니스, 르오네뜨)"
echo "  월07:30 weekly report"
echo "  매월1일 monthly report"
echo "  매년1/2 yearly report"
echo ""
echo "  전부 forestdragon 유저로 실행됩니다."
echo "========================================="
