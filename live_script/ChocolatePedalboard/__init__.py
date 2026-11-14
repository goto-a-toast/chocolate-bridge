"""ChocolatePedalboard: Ableton Live remote script for chocolate-bridge.

Select it in Live > Settings > Link, Tempo & MIDI as a Control Surface with
input "Chocolate to Live".  It
  * finds the rack named "Pedalboard" on any track,
  * switches that rack's Chain Selector when the bridge sends CC 102
    (group n -> chain n, zones distributed equally),
  * reads the active chain and each device's on/off state about ten times a
    second and sends it as JSON over UDP to the bridge, which shows it on the
    pedalboard page (http://localhost:8765/).
Notes from the footswitches are not touched here; map them to the devices'
on/off buttons with Live's MIDI Map Mode as usual.
"""
import json
import os
import socket
import sys
import time

# Diagnostic: proves Live imported this package (Live writes no log line for that).
try:
    with open(os.path.expanduser("~/Library/Application Support/chocolate-bridge/live_script.txt"), "a") as _f:  # MARKER
        _f.write("%s imported by Python %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), sys.version.split()[0]))
except Exception:
    pass

import Live
from _Framework.ControlSurface import ControlSurface
from _Framework.EncoderElement import EncoderElement
from _Framework.InputControlElement import MIDI_CC_TYPE

from .pedalboard_state import (build_state, describe_params, find_looper, find_rack,
                               group_from_cc, selector_value_for)

MARKER = os.path.expanduser("~/Library/Application Support/chocolate-bridge/live_script.txt")

CHANNEL = 0               # MIDI channel 1, as the pedal sends
GROUP_CC = 102            # must match bridge.py
LOOPER_GROUP = 8          # this group operates the Looper and leaves the chain alone
STATE_ADDR = ("127.0.0.1", 9020)
HEARTBEAT_TICKS = 10      # update_display runs ~every 100 ms -> resend each ~1 s


def create_instance(c_instance):
    return ChocolatePedalboard(c_instance)


class ChocolatePedalboard(ControlSurface):
    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        with self.component_guard():
            self._group_cc = EncoderElement(MIDI_CC_TYPE, CHANNEL, GROUP_CC,
                                            Live.MidiMap.MapMode.absolute)
            self._group_cc.add_value_listener(self._on_group)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._last = None
        self._ticks = 0
        self._looper_described = False
        self.log_message("ChocolatePedalboard ready")

    def _on_group(self, value):
        group = group_from_cc(value)
        if group == LOOPER_GROUP - 1:
            # The looper group only operates the Looper; keep the current preset sounding.
            self.show_message("Pedalboard: looper controls (group %d)" % LOOPER_GROUP)
            return
        _track, rack = find_rack(self.song().tracks)
        if rack is None or not rack.chains:
            self.show_message("Pedalboard: no rack named 'Pedalboard'")
            return
        index = min(group, len(rack.chains) - 1)
        for p in rack.parameters:
            if p.name == "Chain Selector":
                p.value = selector_value_for(rack, index)
                break
        self.show_message("Pedalboard: %d %s" % (index + 1, rack.chains[index].name))

    def _describe_looper_once(self):
        """Write the Looper's real parameter names and display texts to the marker file."""
        if self._looper_described:
            return
        track, rack = find_rack(self.song().tracks)
        if rack is None:
            return
        looper, where = find_looper(track, rack, self.song().tracks)
        if looper is None:
            return
        self._looper_described = True
        try:
            text = describe_params(looper)
        except Exception as e:
            text = "  (could not read: %r)" % (e,)
        try:
            with open(MARKER, "a") as f:
                f.write("Looper (%s) parameters:\n%s\n" % (where, text))
        except Exception:
            pass

    def update_display(self):
        ControlSurface.update_display(self)
        self._ticks += 1
        try:
            self._describe_looper_once()
        except Exception:
            pass
        try:
            state = json.dumps(build_state(self.song().tracks), ensure_ascii=False)
        except Exception as e:  # a device deleted mid-read, etc.; try again next tick
            self.log_message("ChocolatePedalboard: %r" % (e,))
            return
        if state != self._last or self._ticks % HEARTBEAT_TICKS == 0:
            self._last = state
            try:
                self._sock.sendto(state.encode("utf-8"), STATE_ADDR)
            except socket.error:
                pass  # bridge not running; the page shows "not connected"

    def disconnect(self):
        self._group_cc.remove_value_listener(self._on_group)
        self._sock.close()
        ControlSurface.disconnect(self)
