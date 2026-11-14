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

Looper switch: switch D sends LOOPER_NOTE in every group instead of its own
note, so one MIDI mapping (Looper's main button) works whatever the preset.
Group 8 is the looper group: map its A/B/C (notes 64/65/66) to the Looper's
Stop / Reverse / Clear.

Port selection: every port matching DEVICE_MATCHES is opened at once.  When
the pedal is paired over Bluetooth it may send only there even though the USB
port ("SINCO") still exists, so listening to a single "preferred" port can
miss every press.  If the pedal does send the same message on both links, the
copy arriving within DEDUP_WINDOW is dropped, so nothing double-triggers.
"""
import json, os, socket, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
LOOPER_SWITCH = 3       # switch D (0 = A) ...
LOOPER_NOTE = 100       # ... sends this note in every group (E6 in Live's naming)
STATE_PORT = 9020       # UDP, JSON state from the ChocolatePedalboard Live script
PAGE_PORT = 8765        # http://localhost:8765/ = the pedalboard page
LIVE_TIMEOUT = 3.0      # seconds without state -> page shows "Live not connected"
PAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pedalboard.html")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def is_pedal(name):
    """True if the port name looks like the pedal (and is not our own output)."""
    low = name.lower()
    if OUT_NAME.lower() in low:                # never listen to our own output
        return False
    return any(key.lower() in low for key in DEVICE_MATCHES)


def make_handler(out, board=None):
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
            if board is not None:
                board.set_group(g)

    def on_midi(event, port):
        msg, _dt = event
        if not msg or is_duplicate(msg, port):
            return
        status = msg[0] & 0xF0
        ch = msg[0] & 0x0F
        if status == 0xC0 and len(msg) >= 2:
            pc = msg[1]
            note = LOOPER_NOTE if pc % 4 == LOOPER_SWITCH else NOTE_BASE + pc
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


class LoopClock:
    """Estimates the Looper's length and play position from its state changes.

    Live does not expose either, so: length = time from Record to the first
    Play/Overdub (scaled to speed 1); position advances at speed * direction
    while playing or overdubbing; Stop rewinds to the start.  State arrives at
    least once a second, so the estimate is piecewise exact between changes.
    """
    def __init__(self):
        self.length, self.phase, self.rec_start = None, 0.0, None
        self.prev, self.rate, self.t = None, 1.0, time.monotonic()

    def _advanced(self, now):
        if self.prev in ("play", "overdub") and self.length:
            return (self.phase + (now - self.t) * self.rate / self.length) % 1.0
        return self.phase

    def update(self, looper, now=None):
        now = time.monotonic() if now is None else now
        state = looper.get("state")
        rate = looper.get("factor", 1.0) * (-1.0 if looper.get("reverse") else 1.0)
        self.phase, self.t = self._advanced(now), now
        if state == "record" and self.prev != "record":
            self.rec_start, self.length, self.phase = now, None, 0.0
        elif self.prev == "record" and state in ("play", "overdub") and self.rec_start is not None:
            self.length, self.phase = (now - self.rec_start) * abs(self.rate), 0.0
        elif state == "stop":
            self.phase = 0.0
        self.prev, self.rate = state, rate

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        playing = self.prev in ("play", "overdub") and bool(self.length)
        recording = now - self.rec_start if self.prev == "record" and self.rec_start is not None else None
        return {"length": self.length, "phase": self._advanced(now),
                "rate": self.rate if playing else 0.0, "recording": recording}


class Board:
    """Latest pedalboard state from Live (+ the bridge's own group count),
    shared between the MIDI, UDP and HTTP threads."""
    def __init__(self):
        self.cond = threading.Condition()
        self.state, self.stamp, self.version = None, 0.0, 0
        self.group, self.clock = 0, LoopClock()

    def update(self, state):
        with self.cond:
            if state.get("looper"):
                self.clock.update(state["looper"])
            if state != self.state:
                self.state, self.version = state, self.version + 1
            self.stamp = time.monotonic()
            self.cond.notify_all()

    def set_group(self, g):
        with self.cond:
            self.group, self.version = g, self.version + 1
            self.cond.notify_all()

    def snapshot(self):
        live = self.state is not None and time.monotonic() - self.stamp < LIVE_TIMEOUT
        snap = dict(self.state or {}, live=live, group=self.group + 1)
        if snap.get("looper"):
            snap["looper"] = dict(snap["looper"], clock=self.clock.snapshot())
        return snap


def serve_state(board, port=STATE_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", port))
    while True:
        data, _ = sock.recvfrom(65536)
        try:
            board.update(json.loads(data.decode("utf-8")))
        except ValueError:
            pass


def make_page_handler(board):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):          # keep bridge.log for MIDI
            pass

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                with open(PAGE_FILE, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                seen = -1
                try:
                    while True:  # on every change, and once a second so "live" can time out
                        with board.cond:
                            board.cond.wait_for(lambda: board.version != seen, timeout=1.0)
                            seen, snap = board.version, board.snapshot()
                        self.wfile.write(b"data: " + json.dumps(snap, ensure_ascii=False).encode("utf-8") + b"\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_error(404)
    return Handler


def start_display(board):
    """Pedalboard page + state receiver.  Failure here must not stop the MIDI bridge."""
    try:
        threading.Thread(target=serve_state, args=(board,), daemon=True).start()
        httpd = ThreadingHTTPServer(("127.0.0.1", PAGE_PORT), make_page_handler(board))
        httpd.daemon_threads = True
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        log(f"pedalboard page: http://localhost:{PAGE_PORT}/")
    except OSError as e:
        log(f"pedalboard page disabled: {e}")


def main():
    board = Board()
    start_display(board)
    out = rtmidi.MidiOut()
    out.open_virtual_port(OUT_NAME)
    log(f"virtual port '{OUT_NAME}' created")
    handler = make_handler(out, board)

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
