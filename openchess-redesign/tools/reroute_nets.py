"""Lock all existing routing, delete the given nets' tracks/vias (so Freerouting re-routes only them).
Usage: reroute_nets.py board.kicad_pcb NET [NET...]"""
import sys, pcbnew
path = sys.argv[1]; nets = set(sys.argv[2:])
b = pcbnew.LoadBoard(path)
removed = 0
for t in list(b.GetTracks()):
    if t.GetNetname() in nets:
        b.Remove(t); removed += 1
    else:
        t.SetLocked(True)
pcbnew.SaveBoard(path, b)
print("removed", removed, "items of", nets, "- everything else locked")
