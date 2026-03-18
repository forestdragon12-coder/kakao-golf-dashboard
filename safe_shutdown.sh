#!/bin/bash
# Legacy wrapper kept so existing LaunchDaemon entries continue to work
# until mac_scheduler_setup.sh is re-run.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec /bin/bash "$SCRIPT_DIR/safe_sleep.sh" "$@"
