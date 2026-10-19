"""Import a Specctra session (.ses) written by Freerouting into a pcbnew BOARD.

KiCad's own importer is not usable headless in KiCad 7, so this reads the
network_out section (wires + vias) and adds them to the board.  Only new
(non-fixed) routes are listed in the session, so existing tracks are kept.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from sexp import parse, find, find_all

LAYERS = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}

def import_ses(board, ses_path):
    root = parse(open(ses_path, encoding="utf-8").read())[0]
    routes = find(root, "routes")
    res = find(routes, "resolution")
    unit, per = res[1], float(res[2])                   # e.g. um 10 -> 10 units per um
    scale = {"um": 1000.0, "mm": 1e6, "mil": 25400.0, "inch": 25.4e6}[unit] / per   # units -> nm
    def P(v): return int(round(float(v) * scale))
    net_out = find(routes, "network_out")
    n_tracks = n_vias = 0
    for net in find_all(net_out, "net"):
        name = str(net[1])
        code = board.GetNetcodeFromNetname(name)
        if code <= 0:
            print("WARNING: unknown net in session:", name); continue
        for w in find_all(net, "wire"):
            path = find(w, "path")
            layer = LAYERS[str(path[1])]; width = P(path[2])
            pts = [(P(path[i]), -P(path[i + 1])) for i in range(3, len(path), 2)]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                if (x1, y1) == (x2, y2):
                    continue
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(x1, y1)); t.SetEnd(pcbnew.VECTOR2I(x2, y2))
                t.SetWidth(width); t.SetLayer(layer); t.SetNetCode(code)
                board.Add(t); n_tracks += 1
        for v in find_all(net, "via"):
            m = re.search(r"_(\d+):(\d+)_um", str(v[1]))
            size, drill = int(m.group(1)) * 1000, int(m.group(2)) * 1000
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(P(v[2]), -P(v[3])))
            via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetWidth(size); via.SetDrill(drill)
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNetCode(code)
            board.Add(via); n_vias += 1
    return n_tracks, n_vias

if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1])
    print(import_ses(b, sys.argv[2]))
    pcbnew.SaveBoard(sys.argv[1], b)
