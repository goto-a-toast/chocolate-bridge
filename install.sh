#!/bin/bash
# Chocolate -> Live bridge installer.  Usage: unzip, then  bash install.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.chocolate-bridge"
PLIST_DIR="${PLIST_DIR:-$HOME/Library/LaunchAgents}"
PLIST="$PLIST_DIR/$LABEL.plist"

PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3,9))' 2>/dev/null; then
  echo "Python 3.9+ が見つかりません。ターミナルで  xcode-select --install  を実行してから再実行してください。"
  exit 1
fi

echo "[1/3] Python 環境を作成 ($PY)"
rm -rf "$DIR/venv"
"$PY" -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install --quiet --upgrade pip
"$DIR/venv/bin/pip" install --quiet python-rtmidi

echo "[2/3] 自動起動の設定ファイルを作成: $PLIST"
mkdir -p "$PLIST_DIR"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/venv/bin/python</string>
    <string>-u</string>
    <string>$DIR/bridge.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$DIR/bridge.log</string>
  <key>StandardErrorPath</key><string>$DIR/bridge.log</string>
</dict>
</plist>
PL
plutil -lint "$PLIST" >/dev/null

if [ "${NO_LOAD:-0}" = "1" ]; then echo "(NO_LOAD=1: 起動はスキップ)"; exit 0; fi
echo "[3/3] 起動"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 3
tail -3 "$DIR/bridge.log" || true
echo "完了。Live の環境設定で入力「Chocolate to Live」の Remote を On にしてください。"
