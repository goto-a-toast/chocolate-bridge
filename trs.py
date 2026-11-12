#!/usr/bin/env python3
"""Switch the Chocolate's TRS jack (USB connection required).

    ./venv/bin/python trs.py expression   # use an expression pedal
    ./venv/bin/python trs.py midi         # TRS MIDI (also stops noise from an empty jack)
"""
import sys
from choc import Choc

VALUES = {"expression": 0, "midi": 1}
if len(sys.argv) != 2 or sys.argv[1] not in VALUES:
    print(__doc__); sys.exit(1)
try:
    c = Choc()
except StopIteration:
    print("ペダルが USB で見つかりません。USB ケーブルで繋いでから実行してください。"); sys.exit(1)
if c.discover() is None:
    print("ペダルが応答しません。USB ケーブルを挿し直してください。"); sys.exit(1)
ok = c.write(0x0C, VALUES[sys.argv[1]])
print(f"TRS -> {sys.argv[1]}:", "OK" if ok else "応答なし（失敗）")
sys.exit(0 if ok else 1)
