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


def build_state(tracks):
    track, rack = find_rack(tracks)
    if rack is None:
        return {"rack": None}
    idx = active_chain(rack)
    chains = [c.name for c in rack.chains]
    pedals = []
    if idx is not None:
        for d in rack.chains[idx].devices:
            label, name = split_label(d.name)
            pedals.append({"name": name, "switch": label, "on": device_on(d)})
    return {"rack": rack.name, "track": track.name, "chains": chains,
            "active": idx, "pedals": pedals}
