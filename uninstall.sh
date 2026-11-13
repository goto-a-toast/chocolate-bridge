#!/bin/bash
# Remove the LaunchAgent and the installed runtime (this folder is kept).
SRC="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.chocolate-bridge"
APP="${APP_DIR:-$HOME/Library/Application Support/chocolate-bridge}"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -rf "$APP"
rm -rf "${LIVE_SCRIPTS_DIR:-$(python3 "$SRC/live_script/find_user_library.py")/Remote Scripts}/ChocolatePedalboard"
[ -L "$SRC/venv" ] && rm -f "$SRC/venv"
[ -L "$SRC/bridge.log" ] && rm -f "$SRC/bridge.log"
echo "自動起動を解除し、インストールしたプログラムを削除しました（このフォルダは残っています）。"
