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
        if bb.GetLeft() - r < px < bb.GetRight() + r and bb.GetTop() - r < py < bb.GetBottom() + r:
            return False
    for z in board.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowVias() and z.Outline().Contains(pcbnew.VECTOR2I(px, py)):
            return False
    return 1.0 < x < D.BOARD_W - 1.0 and 1.0 < y < D.BOARD_H - 1.0

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
            for rad in (1.4, 1.9, 2.5, 3.2):
                placed = False
                for k in range(8):
                    a = math.radians(45 * k)
                    vx, vy = x + rad * math.cos(a), y + rad * math.sin(a)
                    # the stub track from the pad to the via must be free as well (sampled away from the pad itself)
                    stub_ok = all(free_spot(board, x + (vx - x) * f, y + (vy - y) * f, keep=0.15)
                                  for f in (0.55, 0.75) if rad * f > 1.0)
                    if free_spot(board, vx, vy) and stub_ok:
                        tr = pcbnew.PCB_TRACK(board)
                        tr.SetStart(pcbnew.VECTOR2I(MM(x), MM(y))); tr.SetEnd(pcbnew.VECTOR2I(MM(vx), MM(vy)))
                        tr.SetWidth(MM(0.3)); tr.SetLayer(pcbnew.F_Cu); tr.SetNetCode(gnd); board.Add(tr)
                        v = pcbnew.PCB_VIA(board)
                        v.SetPosition(pcbnew.VECTOR2I(MM(vx), MM(vy))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                        v.SetDrill(MM(D.VIA_DRILL)); v.SetWidth(MM(D.VIA_D)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                        v.SetNetCode(gnd); board.Add(v); added += 1; placed = True
                        break
                if placed:
                    break
        print("  added vias:", added)
        if not added:
            break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    set_page(path)
    os.remove(report)

if __name__ == "__main__":
    main()
