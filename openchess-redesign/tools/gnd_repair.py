"""Connect GND pour islands: for every GND pad/via that DRC reports as unconnected, add a via next to it
(so the island on one layer reaches the pour on the other layer). Iterates fill -> DRC -> add vias.
Usage: gnd_repair.py board.kicad_pcb"""
import os, re, sys, math, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
import design as D
from gen_pcb import set_page

MM = pcbnew.FromMM

def unconnected_gnd(report):
    txt = open(report).read()
    out = []
    for block in re.split(r"\n(?=\[)", txt):
        if not block.startswith("[unconnected_items]"):
            continue
        for m in re.finditer(r"@\(([-\d.]+) mm, ([-\d.]+) mm\): (PTH pad|Pad|Via) [^\n]*\[GND\]", block):
            out.append((float(m.group(1)), float(m.group(2))))
    return out

def free_spot(board, x, y, keep=0.3):
    px, py = MM(x), MM(y)
    r = MM(D.VIA_D / 2 + keep)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            if bb.GetLeft() - r < px < bb.GetRight() + r and bb.GetTop() - r < py < bb.GetBottom() + r:
                return False
    for t in board.GetTracks():
        bb = t.GetBoundingBox()
        if not (bb.GetLeft() - r < px < bb.GetRight() + r and bb.GetTop() - r < py < bb.GetBottom() + r):
            continue
        if t.GetClass() == "PCB_VIA":
            return False
        # exact point-to-segment distance (bounding boxes of diagonal tracks are far too pessimistic)
        a, b_ = t.GetStart(), t.GetEnd()
        dx, dy = b_.x - a.x, b_.y - a.y
        L2 = dx * dx + dy * dy
        u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - a.x) * dx + (py - a.y) * dy) / L2))
        qx, qy = a.x + u * dx, a.y + u * dy
        if ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5 < t.GetWidth() / 2 + MM(D.VIA_D / 2 + keep):
            return False
    for z in board.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowVias() and z.Outline().Contains(pcbnew.VECTOR2I(px, py)):
            return False
    return 1.0 < x < D.BOARD_W - 1.0 and 1.0 < y < D.BOARD_H - 1.0

def stub_via(board, gnd, x, y):
    """Add a short F.Cu stub from (x, y) to a new GND via at a free spot nearby. Returns 1 if placed."""
    for rad in (1.4, 1.9, 2.5, 3.2, 4.0):
        for k in range(8):
            a = math.radians(45 * k)
            vx, vy = x + rad * math.cos(a), y + rad * math.sin(a)
            stub_ok = all(free_spot(board, x + (vx - x) * f, y + (vy - y) * f, keep=0.15)
                          for f in (0.4, 0.55, 0.75) if rad * f > 1.0)
            if free_spot(board, vx, vy) and stub_ok:
                tr = pcbnew.PCB_TRACK(board)
                tr.SetStart(pcbnew.VECTOR2I(MM(x), MM(y))); tr.SetEnd(pcbnew.VECTOR2I(MM(vx), MM(vy)))
                tr.SetWidth(MM(0.25)); tr.SetLayer(pcbnew.F_Cu); tr.SetNetCode(gnd); board.Add(tr)
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(MM(vx), MM(vy))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetDrill(MM(D.VIA_DRILL)); v.SetWidth(MM(D.VIA_D)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNetCode(gnd); board.Add(v)
                print(f"  stub via for pad ({x:.2f}, {y:.2f}) at ({vx:.2f}, {vy:.2f})")
                return 1
    return 0


def main():
    path = sys.argv[1]
    report = path.replace(".kicad_pcb", "_gndrepair.rpt")
    board = pcbnew.LoadBoard(path)
    gnd = board.GetNetcodeFromNetname("GND")
    tried = set()
    for rnd in range(5):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.WriteDRCReport(board, report, pcbnew.EDA_UNITS_MILLIMETRES, True)
        items = [p for p in unconnected_gnd(report) if p not in tried]
        print(f"round {rnd}: {len(items)} unconnected GND pads/vias")
        if not items:
            break
        added = 0
        for (x, y) in items:
            tried.add((x, y))
            added += stub_via(board, gnd, x, y)
        print("  added vias:", added)
        if not added:
            break
    # orphan stitching vias: a GND via whose pour pieces on BOTH layers contain no pad sits on an island
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    gnd_pads = [pad.GetPosition() for fp in board.GetFootprints() for pad in fp.Pads() if pad.GetNetCode() == gnd]
    pieces = {}      # layer -> list of (polyset, index, has_pad)
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() != gnd:
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(layer):
                continue
            ps = z.GetFilledPolysList(layer)
            for i in range(ps.OutlineCount()):
                has_pad = any(ps.Contains(pp, i) for pp in gnd_pads)
                pieces.setdefault(layer, []).append((ps, i, has_pad))
    def piece_has_pad(layer, pos):
        for ps, i, has_pad in pieces.get(layer, []):
            if ps.Contains(pos, i):
                return has_pad
        return None          # not in any pour piece
    removed = 0
    anchored = set()      # vias that a track ends on (pre-placed pad stubs) are never orphans
    for tr in board.GetTracks():
        if tr.GetClass() == "PCB_TRACK":
            anchored.add((tr.GetStart().x, tr.GetStart().y)); anchored.add((tr.GetEnd().x, tr.GetEnd().y))
    for v in list(board.GetTracks()):
        if v.GetClass() == "PCB_VIA" and v.GetNetCode() == gnd and (v.GetPosition().x, v.GetPosition().y) not in anchored:
            f, b_ = piece_has_pad(pcbnew.F_Cu, v.GetPosition()), piece_has_pad(pcbnew.B_Cu, v.GetPosition())
            if not f and not b_:
                board.Remove(v); removed += 1
    print("removed orphan GND vias:", removed)
    bridge_islands(board, gnd)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    set_page(path)
    os.remove(report)


def bridge_islands(board, gnd, max_rounds=12):
    """If the GND copper forms several clusters (pour pieces linked by vias/THT pads), add vias where a piece
    of one cluster on F.Cu overlaps a piece of another cluster on B.Cu, until only one cluster holds pads."""
    for rnd in range(max_rounds):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pieces = []          # (layer, polyset, idx)
        for z in board.Zones():
            if z.GetIsRuleArea() or z.GetNetCode() != gnd:
                continue
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if z.IsOnLayer(layer):
                    ps = z.GetFilledPolysList(layer)
                    for i in range(ps.OutlineCount()):
                        pieces.append((layer, ps, i))
        def find_piece(layer, pos):
            for k, (l, ps, i) in enumerate(pieces):
                if l == layer and ps.Contains(pos, i):
                    return k
            return None
        parent = list(range(len(pieces)))
        def root(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        def union(a, b):
            if a is None or b is None: return
            ra, rb = root(a), root(b)
            if ra != rb: parent[ra] = rb
        haspad = [False] * len(pieces)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetCode() != gnd: continue
                ks = [find_piece(l, pad.GetPosition()) for l in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.IsOnLayer(l)]
                ks = [k for k in ks if k is not None]
                for k in ks: haspad[k] = True
                for k in ks[1:]: union(ks[0], k)
        for v in board.GetTracks():
            if v.GetClass() == "PCB_VIA" and v.GetNetCode() == gnd:
                union(find_piece(pcbnew.F_Cu, v.GetPosition()), find_piece(pcbnew.B_Cu, v.GetPosition()))
        comps = {}
        for k in range(len(pieces)):
            if haspad[k]: comps.setdefault(root(k), []).append(k)
        if len(comps) <= 1:
            print(f"bridge_islands: single GND cluster after {rnd} round(s)")
            return
        order = sorted(comps.values(), key=len, reverse=True)
        main, others = order[0], order[1:]
        print(f"bridge_islands round {rnd}: {len(comps)} clusters, sizes {[len(c) for c in order]}")
        added = 0
        for comp in others:
            placed = False
            for k in comp:
                layer, ps, i = pieces[k]
                other = pcbnew.B_Cu if layer == pcbnew.F_Cu else pcbnew.F_Cu
                bb = ps.Outline(i).BBox()
                x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
                x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
                step = 1.0
                y = y0 + 0.5
                while y < y1 and not placed:
                    x = x0 + 0.5
                    while x < x1:
                        pos = pcbnew.VECTOR2I(MM(x), MM(y))
                        if ps.Contains(pos, i):
                            km = find_piece(other, pos)
                            if km is not None and root(km) == root(main[0]) and free_spot(board, x, y, keep=0.35):
                                v = pcbnew.PCB_VIA(board)
                                v.SetPosition(pos); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                                v.SetDrill(MM(D.VIA_DRILL)); v.SetWidth(MM(D.VIA_D)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                                v.SetNetCode(gnd); board.Add(v); added += 1; placed = True
                                print(f"  bridge via at ({x:.1f}, {y:.1f})")
                                break
                        x += step
                    y += step
                if placed: break
        if not added:
            # fall back: give the pads of the minor clusters their own stub + via
            for comp in others:
                for fp in board.GetFootprints():
                    for pad in fp.Pads():
                        if pad.GetNetCode() != gnd: continue
                        ks = [find_piece(l, pad.GetPosition()) for l in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.IsOnLayer(l)]
                        if any(k in comp for k in ks if k is not None):
                            print("  island pad", fp.GetReference(), pad.GetNumber())
                            added += stub_via(board, gnd, pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y))
            if not added:
                print("bridge_islands: no bridging spot found"); return

if __name__ == "__main__":
    main()
