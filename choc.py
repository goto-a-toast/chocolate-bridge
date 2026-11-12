"""Minimal M-VAVE Chocolate (SINCO) SysEx helper: read config blob, write single bytes."""
import rtmidi, time, sys

ADV_START, ADV_BLOCK, PAGE_STRIDE = 93, 417, 4*417
TYPES = {0:"PC",1:"CC",2:"NoteOn",3:"NoteOff",4:"SysEx"}
MODES = {0:"Program Change A",1:"Program Change B",2:"Custom",3:"Advanced Custom",4:"Manufacturer",
         5:"Touch Screen",6:"Video",7:"Keyboard A",8:"Keyboard B",9:"Multimedia",10:"Custom Keyboard",11:"Mix Key",12:"Speaker"}

def enc14(v): return [v & 0x7F, (v >> 7) & 0x7F]
def addr4(a): return [a & 0x7F, (a>>7)&0x7F, (a>>14)&0x7F, 0]
def ck_const(addr):
    rel = addr - ADV_START
    if 0 <= rel < 8*ADV_BLOCK:
        return [0x28A,0x38B,0x18B,0x38B][(rel//ADV_BLOCK) % 4]
    if 23637 <= addr <= 23642: return 0x20B
    return 0x28A
def build_write(addr, value):
    d = [0x00,0x32,0x09,0x49, 0,0,0,2, *addr4(addr), 0x10,0,0,0, value & 0x7F]
    x = ck_const(addr) - sum(d) - d[8] - (value & 0x7F)
    return [0xF0, *d, *enc14(x), 0xF7]
def build_read(addr, rr, final=False):
    return [0xF0,0x00,0x32,0x0D,0x41, 0,0,0,2, *addr4(addr), *([0x70,0x36] if final else [0x10,0x7E]), 0,0, *enc14(rr), 0xF7]

class Choc:
    def __init__(self):
        self.mi, self.mo = rtmidi.MidiIn(), rtmidi.MidiOut()
        self.mi.ignore_types(sysex=False, timing=True, active_sense=True)
        ports = self.mi.get_ports(); idx = next(i for i,p in enumerate(ports) if "SINCO" in p)
        self.mi.open_port(idx); self.mo.open_port(idx)
        self.rx = []; self.mi.set_callback(lambda ev,_: self.rx.append(bytes(ev[0])))
    def send(self, m): self.mo.send_message(m)
    def wait(self, pred, timeout=2.0):
        t0 = time.time()
        while time.time()-t0 < timeout:
            for m in list(self.rx):
                if pred(m): self.rx.remove(m); return m
            time.sleep(0.01)
        return None
    def discover(self):
        self.send([0xF0,0x00,0x32,0x45,0,0,0,0x40,0x7F,0xF7])
        return self.wait(lambda m: m[1:5]==b"\x00\x32\x45\x58")
    def read_blob(self):
        blob = bytearray(); tail = None; rr = 7
        for i in range(24):
            final = (i == 23)
            m = None
            for attempt in range(3):
                self.send(build_read(i*1009, 66 if final else rr, final))
                m = self.wait(lambda m: m[1:4]==b"\x00\x32\x0D", 5.0)
                if m is not None: break
                print(f"  read {i}: no response (attempt {attempt+1})")
            if m is None: break
            time.sleep(0.1)
            payload = m[17:-3]
            if m[4] == 0x49: blob += payload
            elif m[4] == 0x79: tail = payload
            rr += 12 if i == 0 else 11
        return bytes(blob), tail
    def write(self, addr, value):
        self.send(build_write(addr, value))
        ack = self.wait(lambda m: m[1:5]==b"\x00\x32\x01\x08", 2.0)
        return ack is not None

def decode(blob, tail):
    out = {}
    out["mode"] = (blob[0], MODES.get(blob[0]))
    out["trs"] = blob[1]; out["midi_channel"] = blob[2]+1
    out["custom_cc"] = [(f"slot{b}", "latch" if blob[3+2*b] else "momentary", f"CC{blob[4+2*b]}") for b in range(5)]
    sysblk = tail[-9:] if tail else blob[23637:23646]
    out["bankMaxA+1"], out["bankMaxB+1"], out["groups+1"], out["usrpage"], out["hidpage"], out["polar"] = [int(x)+ (1 if i<3 else 0) for i,x in enumerate(sysblk[:6])]
    page = sysblk[3]
    sw = {}
    for s, name in enumerate("ABCD"):
        base = ADV_START + page*PAGE_STRIDE + s*ADV_BLOCK
        entry = {"step_mode": blob[base]}
        for bank, bn in ((0,"A"),(1,"B")):
            codes = []
            for slot in range(16):
                o = base+1+bank*80+slot*5
                en, ch, ty, d1, d2 = blob[o:o+5]
                if en: codes.append(f"ch{ch+1} {TYPES.get(ty,ty)} {d1} {d2}")
            entry[f"bank{bn}"] = codes
        sw[name] = entry
    out["adv_custom_page"] = page; out["switches"] = sw
    return out

if __name__ == "__main__":
    c = Choc()
    d = c.discover(); print("discovery:", d.hex(" ") if d else None)
    blob, tail = c.read_blob()
    print("blob:", len(blob), "tail:", len(tail) if tail else None)
    open("blob.bin","wb").write(blob)
    if tail: open("tail.bin","wb").write(tail)
    if len(blob) >= 23646:
        import pprint; pprint.pprint(decode(blob, tail), width=120, sort_dicts=False)
