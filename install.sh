#!/bin/bash
# Chocolate -> Live bridge installer.  Usage:  bash install.sh
#
# macOS blocks background agents from reading ~/Desktop, ~/Documents and
# ~/Downloads, so the runtime (Python env, scripts, log) is installed to
# ~/Library/Application Support/chocolate-bridge and the LaunchAgent runs it
# from there.  Re-run this after `git pull` to update the installed copy.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
APP="${APP_DIR:-$HOME/Library/Application Support/chocolate-bridge}"
LABEL="com.chocolate-bridge"
PLIST_DIR="${PLIST_DIR:-$HOME/Library/LaunchAgents}"
PLIST="$PLIST_DIR/$LABEL.plist"

PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3,9))' 2>/dev/null; then
  echo "Python 3.9+ が見つかりません。ターミナルで  xcode-select --install  を実行してから再実行してください。"
  exit 1
fi

echo "[1/4] プログラムを配置: $APP"
mkdir -p "$APP"
cp "$SRC/bridge.py" "$SRC/choc.py" "$SRC/trs.py" "$SRC/pedalboard.html" "$APP/"
# Live remote script for the pedalboard page (Live 11+ reads User Library/Remote Scripts).
LIVE_SCRIPTS="${LIVE_SCRIPTS_DIR:-$HOME/Music/Ableton/User Library/Remote Scripts}"
mkdir -p "$LIVE_SCRIPTS"
rm -rf "$LIVE_SCRIPTS/ChocolatePedalboard"
cp -R "$SRC/live_script/ChocolatePedalboard" "$LIVE_SCRIPTS/"
echo "      Live 用スクリプト: $LIVE_SCRIPTS/ChocolatePedalboard"

echo "[2/4] Python 環境を作成 ($PY)"
rm -rf "$APP/venv"
"$PY" -m venv "$APP/venv"
"$APP/venv/bin/python" -m pip install --quiet --upgrade pip
"$APP/venv/bin/python" -m pip install --quiet python-rtmidi
# Convenience links so ./venv/bin/python and bridge.log work from this folder.
[ -d "$SRC/venv" ] && [ ! -L "$SRC/venv" ] && rm -rf "$SRC/venv"
ln -sfn "$APP/venv" "$SRC/venv"
touch "$APP/bridge.log"
[ -f "$SRC/bridge.log" ] && [ ! -L "$SRC/bridge.log" ] && mv "$SRC/bridge.log" "$SRC/bridge.log.old"
ln -sfn "$APP/bridge.log" "$SRC/bridge.log"

echo "[3/4] 自動起動の設定ファイルを作成: $PLIST"
mkdir -p "$PLIST_DIR"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$APP/venv/bin/python</string>
    <string>-u</string>
    <string>$APP/bridge.py</string>
  </array>
  <key>WorkingDirectory</key><string>$APP</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$APP/bridge.log</string>
  <key>StandardErrorPath</key><string>$APP/bridge.log</string>
</dict>
</plist>
PL
plutil -lint "$PLIST" >/dev/null

if [ "${NO_LOAD:-0}" = "1" ]; then echo "(NO_LOAD=1: 起動はスキップ)"; exit 0; fi
echo "[4/4] 起動"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 4
tail -2 "$APP/bridge.log" || true
echo "完了。Live の環境設定で入力「Chocolate to Live」の Remote を On にしてください。"
echo "ペダルボード画面: http://localhost:8765/ （README の「ペダルボード画面」を参照）"
