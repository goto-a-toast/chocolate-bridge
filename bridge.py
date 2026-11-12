#!/usr/bin/env python3
"""Chocolate -> Live bridge.

Reads the M-VAVE Chocolate (Program Change A mode) over USB or Bluetooth MIDI
and re-publishes its messages on a virtual MIDI port "Chocolate to Live":
  Program Change n  ->  Note On (NOTE_BASE + n, velocity 127) + Note Off
  everything else   ->  passed through unchanged
Ableton Live maps notes as toggles, so each footswitch press flips the mapped
button.  PC-A mode: group g (1..8), switch A..D  ->  PC (g-1)*4 + (0..3).

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
            out.send_message([0x90 | ch, note, 127])
            threading.Timer(NOTE_LEN, out.send_message, args=([0x80 | ch, note, 0],)).start()
            log(f"PC {pc} (group {pc // 4 + 1}, switch {'ABCD'[pc % 4]}) -> note {note}  [{port}]")
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
