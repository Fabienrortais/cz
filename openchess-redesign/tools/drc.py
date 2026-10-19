"""Fill zones, run DRC, print a summary. Usage: drc.py board.kicad_pcb [report.rpt] [--save]"""
import sys, re, collections, pcbnew

def run(path, report=None, save=False):
    board = pcbnew.LoadBoard(path)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    report = report or path.replace(".kicad_pcb", "_drc.rpt")
    pcbnew.WriteDRCReport(board, report, pcbnew.EDA_UNITS_MILLIMETRES, True)
    if save:
        pcbnew.SaveBoard(path, board)
    txt = open(report).read()
    kinds = collections.Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
    found = re.findall(r"\*\* Found (\d+) ([^*]+?) \*\*", txt)
    print("DRC:", ", ".join(f"{n} {k.strip()}" for n, k in found))
    for k, n in kinds.most_common():
        print(f"  {k}: {n}")
    return txt, found, kinds

if __name__ == "__main__":
    txt, found, kinds = run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None, "--save" in sys.argv)
    # show first few lines of each error kind
    shown = collections.Counter()
    for block in re.split(r"\n(?=\[)", txt):
        m = re.match(r"\[(\w+)\]", block)
        if m and shown[m.group(1)] < 3:
            shown[m.group(1)] += 1
            print("---", block.strip()[:400])
