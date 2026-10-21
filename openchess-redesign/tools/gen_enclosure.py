"""Write enc_params.scad from design.py and render the enclosure STLs with OpenSCAD.
Usage: gen_enclosure.py [--no-render]   (OPENCHESS_VARIANT selects the variant)"""
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design as D

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ENC = os.path.join(ROOT, "enclosure")
OUT = os.path.join(ENC, "stl" + D.OUT_SUFFIX)
PARTS = ["top_q00", "top_q10", "top_q01", "top_q11", "tray_00", "tray_10", "tray_01", "tray_11", "cover_0", "cover_1"]

def params():
    parts = {p.ref: p for p in D.build_parts()}
    mh = [(p.x, p.y) for r, p in parts.items() if r.startswith("MH")]
    lines = [
        f'VARIANT = "{D.VARIANT}";', f"W = {D.BOARD_W}; H = {D.BOARD_H}; STRIP_Y = {D.STRIP_Y};",
        f"PITCH = {D.PITCH}; GRID_X0 = {D.GRID_X0}; GRID_Y0 = {D.GRID_Y0}; LED_DY = {D.LED_DY};",
        "MH = [" + ", ".join(f"[{x}, {y}]" for x, y in mh) + "];",
        f"J1_X = {parts['J1'].x}; J2_X = {parts['J2'].x + 1.25}; J2_Y = {parts['J2'].y};",
        f"DL1_X = {parts['DL1'].x}; DL1_Y = {parts['DL1'].y};",
        f"BATTERY = {'true' if D.BATTERY else 'false'};",
        (f"J5_X = {parts['J5'].x + 1.0}; J5_Y = {parts['J5'].y}; SW3_X = {parts['SW3'].x}; SW3_Y = {parts['SW3'].y}; JP1_X = {parts['JP1'].x + 2.54}; JP1_Y = {parts['JP1'].y};"
         if D.BATTERY else "J5_X = 0; J5_Y = 0; SW3_X = 0; SW3_Y = 0; JP1_X = 0; JP1_Y = 0;"),
    ]
    if D.VARIANT == "module":
        lines += [f"SW1_X = {parts['SW1'].x}; SW1_Y = {parts['SW1'].y}; SW2_X = {parts['SW2'].x}; SW2_Y = {parts['SW2'].y};",
                  "ANT_X0 = 4; ANT_X1 = 28;", "COVER_INNER_H = 12;",
                  "DEV_USB_X0 = 0; DEV_USB_X1 = 0; DEV_USB_Y0 = 0; DEV_USB_Y1 = 0;"]
    else:
        y0 = D.STRIP_Y + D.DEV_Y0_OFFSET
        lines += ["SW1_X = 0; SW1_Y = 0; SW2_X = 0; SW2_Y = 0;", "ANT_X0 = 0; ANT_X1 = 0;", "COVER_INNER_H = 16;",
                  f"DEV_USB_X0 = {D.DEV_X0 + 44}; DEV_USB_X1 = {D.DEV_X0 + 78}; DEV_USB_Y0 = {y0 - 4}; DEV_USB_Y1 = {y0 + D.DEV_ROW_SPACING + 4};"]
    return "\n".join(lines) + "\n"

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(ENC, "enc_params.scad"), "w").write(params())
    open(os.path.join(OUT, "enc_params.scad"), "w").write(params())   # keep a copy next to the STLs
    print("params written for", D.VARIANT)
    if "--no-render" in sys.argv:
        sys.exit(0)
    procs = []
    for part in PARTS:
        out = os.path.join(OUT, f"{D.PROJECT}-{part}.stl")
        cmd = ["openscad", "-o", out, "-D", f'part="{part}"', os.path.join(ENC, "enclosure.scad")]
        procs.append((part, subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)))
        while len([p for _, p in procs if p.poll() is None]) >= 4:
            import time; time.sleep(2)
    for part, p in procs:
        _, err = p.communicate()
        print(part, "ok" if p.returncode == 0 else "FAILED\n" + err[-800:])
