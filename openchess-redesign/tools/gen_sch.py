"""Generate the KiCad 7 schematic (single A1 sheet) from design.py."""
import math, os, sys, uuid, datetime
sys.path.insert(0, os.path.dirname(__file__))
from sexp import parse, dumps, find, find_all, Sym, S, sym
import design as D

PROJECT = "openchess-board"
ROOT_UUID = "5a7c0b0e-0000-4000-8000-000000000001"

def U(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "openchess/" + seed))

# ----------------------------------------------------------------------------
# library symbol loading / flattening
# ----------------------------------------------------------------------------
_libcache = {}

def load_lib(lib):
    if lib not in _libcache:
        path = os.path.join(D.SYM_LIB, lib + ".kicad_sym")
        _libcache[lib] = parse(open(path, encoding="utf-8").read())[0]
    return _libcache[lib]

def get_symbol(lib, name):
    root = load_lib(lib)
    for c in root:
        if isinstance(c, list) and c and c[0] == "symbol" and c[1] == name:
            return c
    raise KeyError(f"{lib}:{name}")

def flatten(lib, name):
    """Return a lib_symbols entry named 'lib:name' with (extends) resolved."""
    s = get_symbol(lib, name)
    ext = find(s, "extends")
    if ext:
        parent = flatten(lib, ext[1])
        # copy parent, override properties with child's
        import copy
        out = copy.deepcopy(parent)
        pname = ext[1]
        out[1] = f"{lib}:{name}"
        for c in out:
            if isinstance(c, list) and c and c[0] == "symbol":
                c[1] = c[1].replace(pname + "_", name + "_", 1)
        child_props = {p[1]: p for p in find_all(s, "property")}
        for i, c in enumerate(out):
            if isinstance(c, list) and c and c[0] == "property" and c[1] in child_props:
                out[i] = child_props[c[1]]
        return out
    import copy
    out = copy.deepcopy(s)
    out[1] = f"{lib}:{name}"
    return out

def hall_symbol():
    pn = D.SENSOR["pins"]
    def pin(kind, x, y, a, name, num):
        return S(sym("pin"), sym(kind), sym("line"), S(sym("at"), x, y, a), S(sym("length"), 2.54),
                 S(sym("name"), name, S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)))),
                 S(sym("number"), num, S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)))))
    fx = S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)))
    fxh = S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), sym("hide"))
    return S(sym("symbol"), "OpenChess:HALL_SWITCH_SOT23", S(sym("pin_names"), S(sym("offset"), 1.016)),
             S(sym("in_bom"), sym("yes")), S(sym("on_board"), sym("yes")),
             S(sym("property"), "Reference", "H", S(sym("at"), 0, 8.89, 0), fx),
             S(sym("property"), "Value", D.SENSOR["value"], S(sym("at"), 0, -8.89, 0), fx),
             S(sym("property"), "Footprint", "Package_TO_SOT_SMD:SOT-23", S(sym("at"), 0, 0, 0), fxh),
             S(sym("property"), "Datasheet", "", S(sym("at"), 0, 0, 0), fxh),
             S(sym("property"), "ki_description", "Unipolar Hall-effect switch, open-collector, SOT-23", S(sym("at"), 0, 0, 0), fxh),
             S(sym("symbol"), "HALL_SWITCH_SOT23_0_1",
               S(sym("rectangle"), S(sym("start"), -5.08, 5.08), S(sym("end"), 5.08, -5.08),
                 S(sym("stroke"), S(sym("width"), 0.254), S(sym("type"), sym("default"))),
                 S(sym("fill"), S(sym("type"), sym("background")))),
               S(sym("circle"), S(sym("center"), 0, 0), S(sym("radius"), 2.0),
                 S(sym("stroke"), S(sym("width"), 0.254), S(sym("type"), sym("default"))),
                 S(sym("fill"), S(sym("type"), sym("none"))))),
             S(sym("symbol"), "HALL_SWITCH_SOT23_1_1",
               pin("power_in", 0, 7.62, 270, "VCC", pn["VCC"]),
               pin("open_collector", 7.62, 0, 180, "OUT", pn["OUT"]),
               pin("power_in", 0, -7.62, 90, "GND", pn["GND"])))

def symbol_pins(symdef):
    """-> {number: (x, y, angle, name)} from all sub-units."""
    pins = {}
    for sub in find_all(symdef, "symbol"):
        for p in find_all(sub, "pin"):
            at = find(p, "at")
            num = find(p, "number")[1]
            name = find(p, "name")[1]
            pins[num] = (float(at[1]), float(at[2]), float(at[3]), name)
    return pins

# ----------------------------------------------------------------------------
# schematic construction
# ----------------------------------------------------------------------------
class Sch:
    def __init__(self):
        self.items = []
        self.libsyms = {}
        self.pwr_n = 0

    def ensure_lib(self, lib_id):
        if lib_id in self.libsyms:
            return self.libsyms[lib_id]
        if lib_id == "OpenChess:HALL_SWITCH_SOT23":
            s = hall_symbol()
        else:
            lib, name = lib_id.split(":", 1)
            s = flatten(lib, name)
        self.libsyms[lib_id] = s
        return s

    def wire(self, x1, y1, x2, y2):
        self.items.append(S(sym("wire"), S(sym("pts"), S(sym("xy"), r(x1), r(y1)), S(sym("xy"), r(x2), r(y2))),
                            S(sym("stroke"), S(sym("width"), 0), S(sym("type"), sym("default"))),
                            S(sym("uuid"), sym(U(f"wire/{x1}/{y1}/{x2}/{y2}")))))

    def label(self, net, x, y, ang, glob=False):
        just = {0: ("left", "bottom"), 90: ("left", "bottom"), 180: ("right", "bottom"), 270: ("right", "bottom")}[ang]
        kind = "global_label" if glob else "label"
        node = S(sym(kind), net, S(sym("at"), r(x), r(y), ang), S(sym("fields_autoplaced")),
                 S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), S(sym("justify"), sym(just[0]), sym(just[1]))),
                 S(sym("uuid"), sym(U(f"label/{net}/{x}/{y}"))))
        if glob:
            node.insert(2, S(sym("shape"), sym("bidirectional")))
        self.items.append(node)

    def power(self, net, x, y):
        self.pwr_n += 1
        ref = f"#PWR{self.pwr_n:03d}"
        lib_id = {"GND": "power:GND", "+5V": "power:+5V", "+3V3": "power:+3V3"}[net]
        self.ensure_lib(lib_id)
        self.items.append(S(sym("symbol"), S(sym("lib_id"), lib_id), S(sym("at"), r(x), r(y), 0), S(sym("unit"), 1),
                            S(sym("in_bom"), sym("yes")), S(sym("on_board"), sym("yes")), S(sym("dnp"), sym("no")),
                            S(sym("uuid"), sym(U(f"pwr/{ref}"))),
                            S(sym("property"), "Reference", ref, S(sym("at"), r(x), r(y), 0),
                              S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), sym("hide"))),
                            S(sym("property"), "Value", net, S(sym("at"), r(x), r(y + (3.0 if net == "GND" else -3.0)), 0),
                              S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)))),
                            S(sym("property"), "Footprint", "", S(sym("at"), r(x), r(y), 0),
                              S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), sym("hide"))),
                            S(sym("property"), "Datasheet", "", S(sym("at"), r(x), r(y), 0),
                              S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), sym("hide"))),
                            S(sym("pin"), "1", S(sym("uuid"), sym(U(f"pwr/{ref}/1")))),
                            S(sym("instances"), S(sym("project"), PROJECT,
                                                  S(sym("path"), "/" + ROOT_UUID, S(sym("reference"), ref), S(sym("unit"), 1))))))

    def pwr_flag(self, net, x, y):
        self.ensure_lib("power:PWR_FLAG")
        self.pwr_n += 1
        ref = f"#FLG{self.pwr_n:03d}"
        self.items.append(S(sym("symbol"), S(sym("lib_id"), "power:PWR_FLAG"), S(sym("at"), r(x), r(y), 0), S(sym("unit"), 1),
                            S(sym("in_bom"), sym("yes")), S(sym("on_board"), sym("yes")), S(sym("dnp"), sym("no")),
                            S(sym("uuid"), sym(U(f"flg/{ref}"))),
                            S(sym("property"), "Reference", ref, S(sym("at"), r(x), r(y), 0),
                              S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), sym("hide"))),
                            S(sym("property"), "Value", "PWR_FLAG", S(sym("at"), r(x), r(y - 4), 0),
                              S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)))),
                            S(sym("property"), "Footprint", "", S(sym("at"), r(x), r(y), 0),
                              S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), sym("hide"))),
                            S(sym("property"), "Datasheet", "", S(sym("at"), r(x), r(y), 0),
                              S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), sym("hide"))),
                            S(sym("pin"), "1", S(sym("uuid"), sym(U(f"flg/{ref}/1")))),
                            S(sym("instances"), S(sym("project"), PROJECT,
                                                  S(sym("path"), "/" + ROOT_UUID, S(sym("reference"), ref), S(sym("unit"), 1))))))
        # stub down + label
        self.wire(x, y, x, y + 2.54)
        self.label(net, x, y + 2.54, 270)

    def part(self, p: D.Part, x, y, stub=2.54, power_syms=True, labels=True):
        symdef = self.ensure_lib(p.symbol)
        pins = symbol_pins(symdef)
        fx = S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)))
        fxh = S(sym("effects"), S(sym("font"), S(sym("size"), 1.27, 1.27)), sym("hide"))
        # bounding box of pins for ref/value placement
        ys = [pp[1] for pp in pins.values()] or [0]
        xs = [pp[0] for pp in pins.values()] or [0]
        top = y - max(ys) - 2.5
        node = S(sym("symbol"), S(sym("lib_id"), p.symbol), S(sym("at"), r(x), r(y), 0), S(sym("unit"), 1),
                 S(sym("in_bom"), sym("yes" if p.pins else "no")), S(sym("on_board"), sym("yes")), S(sym("dnp"), sym("no")),
                 S(sym("uuid"), sym(p.uuid)),
                 S(sym("property"), "Reference", p.ref, S(sym("at"), r(x + max(xs) + 1.0 if xs else x), r(top), 0), fx),
                 S(sym("property"), "Value", p.value, S(sym("at"), r(x + max(xs) + 1.0 if xs else x), r(top + 2.54), 0), fx),
                 S(sym("property"), "Footprint", p.footprint, S(sym("at"), r(x), r(y), 0), fxh),
                 S(sym("property"), "Datasheet", "~", S(sym("at"), r(x), r(y), 0), fxh),
                 S(sym("property"), "LCSC", p.lcsc, S(sym("at"), r(x), r(y), 0), fxh),
                 S(sym("property"), "MPN", p.mpn, S(sym("at"), r(x), r(y), 0), fxh))
        for num in pins:
            node.append(S(sym("pin"), num, S(sym("uuid"), sym(U(f"{p.ref}/pin/{num}")))))
        node.append(S(sym("instances"), S(sym("project"), PROJECT,
                                          S(sym("path"), "/" + ROOT_UUID, S(sym("reference"), p.ref), S(sym("unit"), 1)))))
        self.items.append(node)
        # stubs + labels
        done_nets = set()
        for num, (px, py, pa, pname) in pins.items():
            net = p.pins.get(num)
            if net is None:
                continue
            net = D.canonical_net(net)
            cx, cy = x + px, y - py
            a = math.radians(pa)
            dx, dy = -math.cos(a), math.sin(a)
            dx, dy = round(dx), round(dy)
            ex, ey = cx + dx * stub, cy + dy * stub
            if net.startswith("NC"):
                self.items.append(S(sym("no_connect"), S(sym("at"), r(cx), r(cy)), S(sym("uuid"), sym(U(f"{p.ref}/nc/{num}")))))
                continue
            self.wire(cx, cy, ex, ey)
            if power_syms and net in ("GND", "+5V", "+3V3"):
                self.power(net, ex, ey)
            elif labels:
                ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(dx, dy)]
                self.label(net, ex, ey, ang)

    def text(self, s, x, y, size=2.5):
        self.items.append(S(sym("text"), s, S(sym("at"), r(x), r(y), 0),
                            S(sym("effects"), S(sym("font"), S(sym("size"), size, size), sym("bold")), S(sym("justify"), sym("left"), sym("bottom"))),
                            S(sym("uuid"), sym(U(f"text/{s}/{x}/{y}")))))

    def dump(self):
        root = S(sym("kicad_sch"), S(sym("version"), 20230121), S(sym("generator"), sym("openchess_gen")),
                 S(sym("uuid"), sym(ROOT_UUID)), S(sym("paper"), "A1"),
                 S(sym("title_block"), S(sym("title"), "OpenChess PCB redesign - 8x8 Hall/WS2812B board"),
                   S(sym("date"), datetime.date.today().isoformat()), S(sym("rev"), "1.0"),
                   S(sym("comment"), 1, "Generated by tools/gen_sch.py - firmware-compatible with joojoooo/OpenChess"),
                   S(sym("comment"), 2, f"pitch {D.PITCH} mm, sensor {D.SENSOR['value']} pinout {D.SENSOR['pins']}")),
                 S(sym("lib_symbols"), *self.libsyms.values()))
        root.extend(self.items)
        root.append(S(sym("sheet_instances"), S(sym("path"), "/", S(sym("page"), "1"))))
        return dumps(root) + "\n"

def r(v):
    """snap to 0.01 mm (keeps 1.27 grid alignment of our coordinates)."""
    return round(v, 2)

def build():
    parts = D.build_parts()
    for p in parts:
        p.uuid = U(f"sym/{p.ref}")
    byref = {p.ref: p for p in parts}
    sch = Sch()

    # --- sensor matrix (top-left) -------------------------------------------
    sch.text("HALL SENSOR MATRIX  (columns = switched +5V via PNP, rows = open-collector OUT wired-OR, 10k pull-up to 3V3)", 20, 20, 2.0)
    for r_ in range(8):
        for f in range(8):
            p = byref[f"H{r_*8+f+1}"]
            x = 30 + 25.4 * f
            y = 40 + 22.86 * (7 - r_)
            sch.part(p, x, y)
    # --- LED matrix (bottom-left) -------------------------------------------
    sch.text("WS2812B LED CHAIN  (serpentine a1->h1, h2->a2, ... ; each LED has a 100nF cap)", 20, 232, 2.0)
    order = D.led_chain_order()
    for k, (f, r_) in enumerate(order):
        p = byref[f"D{k+1}"]
        x = 30 + 30.48 * f
        y = 250 + 25.4 * (7 - r_)
        sch.part(p, x, y)
    for k in range(64):
        p = byref[f"C{k+1}"]
        x = 280 + 12.7 * (k % 8)
        y = 255 + 20.32 * (k // 8)
        sch.part(p, x, y)
    # --- controller ---------------------------------------------------------
    sch.text("CONTROLLER  (ESP32-WROOM-32E, CH340C USB-UART, AMS1117-3.3, 74HCT595 column driver, 74AHCT1G125 LED level shifter)", 240, 20, 2.0)
    place = {
        "U1": (300, 95), "U3": (400, 100), "J1": (480, 100), "U4": (560, 100),
        "U2": (420, 180), "F1": (460, 180), "C75": (480, 180), "C76": (495, 180), "J2": (530, 180),
        "DL1": (570, 185), "R24": (590, 180),
        "Q9": (400, 220), "R21": (385, 240), "Q10": (440, 220), "R22": (425, 240),
        "C65": (300, 180), "C66": (315, 180), "R19": (330, 180), "C67": (345, 180), "R20": (360, 180),
        "SW1": (300, 215), "SW2": (330, 215),
        "U5": (560, 160), "C74": (590, 160), "R23": (600, 180),
        "C68": (420, 215), "C69": (440, 215), "C71": (470, 215), "C72": (490, 215), "C73": (510, 215),
        "R17": (520, 240), "R18": (535, 240),
    }
    for i in range(8):
        place[f"R{9+i}"] = (300 + 12.7 * i, 260)
        place[f"R{1+i}"] = (640, 50 + 22.86 * i)
        place[f"Q{1+i}"] = (665, 50 + 22.86 * i)
    for i in range(7):
        place[f"MH{i+1}"] = (720 + 12 * i, 300)
    for ref, (x, y) in place.items():
        sch.part(byref[ref], x, y)
    sch.text("Column drivers: 74HCT595 Qn -> 1k -> PNP base; emitter +5V; collector = COLn (switched +5V to 8 sensors). Firmware: SR_INVERT_OUTPUTS = PNP", 620, 40, 1.5)
    sch.text("ESP32 GPIO map = OpenChess defaults: LED IO32, SR SER IO33, SRCLK IO14, RCLK IO26, rows IO4,16,17,18,19,21,22,23", 240, 300, 1.5)
    # power flags
    sch.text("POWER FLAGS", 700, 360, 1.5)
    for i, n in enumerate(["+5V", "+3V3", "GND", "VBUS"]):
        sch.pwr_flag(n, 700 + 15 * i, 370)
    return sch, parts

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "hardware", PROJECT + ".kicad_sch")
    sch, parts = build()
    open(out, "w", encoding="utf-8").write(sch.dump())
    print("wrote", out, "libsyms:", len(sch.libsyms))
