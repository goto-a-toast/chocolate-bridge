#!/usr/bin/env python3
"""Chocolate -> Live bridge.

Reads the M-VAVE Chocolate (Program Change A mode) over USB or Bluetooth MIDI
and re-publishes its messages on a virtual MIDI port "Chocolate to Live":
  Program Change n  ->  Note On (NOTE_BASE + n, velocity 127) + Note Off
  group change      ->  CC GROUP_CC, value = group spread over 0..127
  everything else   ->  passed through unchanged
Ableton Live maps notes as toggles, so each footswitch press flips the mapped
button.  PC-A mode: group g (1..8), switch A..D  ->  PC (g-1)*4 + (0..3).

Group tracking: A+B / C+D send CC PREV_CC / NEXT_CC (always value 5) with no
group number, and the groups wrap (1 -> 8, 8 -> 1).  The bridge counts the
group itself and re-syncs from every Program Change, so it cannot drift.  The
group CC value is group_index * 128 / GROUPS (8 groups: 0, 16, 32, ...), which
lines up with "Distribute Ranges Equally" on a Rack's Chain Selector.  The raw
PREV/NEXT CCs are swallowed so Live cannot learn them by mistake.

Port selection: every port matching DEVICE_MATCHES is opened at once.  When
the pedal is paired over Bluetooth it may send only there even though the USB
port ("SINCO") still exists, so listening to a single "preferred" port can
miss every press.  If the pedal does send the same message on both links, the
copy arriving within DEDUP_WINDOW is dropped, so nothing double-triggers.
"""
import time, threading
import rtmidi

OUT_NAME = "Chocolate to Live"
# Priority order, case-insensitive substrings.  USB first, then Bluetooth names.
DEVICE_MATCHES = ["SINCO", "FootCtrl", "M-VAVE", "MVAVE", "Chocolate", "CUVAVE"]
NOTE_BASE = 36          # PC 0 -> note 36 (C1 in Live's naming)
NOTE_LEN = 0.03         # seconds between Note On and Note Off
POLL = 2.0              # seconds between port scans
DEDUP_WINDOW = 0.1      # seconds; identical messages from another link are dropped
GROUPS = 8              # groups in PC-A mode
PREV_CC, NEXT_CC = 2, 3 # what the pedal sends on A+B / C+D
GROUP_CC = 102          # CC the bridge sends to Live when the group changes


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def is_pedal(name):
    """True if the port name looks like the pedal (and is not our own output)."""
    low = name.lower()
    if OUT_NAME.lower() in low:                # never listen to our own output
        return False
    return any(key.lower() in low for key in DEVICE_MATCHES)


def make_handler(out):
    lock = threading.Lock()
    last = {}                                   # message bytes -> (time, port)

    def is_duplicate(msg, port):
        """Same message from a different port within DEDUP_WINDOW = one press on two links."""
        key, now = tuple(msg), time.monotonic()
        with lock:
            prev = last.get(key)
            last[key] = (now, port)
            return prev is not None and prev[1] != port and now - prev[0] < DEDUP_WINDOW

    group = [0]                                 # 0-based; the pedal powers up in group 1

    def set_group(g, ch, why):
        """Record the current group and tell Live when it changes."""
        if g != group[0]:
            group[0] = g
            value = g * 128 // GROUPS
            out.send_message([0xB0 | ch, GROUP_CC, value])
            log(f"group {g + 1} ({why}) -> CC {GROUP_CC} = {value}")

    def on_midi(event, port):
        msg, _dt = event
        if not msg or is_duplicate(msg, port):
            return
        status = msg[0] & 0xF0
        ch = msg[0] & 0x0F
        if status == 0xC0 and len(msg) >= 2:
            pc = msg[1]
            note = NOTE_BASE + pc
            if note > 127:
                return
            set_group(pc // 4 % GROUPS, ch, "switch")
            out.send_message([0x90 | ch, note, 127])
            threading.Timer(NOTE_LEN, out.send_message, args=([0x80 | ch, note, 0],)).start()
            log(f"PC {pc} (group {pc // 4 + 1}, switch {'ABCD'[pc % 4]}) -> note {note}  [{port}]")
        elif status == 0xB0 and len(msg) >= 3 and msg[1] in (PREV_CC, NEXT_CC):
            step = 1 if msg[1] == NEXT_CC else -1
            set_group((group[0] + step) % GROUPS, ch, "next" if step > 0 else "prev")
        elif status != 0xF0:      # pass through notes/CC etc., drop sysex/realtime
            out.send_message(msg)
            log("passthrough", " ".join(f"{b:02X}" for b in msg), f"[{port}]")
    return on_midi


def main():
    out = rtmidi.MidiOut()
    out.open_virtual_port(OUT_NAME)
    log(f"virtual port '{OUT_NAME}' created")
    handler = make_handler(out)

    opened = {}                                 # port name -> MidiIn
    while True:
        names = rtmidi.MidiIn().get_ports()

        for name in [n for n in opened if n not in names]:
            opened.pop(name).close_port()
            log(f"device disconnected: '{name}'")

        for idx, name in enumerate(names):
            if name in opened or not is_pedal(name):
                continue
            midi_in = rtmidi.MidiIn()
            midi_in.ignore_types(sysex=True, timing=True, active_sense=True)
            midi_in.open_port(idx)
            midi_in.set_callback(handler, name)
            opened[name] = midi_in
            log(f"connected to '{name}'")
        time.sleep(POLL)


if __name__ == "__main__":
    main()
