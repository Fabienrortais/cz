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
    work = os.path.join(os.path.dirname(os.path.abspath(path)), "..", "build")
    os.makedirs(work, exist_ok=True)
    dsn = os.path.join(work, "openchess-board.dsn")
    ses = os.path.join(work, "openchess-board.ses")

    board = pcbnew.LoadBoard(path)
    n_fixed = len(list(board.GetTracks()))
    ko = add_grid_keepout(board)
    ok = pcbnew.ExportSpecctraDSN(board, dsn)
    print("DSN export:", ok, dsn, "fixed tracks/vias:", n_fixed)
    txt = open(dsn).read()
    print("DSN classes:", re.findall(r"\(class (\S+)", txt)[:5], "| fixed wires:", txt.count("(type fix)"), "| protect:", txt.count("(type protect)"))

    if os.path.exists(ses):
        os.remove(ses)
    cmd = ["xvfb-run", "-a", "java", "-jar", jar, "-de", dsn, "-do", ses, "-mp", passes, "-oit", "2", "-mt", "1"]
    t0 = time.time()
    log = open(os.path.join(work, "freerouting.log"), "w")
    r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=3000)
    log.close()
    print(f"freerouting exit {r.returncode} in {time.time()-t0:.0f}s; ses exists: {os.path.exists(ses)}")
    if not os.path.exists(ses):
        print(open(os.path.join(work, "freerouting.log")).read()[-3000:])
        sys.exit(1)

    # import the session into the board that still has the keepout, then drop the keepout
    ok = pcbnew.ImportSpecctraSES(board, ses)
    print("SES import:", ok, "tracks/vias now:", len(list(board.GetTracks())))
    board.Remove(ko)
    # Re-lock nothing; keep everything as routed. Fill zones and save.
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    from gen_pcb import set_page
    set_page(path)
    print("saved", path)

if __name__ == "__main__":
    main()
