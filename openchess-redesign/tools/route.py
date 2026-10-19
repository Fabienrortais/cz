"""Autoroute the controller strip with Freerouting, keeping the scripted matrix routing fixed.

Usage: route.py board.kicad_pcb freerouting.jar [--passes N]
"""
import os, sys, subprocess, shutil, re, time
sys.path.insert(0, os.path.dirname(__file__))
import pcbnew
import design as D

MM = pcbnew.FromMM

def add_grid_keepout(board):
    """Rule area over the matrix so the autorouter only works in the strip.
    A notch lets it reach the DIN pad of the first LED (a1)."""
    Ys, W = D.STRIP_Y, D.BOARD_W
    cx, cy = D.sq_center(0, 0)
    pts = [(0, 0), (W, 0), (W, Ys - 3.0), (cx + 4.5, Ys - 3.0), (cx + 4.5, cy + 4.0), (cx - 10.0, cy + 4.0),
           (cx - 10.0, Ys - 3.0), (0, Ys - 3.0)]
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetZoneName("TEMP_autoroute_keepout")
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(False)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET(); add = ls.addLayer if hasattr(ls, "addLayer") else ls.AddLayer; add(pcbnew.F_Cu); add(pcbnew.B_Cu); z.SetLayerSet(ls)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts:
        ol.Append(MM(x), MM(y))
    board.Add(z)
    return z

def main():
    path = sys.argv[1]; jar = sys.argv[2]
    passes = "30"
    if "--passes" in sys.argv:
        passes = sys.argv[sys.argv.index("--passes") + 1]
    work = os.path.join(os.path.dirname(os.path.abspath(path)), "..", "build", D.VARIANT)
    os.makedirs(work, exist_ok=True)
    dsn = os.path.join(work, D.PROJECT + ".dsn")
    ses = os.path.join(work, D.PROJECT + ".ses")

    board = pcbnew.LoadBoard(path)
    n_fixed = len(list(board.GetTracks()))
    ko = add_grid_keepout(board)
    # give the autorouter a small clearance margin over the DRC rule (Freerouting rounds)
    ds = board.GetDesignSettings()
    try:
        nc = ds.m_NetSettings.m_DefaultNetClass
    except AttributeError:
        nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(D.CLEARANCE + 0.06))
    ok = pcbnew.ExportSpecctraDSN(board, dsn)
    nc.SetClearance(MM(D.CLEARANCE))
    print("DSN export:", ok, dsn, "fixed tracks/vias:", n_fixed)
    txt = open(dsn).read()
    print("DSN classes:", re.findall(r"\(class (\S+)", txt)[:5], "| fixed wires:", txt.count("(type fix)"), "| protect:", txt.count("(type protect)"))

    if "--import-only" not in sys.argv:
        if os.path.exists(ses):
            os.remove(ses)
        run_freerouting(jar, dsn, ses, passes, work)
    import_session(board, ses, ko, path)

def run_freerouting(jar, dsn, ses, passes, work):
    cmd = ["xvfb-run", "-a", "java", "-jar", jar, "-de", dsn, "-do", ses, "-mp", passes, "-oit", "2", "-mt", "1"]
    t0 = time.time()
    log = open(os.path.join(work, "freerouting.log"), "w")
    r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=3000)
    log.close()
    print(f"freerouting exit {r.returncode} in {time.time()-t0:.0f}s; ses exists: {os.path.exists(ses)}")
    if not os.path.exists(ses):
        print(open(os.path.join(work, "freerouting.log")).read()[-3000:])
        sys.exit(1)

def cleanup_dangling(board):
    """Delete unlocked track segments with a free end (autorouter leftovers). Repeats until stable."""
    removed = 0
    while True:
        tracks = [t for t in board.GetTracks()]
        pts = {}
        for t in tracks:
            if t.GetClass() == "PCB_VIA":
                for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                    pts.setdefault((t.GetPosition().x, t.GetPosition().y, l), []).append(t)
            else:
                for p in (t.GetStart(), t.GetEnd()):
                    pts.setdefault((p.x, p.y, t.GetLayer()), []).append(t)
        pads = [(pad, pad.GetLayerSet()) for fp in board.GetFootprints() for pad in fp.Pads()]
        segs = [t for t in tracks if t.GetClass() == "PCB_TRACK"]
        def on_segment(p, s):
            a, b = s.GetStart(), s.GetEnd()
            bb = s.GetBoundingBox()
            if not (bb.GetLeft() - 1000 <= p.x <= bb.GetRight() + 1000 and bb.GetTop() - 1000 <= p.y <= bb.GetBottom() + 1000):
                return False
            ax, ay, bx, by = a.x, a.y, b.x, b.y
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            if L2 == 0:
                return False
            u = max(0.0, min(1.0, ((p.x - ax) * dx + (p.y - ay) * dy) / L2))
            qx, qy = ax + u * dx, ay + u * dy
            return ((p.x - qx) ** 2 + (p.y - qy) ** 2) ** 0.5 <= s.GetWidth() / 2 + 1000
        def anchored(p, layer, me):
            if len([x for x in pts.get((p.x, p.y, layer), []) if x is not me]) > 0:
                return True
            for pad, ls in pads:
                if ls.Contains(layer) and pad.HitTest(p):
                    return True
            for s in segs:                       # T-junction onto another segment of the same layer
                if s is not me and s.GetLayer() == layer and on_segment(p, s):
                    return True
            return False
        victims = [t for t in tracks if t.GetClass() == "PCB_TRACK" and not t.IsLocked()
                   and (not anchored(t.GetStart(), t.GetLayer(), t) or not anchored(t.GetEnd(), t.GetLayer(), t))]
        if not victims:
            return removed
        for t in victims:
            board.Remove(t); removed += 1

def import_session(board, ses, ko, path):
    # import the session into the board that still has the keepout, then drop the keepout
    from ses_import import import_ses     # KiCad's importer is GUI-only in KiCad 7; use our own
    n_t, n_v = import_ses(board, ses)
    print("SES import: added", n_t, "tracks and", n_v, "vias; tracks/vias now:", len(list(board.GetTracks())))
    board.Remove(ko)
    print("removed dangling tails:", cleanup_dangling(board))
    # Re-lock nothing; keep everything as routed. Fill zones and save.
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    from gen_pcb import set_page
    set_page(path)
    print("saved", path)

if __name__ == "__main__":
    main()
