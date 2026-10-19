"""Compare the netlist exported by kicad-cli from the schematic with design.py."""
import os, sys, subprocess, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(__file__))
import design as D

def sch_nets(xml_path):
    root = ET.parse(xml_path).getroot()
    nets = {}
    for net in root.iter("net"):
        name = net.get("name").lstrip("/")
        if name.startswith("unconnected-"):
            continue
        nodes = sorted((n.get("ref"), n.get("pin")) for n in net.findall("node"))
        nets[name] = nodes
    return nets

def model_nets():
    parts = D.build_parts()
    nets = {}
    for n, pins in D.all_nets(parts).items():
        if n.startswith("NC"):
            continue
        nets[n] = sorted(pins)
    return nets

if __name__ == "__main__":
    sch = sys.argv[1]; xml = sys.argv[2]
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "-o", xml, sch], check=True)
    a, b = sch_nets(xml), model_nets()
    ok = True
    for n in sorted(set(a) | set(b)):
        if a.get(n) != b.get(n):
            ok = False
            print("MISMATCH", n, "\n  sch  :", a.get(n), "\n  model:", b.get(n))
    print("nets schematic:", len(a), "model:", len(b), "->", "OK" if ok else "FAIL")
    sys.exit(0 if ok else 1)
