#!/bin/bash
LABEL="com.chocolate-bridge"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "自動起動を解除しました（このフォルダは残っています）。"
