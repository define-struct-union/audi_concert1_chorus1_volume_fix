#!/usr/bin/env bash
# Plots gerbers + drill files for the v5 board and zips them for JLCPCB.
# Needs KiCad 8 or newer (the PCB file is format 20240108; KiCad 7 cannot open it).
#   Ubuntu/Debian: sudo add-apt-repository ppa:kicad/kicad-8.0-releases && sudo apt install kicad
#   Windows/macOS: https://www.kicad.org/download/  (kicad-cli ships with it)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PCB="${1:-$HERE/../audi_concert1_chorus1_volume_fix/audi_concert1_chorus1_volume_fix.kicad_pcb}"
OUT="$HERE/gerbers"
rm -rf "$OUT"          # stale plots from an earlier run must not end up in the zip
mkdir -p "$OUT"

# Default origin on purpose: the generated cpl_jlcpcb.csv uses the same one.
kicad-cli pcb export gerbers \
  --layers F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,Edge.Cuts \
  --no-protel-ext -o "$OUT/" "$PCB"
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map -o "$OUT/" "$PCB"

rm -f "$OUT"/*drl_map.pdf     # JLC does not want them
cd "$OUT" && rm -f ../gerbers.zip && zip -j ../gerbers.zip ./* >/dev/null
echo "OK -> $HERE/gerbers.zip"
