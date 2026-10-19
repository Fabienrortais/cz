#!/usr/bin/env bash
# Regenerate schematic, PCB, routing, DRC and manufacturing files.
# usage: ./build.sh /path/to/freerouting.jar [--no-route]
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-/usr/bin/python3}      # must be the python that can `import pcbnew`
JAR=${1:-}
$PY tools/gen_sch.py
$PY tools/verify_netlist.py hardware/openchess-board.kicad_sch build/netlist.xml
$PY tools/gen_pcb.py
if [[ -n "$JAR" && "${2:-}" != "--no-route" ]]; then
  $PY tools/route.py hardware/openchess-board.kicad_pcb "$JAR" --passes 30
fi
$PY tools/drc.py hardware/openchess-board.kicad_pcb hardware/openchess-board_drc.rpt --save
$PY tools/export.py
