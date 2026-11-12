#!/usr/bin/env python3
"""Chocolate -> Live bridge.

Reads the M-VAVE Chocolate (Program Change A mode) over USB or Bluetooth MIDI
and re-publishes its messages on a virtual MIDI port "Chocolate to Live":
  Program Change n  ->  Note On (NOTE_BASE + n, velocity 127) + Note Off
  everything else   ->  passed through unchanged
Ableton Live maps notes as toggles, so each footswitch press flips the mapped
button.  PC-A mode: group g (1..8), switch A..D  ->  PC (g-1)*4 + (0..3).

Port selection: the first match in DEVICE_MATCHES wins, so USB ("SINCO") is
preferred over Bluetooth ("FootCtrl" etc.).  If a better port appears while a
worse one is in use, the bridge switches over; only one port is ever open, so
a pedal connected by cable and Bluetooth at once does not double-trigger.
"""
import time, threading
import rtmidi

OUT_NAME = "Chocolate to Live"
# Priority order, case-insensitive substrings.  USB first, then Bluetooth names.
DEVICE_MATCHES = ["SINCO", "FootCtrl", "M-VAVE", "MVAVE", "Chocolate", "CUVAVE"]
NOTE_BASE = 36          # PC 0 -> note 36 (C1 in Live's naming)
NOTE_LEN = 0.03         # seconds between Note On and Note Off
POLL = 2.0              # seconds between port scans


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def rank(name):
    """Priority of a port name (lower is better), or None if not the pedal."""
    if OUT_NAME.lower() in name.lower():      # never listen to our own output
        return None
    for i, key in enumerate(DEVICE_MATCHES):
        if key.lower() in name.lower():
            return i
    return None


def best_port(names):
    """Return (index, name, rank) of the preferred pedal port, or (None, None, None)."""
    found = [(rank(n), i, n) for i, n in enumerate(names) if rank(n) is not None]
    if not found:
        return None, None, None
    r, i, n = min(found)
    return i, n, r


def make_handler(out):
    def on_midi(event, _):
        msg, _dt = event
        if not msg:
            return
        status = msg[0] & 0xF0
        ch = msg[0] & 0x0F
        if status == 0xC0 and len(msg) >= 2:
            pc = msg[1]
            note = NOTE_BASE + pc
            if note > 127:
                return
            out.send_message([0x90 | ch, note, 127])
            threading.Timer(NOTE_LEN, out.send_message, args=([0x80 | ch, note, 0],)).start()
            log(f"PC {pc} (group {pc // 4 + 1}, switch {'ABCD'[pc % 4]}) -> note {note}")
        elif status != 0xF0:      # pass through notes/CC etc., drop sysex/realtime
            out.send_message(msg)
            log("passthrough", " ".join(f"{b:02X}" for b in msg))
    return on_midi


def main():
    out = rtmidi.MidiOut()
    out.open_virtual_port(OUT_NAME)
    log(f"virtual port '{OUT_NAME}' created")
    handler = make_handler(out)

    midi_in, cur_name, cur_rank = None, None, None
    while True:
        names = rtmidi.MidiIn().get_ports()
        idx, name, r = best_port(names)

        lost = midi_in is not None and cur_name not in names
        better = midi_in is not None and r is not None and r < cur_rank
        if lost or better:
            log(("device disconnected: " if lost else "switching from ") + f"'{cur_name}'")
            midi_in.close_port()
            midi_in, cur_name, cur_rank = None, None, None

        if midi_in is None and idx is not None:
            midi_in = rtmidi.MidiIn()
            midi_in.ignore_types(sysex=True, timing=True, active_sense=True)
            midi_in.open_port(idx)
            midi_in.set_callback(handler)
            cur_name, cur_rank = name, r
            kind = "USB" if r == 0 else "Bluetooth"
            log(f"connected to '{name}' ({kind})")
        time.sleep(POLL)


if __name__ == "__main__":
    main()
