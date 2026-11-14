"""Pure helpers for the ChocolatePedalboard remote script.

Kept free of Live imports so they can be tested outside Ableton: every
argument is duck-typed (anything with .name, .chains, .devices, .parameters,
.value, .min, .max works).
"""
import re

RACK_NAME = "Pedalboard"
GROUPS = 8          # must match bridge.py
_LABEL = re.compile(r"^\s*([A-Da-d])\s*[:：\-_\s]\s*(.+)$")


def find_rack(tracks, name=RACK_NAME):
    """Return (track, rack) for the first top-level rack called `name`, else (None, None)."""
    for track in tracks:
        for device in track.devices:
            if getattr(device, "can_have_chains", False) and device.name.strip().lower() == name.lower():
                return track, device
    return None, None


def chain_selector(rack):
    for p in rack.parameters:
        if p.name == "Chain Selector":
            return p
    return None


def active_chain(rack):
    """Index of the chain the selector points at, assuming equally distributed zones."""
    n = len(rack.chains)
    sel = chain_selector(rack)
    if n == 0 or sel is None:
        return 0 if n else None
    span = float(sel.max - sel.min + 1)
    return max(0, min(n - 1, int((sel.value - sel.min) * n / span)))


def selector_value_for(rack, index):
    """Selector value at the middle of chain `index`'s equal zone."""
    sel = chain_selector(rack)
    n = len(rack.chains)
    span = float(sel.max - sel.min + 1)
    return sel.min + min(sel.max - sel.min, int((index + 0.5) * span / n))


def group_from_cc(value):
    """bridge.py sends group_index * 128 / GROUPS."""
    return int(round(value * GROUPS / 128.0))


def split_label(name):
    """'A: Drive' -> ('A', 'Drive'); 'Drive' -> (None, 'Drive')."""
    m = _LABEL.match(name)
    return (m.group(1).upper(), m.group(2).strip()) if m else (None, name)


def device_on(device):
    for p in device.parameters:
        if p.name == "Device On":
            return p.value > 0
    return bool(device.parameters[0].value) if device.parameters else True


def is_looper(device):
    return getattr(device, "class_name", "") == "Looper"


def find_looper(track, rack, tracks):
    """(looper, where): after the rack on its track is the intended spot ('track');
    inside a chain ('chain') or on another track ('other') still works but is flagged."""
    for d in track.devices:
        if is_looper(d):
            return d, "track"
    for c in rack.chains:
        for d in c.devices:
            if is_looper(d):
                return d, "chain"
    for t in tracks:
        for d in t.devices:
            if is_looper(d):
                return d, "other"
    return None, None


def param_text(p):
    """The value as Live displays it ('Play', '-12.0 st', ...)."""
    try:
        return p.str_for_value(p.value)
    except Exception:
        return str(p.value)


def params_by_name(device):
    return dict((p.name, p) for p in device.parameters)


_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def normalize_state(text):
    t = text.lower()
    for key, word in (("overdub", "overdub"), ("rec", "record"), ("play", "play"), ("stop", "stop")):
        if key in t:
            return word
    return "unknown"


def speed_factor(text, p):
    """Playback rate from the Speed parameter: semitones ('st', or a range below 0)
    become 2**(st/12); a percentage or a plain ratio is used as is."""
    m = _NUMBER.search(text)
    if not m:
        return 1.0
    n = float(m.group())
    if "st" in text.lower() or p.min < 0:
        return 2 ** (n / 12.0)
    if "%" in text:
        return n / 100.0
    return n if n > 0 else 1.0


def looper_state(device, where):
    ps = params_by_name(device)
    state = ps.get("State")
    reverse = ps.get("Reverse")
    speed = ps.get("Speed")
    speed_text = param_text(speed) if speed is not None else None
    return {
        "where": where,
        "on": device_on(device),
        "state": normalize_state(param_text(state)) if state is not None else "unknown",
        "reverse": bool(reverse is not None and reverse.value > 0),
        "speed": speed_text,
        "factor": speed_factor(speed_text, speed) if speed is not None else 1.0,
    }


def describe_params(device):
    """One line per parameter, for checking names against a real Looper."""
    lines = []
    for p in device.parameters:
        items = list(getattr(p, "value_items", []) or [])
        lines.append("  %s = %r [%s..%s]%s" % (p.name, param_text(p), p.min, p.max,
                                                (" items=%s" % items) if items else ""))
    return "\n".join(lines)


def build_state(tracks):
    track, rack = find_rack(tracks)
    if rack is None:
        return {"rack": None}
    idx = active_chain(rack)
    chains = [c.name for c in rack.chains]
    pedals = []
    if idx is not None:
        for d in rack.chains[idx].devices:
            if is_looper(d):
                continue                         # shown in its own panel
            label, name = split_label(d.name)
            pedals.append({"name": name, "switch": label, "on": device_on(d)})
    looper, where = find_looper(track, rack, tracks)
    return {"rack": rack.name, "track": track.name, "chains": chains,
            "active": idx, "pedals": pedals,
            "looper": looper_state(looper, where) if looper is not None else None}
