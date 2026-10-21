"""Generate the KiCad 7 PCB: placement + scripted routing of the 8x8 matrix.

The controller strip is left for the autorouter (tools/route.py).
"""
import os, sys, json, math, uuid
sys.path.insert(0, os.path.dirname(__file__))
import pcbnew
import design as D
from gen_sch import U, ROOT_UUID, PROJECT

MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))
def mm(v): return pcbnew.ToMM(v)

def set_page(path):
    """A2 portrait page so that plots/PDFs contain the whole 340 x 374 mm board.
    (PAGE_INFO is not exposed to Python in KiCad 7, so patch the saved file.)"""
    import re
    txt = open(path, encoding="utf-8").read()
    txt = re.sub(r'\(paper "[^"]*"( portrait)?\)', '(paper "A2" portrait)', txt, count=1)
    open(path, "w", encoding="utf-8").write(txt)


class Builder:
    def __init__(self):
        self.b = pcbnew.BOARD()
        self.nets = {}
        self.fps = {}
        ds = self.b.GetDesignSettings()
        ds.SetCopperLayerCount(2)
        ds.m_MinClearance = MM(D.CLEARANCE)
        ds.m_TrackMinWidth = MM(0.2)
        ds.m_ViasMinSize = MM(0.5)
        ds.m_ViasMinAnnularWidth = MM(0.13)
        ds.m_MinThroughDrill = MM(0.2)
        ds.m_CopperEdgeClearance = MM(0.3)
        ds.m_HoleClearance = MM(0.25)
        ds.m_HoleToHoleMin = MM(0.5)
        ds.m_SolderMaskMinWidth = MM(0.0)
        ds.m_SolderMaskExpansion = MM(0.0)
        try:                                   # KiCad 7/8
            nc = ds.m_NetSettings.m_DefaultNetClass
        except AttributeError:                 # KiCad 9/10
            nc = ds.m_NetSettings.GetDefaultNetclass()
        nc.SetClearance(MM(D.CLEARANCE)); nc.SetTrackWidth(MM(D.W_SIG))
        nc.SetViaDiameter(MM(D.VIA_D)); nc.SetViaDrill(MM(D.VIA_DRILL))
        ds.SetBoardThickness(MM(1.6))

    # --- nets -----------------------------------------------------------
    def net(self, name):
        if name is None or name.startswith("NC"):
            return None
        name = D.canonical_net(name)
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def netcode(self, name):
        n = self.net(name)
        return n.GetNetCode() if n else 0

    # --- footprints -------------------------------------------------------
    def add_part(self, p: D.Part, x=None, y=None, rot=None):
        lib, name = p.footprint.split(":", 1)
        fp = pcbnew.FootprintLoad(os.path.join(D.FP_LIB, lib + ".pretty"), name)
        if fp is None:
            raise RuntimeError("footprint not found: " + p.footprint)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(p.ref); fp.SetValue(p.value)
        self.b.Add(fp)
        fp.SetPosition(V(p.x if x is None else x, p.y if y is None else y))
        fp.SetOrientationDegrees(p.rot if rot is None else rot)
        fp.SetPath(pcbnew.KIID_PATH("/" + ROOT_UUID + "/" + U(f"sym/{p.ref}")))
        for pad in fp.Pads():
            netname = p.pins.get(pad.GetNumber())
            n = self.net(netname)
            if n:
                pad.SetNet(n)
        # reference text: smaller for the matrix parts
        if p.ref[0] in "HDC" and p.ref[1:].isdigit() and int(p.ref[1:]) <= 64:
            fp.Reference().SetVisible(False)
        if p.ref in ("U1", "J1", "U4", "C73"):   # solid zone connection: ESP32 thermal pad, USB-C GND pads, 595 GND pins
            for pad in fp.Pads():
                if p.pins.get(pad.GetNumber()) == "GND":
                    pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        if not p.pins:  # mounting holes
            fp.Reference().SetVisible(False)
        self.fps[p.ref] = fp
        return fp

    def pad(self, ref, num):
        """(x, y) in mm of a pad after placement."""
        fp = self.fps[ref]
        pd = fp.FindPadByNumber(str(num))
        return mm(pd.GetPosition().x), mm(pd.GetPosition().y)

    # --- copper -----------------------------------------------------------
    def track(self, x1, y1, x2, y2, layer, width, net, locked=True):
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(V(x1, y1)); t.SetEnd(V(x2, y2))
        t.SetWidth(MM(width)); t.SetLayer(layer); t.SetNetCode(self.netcode(net))
        t.SetLocked(locked)
        self.b.Add(t)
        return t

    def poly(self, pts, layer, width, net):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) != (x2, y2):
                self.track(x1, y1, x2, y2, layer, width, net)

    def via(self, x, y, net, d=D.VIA_D, drill=D.VIA_DRILL, locked=True):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(V(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetDrill(MM(drill)); v.SetWidth(MM(d))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNetCode(self.netcode(net))
        v.SetLocked(locked)
        self.b.Add(v)
        return v

    def zone(self, pts, layer, net, name, clearance=0.25, minw=0.25, priority=0):
        z = pcbnew.ZONE(self.b)
        z.SetLayer(layer); z.SetNetCode(self.netcode(net)); z.SetZoneName(name)
        ol = z.Outline(); ol.NewOutline()
        for x, y in pts:
            ol.Append(MM(x), MM(y))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
        z.SetLocalClearance(MM(clearance)); z.SetMinThickness(MM(minw))
        z.SetAssignedPriority(priority)
        z.SetIsFilled(False)
        self.b.Add(z)
        return z

    def rule_area(self, pts, layers, name, tracks=True, vias=True, pour=True):
        z = pcbnew.ZONE(self.b)
        z.SetIsRuleArea(True); z.SetZoneName(name)
        z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias); z.SetDoNotAllowCopperPour(pour)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        for l in layers:
            (ls.addLayer if hasattr(ls, "addLayer") else ls.AddLayer)(l)
        z.SetLayerSet(ls)
        ol = z.Outline(); ol.NewOutline()
        for x, y in pts:
            ol.Append(MM(x), MM(y))
        self.b.Add(z)
        return z

    def free_spot(self, x, y, keep=0.3, skip_ref=None):
        """True if a via at (x, y) keeps `keep` mm from every pad (except skip_ref's own) and track."""
        px, py = MM(x), MM(y)
        r = MM(D.VIA_D / 2 + keep)
        for fp in self.b.GetFootprints():
            if fp.GetReference() == skip_ref:
                continue
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                if bb.GetLeft() - r < px < bb.GetRight() + r and bb.GetTop() - r < py < bb.GetBottom() + r:
                    return False
        for tr in self.b.GetTracks():
            bb = tr.GetBoundingBox()
            if bb.GetLeft() - r < px < bb.GetRight() + r and bb.GetTop() - r < py < bb.GetBottom() + r:
                return False
        return 1.0 < x < D.BOARD_W - 1.0 and 1.0 < y < D.BOARD_H - 1.0

    def stitch_grid(self, xs, ys, net, exclude=None, keep=0.5):
        """Add vias on a grid wherever they are at least `keep` mm away from every pad/track/via."""
        items = []
        for fp in self.b.GetFootprints():
            for pad in fp.Pads():
                items.append(pad.GetBoundingBox())
        for tr in self.b.GetTracks():
            items.append(tr.GetBoundingBox())
        r = MM(D.VIA_D / 2 + keep)
        n = 0
        for x in xs:
            for y in ys:
                if exclude and exclude(x, y):
                    continue
                px, py = MM(x), MM(y)
                ok = True
                for bb in items:
                    if bb.GetLeft() - r < px < bb.GetRight() + r and bb.GetTop() - r < py < bb.GetBottom() + r:
                        ok = False; break
                if ok:
                    self.via(x, y, net); n += 1
        return n

    # --- graphics -----------------------------------------------------------
    def rect_edge(self, x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(self.b); s.SetShape(pcbnew.SHAPE_T_RECT)
        s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        self.b.Add(s)

    def circle(self, x, y, r, layer=pcbnew.F_SilkS, w=0.15):
        s = pcbnew.PCB_SHAPE(self.b); s.SetShape(pcbnew.SHAPE_T_CIRCLE)
        s.SetStart(V(x, y)); s.SetEnd(V(x + r, y)); s.SetLayer(layer); s.SetWidth(MM(w))
        self.b.Add(s)

    def line(self, x1, y1, x2, y2, layer=pcbnew.F_SilkS, w=0.15):
        s = pcbnew.PCB_SHAPE(self.b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2)); s.SetLayer(layer); s.SetWidth(MM(w))
        self.b.Add(s)

    def text(self, s, x, y, size=1.5, layer=pcbnew.F_SilkS, thick=None, rot=0):
        t = pcbnew.PCB_TEXT(self.b); t.SetText(s); t.SetPosition(V(x, y)); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(thick or size * 0.15))
        t.SetTextAngleDegrees(rot)
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        self.b.Add(t)


def build(out_path):
    B = Builder()
    parts = D.build_parts()
    byref = {p.ref: p for p in parts}
    Ys, W, H = D.STRIP_Y, D.BOARD_W, D.BOARD_H
    F, Bk = pcbnew.F_Cu, pcbnew.B_Cu

    B.rect_edge(0, 0, W, H)

    # ------------------------------------------------------------------ parts
    for p in parts:
        if p.extra.get("led_cap"):
            continue  # placed below from LED pad geometry
        B.add_part(p)

    # dev board sockets: make pin numbers increase towards +x
    for ref in ("J3", "J4"):
        if ref in B.fps:
            fp = B.fps[ref]
            for rot in (90, 270, 0, 180):
                fp.SetOrientationDegrees(rot)
                p1, p2 = B.pad(ref, "1"), B.pad(ref, "2")
                if abs(p2[1] - p1[1]) < 0.01 and p2[0] > p1[0]:
                    break
            fp.SetPosition(V(D.DEV_X0 - (B.pad(ref, "1")[0] - mm(fp.GetPosition().x)), mm(fp.GetPosition().y)))

    # LED decoupling caps: next to the LED VDD pad
    for p in parts:
        if not p.extra.get("led_cap"):
            continue
        f, r = p.extra["square"]
        cx, cy = D.sq_center(f, r)
        if r % 2 == 0:   # LED rot 180: VDD pad bottom-right -> cap below it, pad1 on top
            B.add_part(p, cx + 2.45, cy + D.LED_DY + 4.6, 270)
        else:            # LED rot 0: VDD pad top-left -> cap to the left, pad1 on the right
            B.add_part(p, cx - 6.6, cy + D.LED_DY - 1.65, 180)

    # ------------------------------------------------------------ matrix routing
    bus_top = {}
    for r in range(8):
        for f in range(8):
            i = r * 8 + f
            cx, cy = D.sq_center(f, r)
            href = f"H{i+1}"
            pv = B.pad(href, D.SENSOR["pins"]["VCC"])
            po = B.pad(href, D.SENSOR["pins"]["OUT"])
            colx = cx + D.COL_DX
            # VCC pad -> via on the column trace
            B.track(pv[0], pv[1], colx, pv[1], F, D.W_SIG, f"COL{f}")
            B.via(colx, pv[1], f"COL{f}")
            # OUT pad -> row trace
            rowy = cy + D.ROW_DY
            if po[1] < cy:   # OUT on an upper pad: go left first, then down
                B.poly([po, (cx - 2.6, po[1]), (cx - 2.6, rowy)], F, D.W_SIG, f"ROW{r}")
            else:
                B.track(po[0], po[1], po[0], rowy, F, D.W_SIG, f"ROW{r}")
        # row trace: from the h-file stub to the left-margin bundle via
        cxh, cyr = D.sq_center(7, r)
        rowy = cyr + D.ROW_DY
        x_end = D.ROWBUS_X0 + D.ROWBUS_PITCH * r
        B.track(cxh - 0.94 if B.pad(f"H{r*8+8}", D.SENSOR["pins"]["OUT"])[1] >= cyr else cxh - 2.6, rowy,
                x_end, rowy, F, D.W_SIG, f"ROW{r}")
        B.via(x_end, rowy, f"ROW{r}")
        B.track(x_end, rowy, x_end, Ys + (6.0 if D.VARIANT == "module" else 15.0), Bk, D.W_SIG, f"ROW{r}")   # bundle down to the strip

    # column traces (B.Cu) and vertical +5V buses (B.Cu)
    for f in range(8):
        cx8, cy8 = D.sq_center(f, 7)
        cx1, cy1 = D.sq_center(f, 0)
        colx = cx8 + D.COL_DX
        top = B.pad(f"H{7*8+f+1}", D.SENSOR["pins"]["VCC"])[1]
        B.track(colx, top, colx, Ys - 1.5, Bk, D.W_COL, f"COL{f}")
        B.via(colx, Ys - 1.5, f"COL{f}")
        # down to the PNP collector (F.Cu)
        qc = B.pad(f"Q{f+1}", "3")
        B.track(colx, Ys - 1.5, qc[0], qc[1], F, D.W_COL, f"COL{f}")
        busx = cx8 + D.BUS_DX
        B.track(busx, cy8 + 5.5, busx, Ys + 2.0, Bk, D.W_BUS, "+5V")   # rank 8 LED via is at cy+5.5

    # main +5V bus (B.Cu) along the top of the strip, plus power-entry trace
    cxa, _ = D.sq_center(0, 0); cxh, _ = D.sq_center(7, 0)
    B.track(cxa + D.COL_DX + 0.95, Ys + 2.0, cxh + D.BUS_DX, Ys + 2.0, Bk, D.W_MAINBUS, "+5V")   # from Q1 emitter via to the h bus
    # power entry: B.Cu 3 mm from the bus down to 3 vias, then F.Cu bar to the fuse (+5V side)
    f2 = B.pad("F1", "2"); f1 = B.pad("F1", "1")
    if not D.BATTERY:
        ey = f2[1] - 2.36
        B.track(99.0, Ys + 2.0, 99.0, ey, Bk, 3.0, "+5V")
        for vx in (97.5, 99.0, 100.5):
            B.via(vx, ey, "+5V", 0.8, 0.4)
        B.track(97.5, ey, 100.5, ey, F, 1.5, "+5V")
        B.track(99.0, ey, f2[0], f2[1], F, 1.5, "+5V")
    else:
        route_battery_block(B, f2, Ys, H)
    # USB VBUS: thin stubs out of the 0.5 mm pad row, then a 0.8 mm B.Cu run under the connector to the fuse.
    vb = sorted({round(B.pad("J1", n)[0], 3) for n in ("A4", "A9", "B4", "B9")})
    vy = B.pad("J1", "A4")[1]
    vyr = vy - 1.45
    for vx in vb:
        B.track(vx, vy, vx, vyr, F, 0.28, "VBUS")
    B.track(vb[0], vyr, vb[0] - 2.55, vyr, F, 0.3, "VBUS"); B.via(vb[0] - 2.55, vyr, "VBUS", 0.8, 0.4)
    B.track(vb[1], vyr, vb[1] + 1.75, vyr, F, 0.3, "VBUS"); B.via(vb[1] + 1.75, vyr, "VBUS", 0.8, 0.4)
    B.track(vb[0] - 2.55, vyr, f1[0] - 1.5, vyr, Bk, 0.8, "VBUS"); B.via(f1[0] - 1.5, vyr, "VBUS", 0.8, 0.4)
    B.track(f1[0] - 1.5, vyr, f1[0], f1[1], F, 0.8, "VBUS")
    # USB signal escape: 0.2 mm stubs straight up, fan out to 1.3 mm pitch; D-/D+ pad pairs are interleaved,
    # so the D- pair is bridged on B.Cu and the D+ pair on F.Cu above it.
    sig = [("A5", "CC1"), ("B7", "USB_D-"), ("A6", "USB_D+"), ("A7", "USB_D-"), ("B6", "USB_D+"), ("B5", "CC2")]
    fan = [74.3, 75.6, 76.9, 78.2, 79.5, 80.8]
    ends = {}
    y1, y2 = vy - 2.55, vy - 6.55
    for (pn, net), fx in zip(sig, fan):
        if net not in B.nets:          # nodemcu variant: USB-C is power only
            continue
        px, py = B.pad("J1", pn)
        B.poly([(px, py), (px, y1), (fx, y2)], F, 0.2, net)
        ends.setdefault(net, []).append(fx)
    if "USB_D-" in ends:
        dm = ends["USB_D-"]; dp = ends["USB_D+"]
        for fx in dm:
            B.track(fx, y2, fx, y2 - 1.0, F, 0.2, "USB_D-"); B.via(fx, y2 - 1.0, "USB_D-")
        B.track(dm[0], y2 - 1.0, dm[1], y2 - 1.0, Bk, 0.3, "USB_D-")
        B.track(dm[1], y2 - 1.0, dm[1], y2 - 3.0, Bk, 0.3, "USB_D-")
        for fx in dp:
            B.track(fx, y2, fx, y2 - 2.5, F, 0.2, "USB_D+")
        B.track(dp[0], y2 - 2.5, dp[1], y2 - 2.5, F, 0.3, "USB_D+")
        B.track(dp[1], y2 - 2.5, dp[1], y2 - 3.5, F, 0.3, "USB_D+")
    # external 5V input J2 -> +5V: to the fuse output (no battery block) or straight up into the bus (B.Cu)
    j2 = B.pad("J2", "1")
    if not D.BATTERY:
        B.poly([j2, (j2[0], f2[1]), f2], F, 1.0, "+5V")
    else:
        B.track(j2[0], j2[1], j2[0], Ys + 2.0, Bk, 2.0, "+5V")

    # LEDs: VDD stubs + vias to the bus, caps, data links
    order = D.led_chain_order()
    for k, (f, r) in enumerate(order):
        cx, cy = D.sq_center(f, r)
        dref, cref = f"D{k+1}", f"C{k+1}"
        vdd = B.pad(dref, "1"); dout = B.pad(dref, "2"); din = B.pad(dref, "4")
        busx = cx + D.BUS_DX
        c1 = B.pad(cref, "1")
        if r % 2 == 0:   # rot 180
            B.track(vdd[0], vdd[1], busx, vdd[1], F, 0.3, "+5V"); B.via(busx, vdd[1], "+5V")
            B.track(vdd[0], vdd[1], c1[0], c1[1], F, 0.3, "+5V")
        else:            # rot 0
            B.poly([vdd, (vdd[0], cy + 5.5), (busx, cy + 5.5)], F, 0.3, "+5V"); B.via(busx, cy + 5.5, "+5V")
            B.track(vdd[0], vdd[1], c1[0], c1[1], F, 0.3, "+5V")
        # data link to the next LED
        if k == 63:
            continue
        net = f"LED{k+1}"
        nf, nr = order[k + 1]
        ncx, ncy = D.sq_center(nf, nr)
        ndin = B.pad(f"D{k+2}", "4")
        if nr == r:
            if r % 2 == 0:  # left -> right
                B.poly([dout, (ncx - 7.5, dout[1]), (ncx - 4.2, ndin[1]), ndin], F, D.W_SIG, net)
            else:           # right -> left
                B.poly([dout, (ncx + 7.5, dout[1]), (ncx + 4.2, ndin[1]), ndin], F, D.W_SIG, net)
        else:               # serpentine turn: via + B.Cu vertical link in the margin side
            lx = cx + 3.5 if r % 2 == 0 else cx - 3.5
            B.track(dout[0], dout[1], lx, dout[1], F, D.W_SIG, net); B.via(lx, dout[1], net)
            B.track(lx, dout[1], lx, ndin[1], Bk, D.W_SIG, net); B.via(lx, ndin[1], net)
            B.track(lx, ndin[1], ndin[0], ndin[1], F, D.W_SIG, net)

    # ------------------------------------------------- strip: fixed pre-routing
    band_row = {0: 3, 1: 2, 2: 1, 3: 0, 4: 0, 5: 1, 6: 2, 7: 3}
    for f in range(8):
        qb = B.pad(f"Q{f+1}", "1"); qe = B.pad(f"Q{f+1}", "2")
        r1 = B.pad(f"R{f+1}", "2"); r2 = B.pad(f"R{f+1}", "1")   # R pin2 = SRQn_R (to base), pin1 = SRQn
        rtop, rbot = (r1, r2) if r1[1] < r2[1] else (r2, r1)
        B.track(qb[0], qb[1], rtop[0], rtop[1], F, D.W_SIG, f"SRQ{f}_R")
        # emitter -> +5V main bus via
        B.track(qe[0], qe[1], qe[0], Ys + 2.0, F, 0.4, "+5V"); B.via(qe[0], Ys + 2.0, "+5V")
        # base-drive band row towards the 74HCT595 (freerouting finishes the last bit)
        y_i = Ys + 12.2 + 0.8 * band_row[f]
        x_end = 160.0 if f < 4 else 180.0
        B.poly([rbot, (rbot[0], y_i), (x_end, y_i)], F, D.W_SIG, f"SRQ{f}")

    # dev-board socket GND pins: short stub + via so they never end up on a pour island
    if D.VARIANT != "module":
        for ref, pn, dy in (("J3", "1", -3.0), ("J3", "7", +3.0), ("J4", "14", -3.0)):   # pin 1 goes up: outside the no-pour area
            px, py = B.pad(ref, pn)
            B.track(px, py, px, py + dy, F, 0.4, "GND"); B.via(px, py + dy, "GND")

    # every 2-pad SMD part in the strip with a GND pad gets its own GND via (stub away from the other pad),
    # so decoupling caps / pull-downs never end up on a pour island after autorouting
    for p in (parts if D.VARIANT == "module" else [q for q in parts if q.ref in D.BATTERY_REFS]):   # nodemcu strip routes better without them
        if p.ref[0] in "HDC" and p.ref[1:].isdigit() and int(p.ref[1:]) <= 64:
            continue
        if len(p.pins) != 2 or "GND" not in p.pins.values() or not p.footprint.split(":")[1].startswith(("C_", "R_", "LED_")):
            continue
        gpin = next(k for k, v in p.pins.items() if v == "GND"); opin = next(k for k in p.pins if k != gpin)
        gx, gy = B.pad(p.ref, gpin); ox, oy = B.pad(p.ref, opin)
        dx, dy = gx - ox, gy - oy; L = (dx * dx + dy * dy) ** 0.5; dx, dy = dx / L, dy / L
        for ddx, ddy, dist in ((dx, dy, 1.4), (dx, dy, 1.8), (-dy, dx, 1.5), (dy, -dx, 1.5)):
            vx, vy = gx + ddx * dist, gy + ddy * dist
            if B.free_spot(vx, vy, keep=0.3, skip_ref=p.ref):
                B.track(gx, gy, vx, vy, F, 0.3, "GND"); B.via(vx, vy, "GND")
                break

    # ESP32 module: tie its GND pins to the thermal pad under the module body (the router cannot block that),
    # and chain the two decoupling caps' GND pads into pin 1 so they never sit on a pour island.
    if D.VARIANT == "module":
        tp = [B.pad("U1", "39")]   # first "39" sub-pad is fine: all 39 pads are one copper area
        tx, ty = tp[0]
        p1 = B.pad("U1", "1"); p38 = B.pad("U1", "38"); p15 = B.pad("U1", "15")
        B.poly([p1, (tx + 1.0, p1[1]), (tx + 1.0, ty)], F, 0.4, "GND")
        B.poly([p38, (tx - 2.4, p38[1]), (tx - 2.4, ty)], F, 0.4, "GND")
        B.poly([p15, (p15[0], ty - 3.0), (tx, ty)], F, 0.4, "GND")
        c66 = B.pad("C66", "2"); c67 = B.pad("C67", "2")
        xs = p1[0] + 4.5
        B.poly([c67, (xs, c67[1]), (xs, c66[1]), c66], F, 0.3, "GND")
        B.poly([(xs, c66[1]), (xs, p1[1]), p1], F, 0.3, "GND")

    # 74HCT595 OE pin (GND) sits in a pad row the router tends to box in: give it its own via before routing
    px, py = B.pad("U4", "13")
    B.track(px, py, px, py - 2.6, F, 0.3, "GND"); B.via(px, py - 2.6, "GND")

    # ------------------------------------------------------------ zones (GND)
    outline = [(0, 0), (W, 0), (W, H), (0, H)]
    B.zone(outline, F, "GND", "GND_top")
    B.zone(outline, Bk, "GND", "GND_bottom")
    # antenna keep-out (no copper of any kind under the ESP32 antenna)
    if D.VARIANT == "module":
        ant = [(0.0, Ys + 33.8), (40.0, Ys + 33.8), (40.0, H), (0.0, H)]
        B.rule_area(ant, [F, Bk], "antenna_keepout")
    else:   # no pour under the dev board's antenna end (tracks to the end pins are allowed)
        y0 = Ys + D.DEV_Y0_OFFSET
        # (KiCad exports every rule area as a router keepout, so keep it clear of the end pins' escape path)
        ant = [(0.0, y0 + 2.0), (D.DEV_X0 + 8.0, y0 + 2.0), (D.DEV_X0 + 8.0, y0 + D.DEV_ROW_SPACING - 2.0), (0.0, y0 + D.DEV_ROW_SPACING - 2.0)]
        B.rule_area(ant, [F, Bk], "devboard_antenna_nopour", tracks=False, vias=False, pour=True)

    # ------------------------------------------------------- GND stitching vias
    for i in range(9):
        for j in range(9):
            B.via(D.GRID_X0 + D.PITCH * i, D.GRID_Y0 + D.PITCH * j, "GND")
    for f in range(8):
        cx, _ = D.sq_center(f, 0)
        B.via(cx + 15.0, Ys + 16.3, "GND")
        B.via(cx, 4.0, "GND")
    B.stitch_grid([66, 90, 108, 150, 170, 190, 210, 230, 250, 270, 290, 310], [H - 2.5], "GND", keep=0.3)
    for y in range(40, int(Ys) - 20, 40):
        B.via(W - 5.0, y + 20, "GND")
    if D.VARIANT == "module":
        excl = lambda x, y: (x < 42 and y > Ys + 12) or (x < 40 and y > Ys + 33)
    else:
        excl = lambda x, y: (x < 58 and y > Ys + 15)
    B.stitch_grid([x for x in range(30, int(W) - 8, 6)], [Ys + 17.5 + 5.5 * k for k in range(int((H - Ys - 20) / 5.5))], "GND",
                  exclude=excl)

    # -------------------------------------------------------------- silkscreen
    for r in range(8):
        for f in range(8):
            cx, cy = D.sq_center(f, r)
            B.circle(cx, cy, D.DISC_DIA / 2)
            B.text(D.sq_name(f, r), cx - 16.5, cy - 16.0, 2.0)
            B.line(cx - D.PITCH / 2, cy - D.PITCH / 2, cx + D.PITCH / 2, cy - D.PITCH / 2, w=0.1)
            B.line(cx - D.PITCH / 2, cy - D.PITCH / 2, cx - D.PITCH / 2, cy + D.PITCH / 2, w=0.1)
    B.text(f"OpenChess PCB v1.0 ({D.VARIANT})", 316, H - 13.5, 1.5)
    B.text("LED IO32 | SER IO33 SRCLK IO14 RCLK IO26", 316, H - 11.0, 1.0)
    B.text("ROW1..8 = IO4,16,17,18,19,21,22,23", 316, H - 8.8, 1.0)
    B.text("SR_INVERT_OUTPUTS = PNP (WebUI)", 316, H - 6.6, 1.0)
    B.text("J1 USB-C 5V/3A | J2 5V/4A in", 316, H - 4.4, 1.0)
    if D.BATTERY:
        B.text("JP1: 1-2 USB  2-3 BATTERY", 196, H - 12.0, 1.0)
        B.text("BAT 1S Li-ion  + left", 263, H - 10.5, 1.0)
    B.text("iron disc 12 mm centred on circle; magnet S-pole down", 60, 7.0, 1.5)
    if D.VARIANT == "module":
        B.text("ANTENNA - keep clear", 20, H - 4.5, 1.0, layer=pcbnew.B_SilkS)
    else:
        y0 = Ys + D.DEV_Y0_OFFSET
        B.text("38-pin ESP32 dev board: antenna LEFT, USB RIGHT. 3V3 = bottom-left pin, 5V = bottom-right pin", D.DEV_X0 + 2, y0 - 4.5, 1.1)
        B.text("ANTENNA", D.DEV_X0 + 4, y0 + D.DEV_ROW_SPACING / 2, 1.0)

    pcbnew.SaveBoard(out_path, B.b)
    set_page(out_path)
    return B


def route_battery_block(B, f2, Ys, H):
    """Pre-route the power paths of the optional IP5306 block with wide tracks (the autorouter would use 0.3 mm)."""
    F, Bk = pcbnew.F_Cu, pcbnew.B_Cu
    jp1, jp2, jp3 = B.pad("JP1", "1"), B.pad("JP1", "2"), B.pad("JP1", "3")
    # +5V bus <- JP1 pin 2: B.Cu 3 mm straight up into the main bus (the file-e vertical bus sits on the same x)
    B.track(jp2[0], Ys + 2.0, jp2[0], jp2[1] - 3.0, Bk, 3.0, "+5V")
    B.track(jp2[0], jp2[1] - 3.0, jp2[0], jp2[1], Bk, 1.0, "+5V")      # thin last bit between the 2.54 mm header pins
    # VUSB5: fuse -> along the bottom margin -> JP1 pin 1 -> IP5306 VIN (+ C77)
    yb = H - 2.2
    vin = B.pad("U6", "1"); c77 = B.pad("C77", "1")
    B.poly([f2, (f2[0] + 4.0, f2[1]), (f2[0] + 4.0, yb), (vin[0] - 3.0, yb), (vin[0] - 3.0, vin[1]), vin], F, 1.2, "VUSB5")
    B.track(jp1[0], yb, jp1[0], jp1[1], F, 1.2, "VUSB5")
    B.track(c77[0], c77[1], c77[0], vin[1], F, 0.8, "VUSB5")
    # LX: U6 pin 7 -> L1 pad 1
    p7 = B.pad("U6", "7"); l1 = B.pad("L1", "1"); l2 = B.pad("L1", "2")
    B.track(p7[0], p7[1], l1[0], p7[1], F, 0.8, "LX")
    # BAT: U6 pin 6 -> (below the inductor) -> L1 pad 2 -> C78 -> J5 pin 1
    p6 = B.pad("U6", "6"); c78 = B.pad("C78", "1"); j5 = B.pad("J5", "1")
    l1bb = B.fps["L1"].FindPadByNumber("1").GetBoundingBox()
    yl = mm(l1bb.GetBottom()) + 1.2
    bx = p6[0] + 1.8
    B.poly([p6, (bx, p6[1]), (bx, p6[1] + 1.0)], F, 0.6, "BAT")
    B.poly([(bx, p6[1] + 1.0), (bx, yl), (l2[0], yl), l2], F, 1.5, "BAT")
    B.poly([(l2[0], yl), (c78[0], yl), (j5[0], yl), j5], F, 1.5, "BAT")
    B.track(c78[0], c78[1], c78[0], yl, F, 1.0, "BAT")
    # VBOOST: U6 pin 8 -> C79 -> JP1 pin 3
    p8 = B.pad("U6", "8"); c79 = B.pad("C79", "1")
    yt = H - 25.5
    B.poly([p8, (p8[0] + 2.3, p8[1]), (p8[0] + 2.3, c79[1]), c79], F, 1.0, "VBOOST")
    B.poly([(p8[0] + 2.3, c79[1]), (p8[0] + 2.3, yt), (jp3[0], yt), jp3], F, 1.5, "VBOOST")
    # GND vias for the block's caps and the battery connector
    for ref, pn, dx, dy in (("C77", "2", 0, -1.6), ("C78", "2", 0, -1.6), ("C79", "2", 1.6, 0), ("J5", "2", 0, -3.0)):
        gx, gy = B.pad(ref, pn)
        B.track(gx, gy, gx + dx, gy + dy, F, 0.4, "GND"); B.via(gx + dx, gy + dy, "GND")


def write_project(path):
    pro = {
        "board": {"design_settings": {"defaults": {}, "rules": {
            "min_clearance": D.CLEARANCE, "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25,
            "min_hole_to_hole": 0.5, "min_track_width": 0.2, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3},
            "rule_severities": {"silk_over_copper": "ignore", "silk_overlap": "warning", "lib_footprint_issues": "ignore",
                                "lib_footprint_mismatch": "ignore"}},
                  "layer_presets": [], "viewports": []},
        "boards": [], "cvpcb": {"equivalence_files": []}, "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": PROJECT + ".kicad_pro", "version": 1},
        "net_settings": {
            "classes": [
                {"bus_width": 12, "clearance": D.CLEARANCE, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
                 "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default",
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                 "track_width": D.W_SIG, "via_diameter": D.VIA_D, "via_drill": D.VIA_DRILL, "wire_width": 6},
                {"bus_width": 12, "clearance": 0.25, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
                 "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Power",
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                 "track_width": 1.0, "via_diameter": 0.8, "via_drill": 0.4, "wire_width": 6}],
            "meta": {"version": 3}, "net_colors": None, "netclass_assignments": None,
            "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in ("+5V", "GND", "+3V3", "VBUS")]},
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "specctra_dsn": "", "step": "", "vrml": ""},
                   "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[ROOT_UUID, ""]], "text_variables": {}}
    json.dump(pro, open(path, "w"), indent=2)


if __name__ == "__main__":
    hw = os.path.join(os.path.dirname(__file__), "..", "hardware" + D.OUT_SUFFIX)
    os.makedirs(hw, exist_ok=True)
    out = os.path.join(hw, PROJECT + ".kicad_pcb")
    write_project(os.path.join(hw, PROJECT + ".kicad_pro"))
    B = build(out)
    print("wrote", out, "footprints:", len(B.fps), "nets:", len(B.nets),
          "tracks:", len(list(B.b.GetTracks())))
