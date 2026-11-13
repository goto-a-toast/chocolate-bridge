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
import socket

import Live
from _Framework.ControlSurface import ControlSurface
from _Framework.EncoderElement import EncoderElement
from _Framework.InputControlElement import MIDI_CC_TYPE

from .pedalboard_state import build_state, find_rack, group_from_cc, selector_value_for

CHANNEL = 0               # MIDI channel 1, as the pedal sends
GROUP_CC = 102            # must match bridge.py
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
        self.log_message("ChocolatePedalboard ready")

    def _on_group(self, value):
        _track, rack = find_rack(self.song().tracks)
        if rack is None or not rack.chains:
            self.show_message("Pedalboard: no rack named 'Pedalboard'")
            return
        index = min(group_from_cc(value), len(rack.chains) - 1)
        for p in rack.parameters:
            if p.name == "Chain Selector":
                p.value = selector_value_for(rack, index)
                break
        self.show_message("Pedalboard: %d %s" % (index + 1, rack.chains[index].name))

    def update_display(self):
        ControlSurface.update_display(self)
        self._ticks += 1
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
