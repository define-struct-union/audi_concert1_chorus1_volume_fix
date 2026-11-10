#!/usr/bin/env python3
"""Generate JLCPCB-style BOM + CPL (pick-and-place) from the v5 KiCad PCB.

Usage: python3 -I make_fab.py <path-to.kicad_pcb> <outdir>

Only parts that the assembly house should place are exported:
 - values marked "(NP)" in the schematic are dropped (not populated)
 - U1 (PLCC-52 socket), CON1/CON3/CON4 (headers), JP1/JP2 (solder jumpers)
   are dropped: hand-fitted after delivery.
Coordinates: absolute page coordinates, Y negated (KiCad .pos convention),
so they match gerbers plotted with kicad-cli default settings.
"""
import re, sys, csv, os
from collections import defaultdict

pcb_path, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
src = open(pcb_path, encoding='utf8', errors='replace').read()

HAND_FIT = {'U1', 'CON1', 'CON2', 'CON3', 'CON4', 'JP1', 'JP2'}
# C8 is marked (NP) in the schematic and is the only bottom-side part; leaving it
# out keeps the order single-sided (JLCPCB Economic PCBA).
NOT_FITTED = {'C8'}
# The PCB file still carries a stale value for R2 (1k); the schematic says 3k3.
# R2 is only the LED series resistor, so either works - we follow the schematic.
VALUE_FIX = {'R2': '3k3'}

def footprint_blocks(s):
    i = 0
    while True:
        j = s.find('\n\t(footprint ', i)
        if j < 0:
            return
        k, depth, m = j + 2, 0, j + 2
        while m < len(s):
            if s[m] == '(':
                depth += 1
            elif s[m] == ')':
                depth -= 1
                if depth == 0:
                    break
            m += 1
        yield s[k:m + 1]
        i = m

parts = []
for blk in footprint_blocks(src):
    name = re.match(r'\(footprint "([^"]+)"', blk)
    at = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk)
    ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
    val = re.search(r'\(property "Value" "([^"]*)"', blk)
    layer = re.search(r'\n\t\t\(layer "([^"]+)"\)', blk)
    if not (name and at and ref):
        continue
    parts.append({
        'ref': ref.group(1),
        'val': (val.group(1) if val else '').strip(),
        'fp': name.group(1).split(':')[-1],
        'x': float(at.group(1)),
        'y': float(at.group(2)),
        'rot': float(at.group(3) or 0),
        'side': 'Top' if (layer.group(1) if layer else 'F.Cu') == 'F.Cu' else 'Bottom',
    })

def sort_key(p):
    return (re.sub(r'\d', '', p['ref']), int(re.sub(r'\D', '', p['ref']) or 0))

parts.sort(key=sort_key)
for p in parts:
    p['val'] = VALUE_FIX.get(p['ref'], p['val'])
    if re.fullmatch(r'\d+K', p['val']):          # "1K" and "1k" are the same part
        p['val'] = p['val'].lower()
placed = [p for p in parts
          if '(NP)' not in p['val']
          and p['ref'] not in HAND_FIT
          and p['ref'] not in NOT_FITTED]
dropped = [p for p in parts if p not in placed]

# --- CPL ---
with open(os.path.join(outdir, 'cpl_jlcpcb.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for p in placed:
        w.writerow([p['ref'], f"{p['x']:.4f}", f"{-p['y']:.4f}", p['side'], f"{p['rot']:.1f}"])

# --- BOM (grouped by value+footprint) ---
groups = defaultdict(list)
for p in placed:
    groups[(p['val'], p['fp'])].append(p['ref'])

# Comment strings JLC's matcher understands, plus a known-good LCSC part for each
# line (checked against JLC stock). "base" = JLCPCB Basic part, no feeder fee.
MPN = {
    ('STM32F103C8Tx', 'LQFP-48_7x7mm_Pitch0.5mm'): 'STM32F103C8T6',
    ('AP1117-33', 'AB2_SOT223'): 'AMS1117-3.3',          # AP1117-33 is EOL at JLC, same SOT-223 pinout
    ('8MHz', 'Crystal_SMD_5032-4pin_5.0x3.2mm'): '8MHz crystal SMD5032-4P 20pF',
    ('red', 'LED-1206'): 'LED red 1206',
}
LCSC = {
    'STM32F103C8T6': 'C8734',                    # ST original, LQFP-48
    'AMS1117-3.3': 'C6186',                      # base part
    '8MHz crystal SMD5032-4P 20pF': 'C3003245',  # 5XAA08000202TF80E3, 20pF, min order 5
    'LED red 1206': 'C965822',                   # XL-3216SURC, top emitting
    '1k': 'C17513', '3k3': 'C26010', '47k': 'C17713', '10k': 'C17414', '1M': 'C17514',
    '22p': 'C1804', '100n': 'C49678',
}

def pkg(fp):
    if '0805' in fp: return '0805'
    if '1206' in fp: return '1206'
    if 'SOT223' in fp or 'SOT-223' in fp: return 'SOT-223'
    if 'LQFP-48' in fp: return 'LQFP-48 7x7 0.5mm'
    if '5032' in fp: return 'SMD 5032 (5.0x3.2mm, 4 pad)'
    return fp

rows = []
for (val, fp), refs in groups.items():
    refs.sort(key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r) or 0)))
    rows.append({
        'Comment': MPN.get((val, fp), val),
        'Designator': ','.join(refs),
        'Footprint': pkg(fp),
        'Quantity': len(refs),
        'LCSC Part #': LCSC.get(MPN.get((val, fp), val), ''),
    })
rows.sort(key=lambda r: (-r['Quantity'], r['Comment']))
with open(os.path.join(outdir, 'bom_jlcpcb.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['Comment', 'Designator', 'Footprint', 'Quantity', 'LCSC Part #'])
    w.writeheader()
    w.writerows(rows)

xs, ys = [], []
for m in re.finditer(r'\((?:gr_line|gr_rect|gr_arc|gr_poly)\b(.*?)\n\t\)', src, re.S):
    if '"Edge.Cuts"' not in m.group(1):
        continue
    for a, b in re.findall(r'\((?:start|end|mid|xy) ([-\d.]+) ([-\d.]+)\)', m.group(1)):
        xs.append(float(a)); ys.append(float(b))

with open(os.path.join(outdir, 'bom_readable.txt'), 'w') as f:
    f.write(f"Audi Concert1/Chorus1 volume fix - HW v5\n")
    f.write(f"Board outline: {max(xs)-min(xs):.1f} x {max(ys)-min(ys):.1f} mm, 2 layers, assembly top side only\n\n")
    f.write(f"=== MACHINE-PLACED ({sum(r['Quantity'] for r in rows)} parts, {len(rows)} lines) ===\n")
    for r in rows:
        f.write(f"{r['Quantity']:>3}x  {r['Comment']:<34} {r['Footprint']:<28} {r['Designator']}\n")
    f.write("\n=== YOU FIT BY HAND ===\n")
    f.write("  1x  PLCC-52 socket, SMD, 1.27mm        U1   (clamps onto radio's 68HC05)\n")
    f.write("  1x  pin header 1x2, 2.54mm             CON1 (1=SCL_TO_TDA, 2=SDA_TO_TDA)\n")
    f.write("  1x  pin header 1x3, 2.54mm             CON3 (1=DATA, 2=STATUS, 3=CLOCK to panel)\n")
    f.write("  1x  pin header 1x6, 2.54mm             CON4 (1=GND 2=SWDCLK 3=SWDIO 4=3V3 5=RX 6=TX)\n")
    f.write("      solder blob                        JP1/JP2 boot jumpers -> bridge to GND side\n")
    f.write("\n=== LEAVE EMPTY (not populated in v5) ===\n")
    for p in dropped:
        if '(NP)' in p['val'] or p['ref'] in NOT_FITTED:
            f.write(f"  {p['ref']:<6} {p['val']}\n")

print(f"placed parts: {sum(r['Quantity'] for r in rows)} in {len(rows)} BOM lines")
print(f"board: {max(xs)-min(xs):.2f} x {max(ys)-min(ys):.2f} mm")
print("wrote:", ', '.join(sorted(os.listdir(outdir))))
