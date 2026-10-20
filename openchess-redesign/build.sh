#!/usr/bin/env bash
# Regenerate schematic, PCB, routing, DRC and manufacturing files.
# usage: ./build.sh /path/to/freerouting.jar [--no-route]
set -euo pipefail
cd "$(dirname "$0")"
# find a python that can `import pcbnew` (Linux distro python, or the python bundled with KiCad on macOS/Windows)
PY=${PYTHON:-}
if [[ -z "$PY" ]]; then
  for c in /usr/bin/python3 python3 \
      /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      "/c/Program Files/KiCad/10.0/bin/python.exe" "/c/Program Files/KiCad/9.0/bin/python.exe" "/c/Program Files/KiCad/8.0/bin/python.exe"; do
    if "$c" -c "import pcbnew" >/dev/null 2>&1; then PY=$c; break; fi
  done
fi
[[ -n "$PY" ]] || { echo "no python with the pcbnew module found; set PYTHON=..."; exit 1; }
echo "using $PY ($($PY -c 'import pcbnew; print(pcbnew.GetBuildVersion())'))"
JAR=${1:-}
for V in ${VARIANTS:-module nodemcu}; do
  export OPENCHESS_VARIANT=$V
  SUF=""; [[ "$V" != "module" ]] && SUF="-$V"
  PCB=hardware$SUF/openchess-board$SUF.kicad_pcb
  echo "=== variant $V ==="
  mkdir -p build/$V
  $PY tools/gen_sch.py
  $PY tools/verify_netlist.py hardware$SUF/openchess-board$SUF.kicad_sch build/$V/netlist.xml
  $PY tools/gen_pcb.py
  if [[ -n "$JAR" && "${2:-}" != "--no-route" ]]; then
    $PY tools/route.py "$PCB" "$JAR" --passes ${PASSES:-12}
  fi
  $PY tools/gnd_repair.py "$PCB"
  $PY tools/drc.py "$PCB" hardware$SUF/openchess-board${SUF}_drc.rpt --save
  $PY tools/export.py
done
