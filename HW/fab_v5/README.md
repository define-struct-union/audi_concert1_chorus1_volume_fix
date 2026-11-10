# HW v5 — fabrication files and build guide

Everything needed to order and build the v5 board.
Board: 33.0 × 27.2 mm, 2 layers, components on one side.

```
gerbers.zip       11 files, ready to upload (generated with KiCad 8.0.9)
gerbers/          same files, unzipped
bom_jlcpcb.csv    what the machine solders (23 parts, 11 lines)
cpl_jlcpcb.csv    where each part goes (pick & place)
bom_readable.txt  same thing for humans + what you fit by hand
preview_top.pdf   top view: copper + silkscreen + part outlines
SHOPPING.md       what to buy in Germany
make_fab.py       regenerates the BOM/CPL CSVs and bom_readable.txt
make_gerbers.sh   regenerates gerbers/ and gerbers.zip (needs KiCad 8+)
```

The gerbers in `../audi_concert1_chorus1_volume_fix/gerbers/` are from 2018 and belong to an
**older board revision** — do not use them.

## Step 1 — order
See [SHOPPING.md](SHOPPING.md). JLCPCB: PCB qty 5, assembly ON, Top side, 2 assembled, Economic PCBA.
Upload `gerbers.zip`, `bom_jlcpcb.csv` and `cpl_jlcpcb.csv`.

The `LCSC Part #` column is pre-filled (see [part choices](#part-choices-in-bom_jlcpcbcsv)). Check that
each line in JLC's BOM matcher shows the right package (0805 / 1206 / SOT-223 / LQFP-48 / 5032).

Aisler (EU, ships from DE/NL) also accepts the native KiCad file directly:
`../audi_concert1_chorus1_volume_fix/audi_concert1_chorus1_volume_fix.kicad_pcb`.

## Step 2 — what you solder yourself
| Ref | Part | Note |
|-----|------|------|
| U1 | PLCC-52 socket, SMD, 1.27 mm | clamps onto the radio's 68HC05 — only 10 of its 52 pins carry signals |
| CON1 | 1×2 header | pin1 = SCL_TO_TDA, pin2 = SDA_TO_TDA |
| CON3 | 1×3 header | 1 = DATA, 2 = STATUS, 3 = CLOCK (front panel) |
| CON4 | 1×6 header | 1 GND · 2 SWDCLK · 3 SWDIO · 4 3V3 · 5 RX · 6 TX |
| JP1/JP2 | solder blob | BOOT0 / BOOT1 — bridge to the GND side |

## Step 3 — flash
From the repository root:
```bash
st-flash write SW/bins/audi_volume_fix_stm32_HWv5_v2.0.0.bin 0x08000000
```
ST-Link to CON4: GND→1, SWCLK→2, SWDIO→3, 3V3→4. Firmware v2.0.0 is **HWv5 only**.

## Step 4 — install
Wiki: https://github.com/tomaskovacik/audi_concert1_chorus1_volume_fix/wiki/Installation

Open radio (Torx T8), desolder the two marked resistors, run two wires to the SDA (lower pad) and
SCL (upper pad) holes — **these cannot be swapped** — press the module onto the main MCU, cut the
inner plastic for clearance, power up, red LED must light.

## Regenerating the files
```bash
HW/fab_v5/make_gerbers.sh
python3 -I HW/fab_v5/make_fab.py HW/audi_concert1_chorus1_volume_fix/audi_concert1_chorus1_volume_fix.kicad_pcb HW/fab_v5
```

## Notes / decisions baked into the generated files
- The board outline (Edge.Cuts) stroke in the PCB file was 1 mm and is now 0.05 mm, so the outline
  is drawn as a thin line for the board house.
- `(NP)` parts from the schematic are excluded: C2, C3, R12–R17, R19, R22, R24, U4, Y1, CON2.
- **C8** (10 µF tantalum, 3V3 bulk) is excluded too: the schematic marks it NP and it is the only
  bottom-side part — dropping it keeps the order single-sided and cheap. Hand-fit later if wanted.
- **R2**: the PCB file says 1k, the schematic says 3k3. It is only the LED series resistor,
  so the schematic value is used. Either works; the LED is just dimmer with 3k3.
- Coordinates in `cpl_jlcpcb.csv` use absolute page coordinates with Y negated (KiCad .pos
  convention), matching gerbers plotted by `make_gerbers.sh` with default origin settings.
  Check JLC's online preview once — parts must land inside the board outline.
- GALA (speed-dependent volume) is optional and needs an extra resistor populated. The v5
  schematic note says GALA = PB4; the firmware measures on PB5, which `SW/README.md` describes as
  tied with PB4. Verify on your board before wiring VSS.

## Part choices in bom_jlcpcb.csv
LCSC codes are pre-filled and were checked against JLC stock when the BOM was made.

| Line | LCSC | Note |
|------|------|------|
| 1k / 3k3 / 10k / 47k / 1M 0805 | C17513 / C26010 / C17414 / C17713 / C17514 | all **Basic** parts, no feeder fee |
| 22p / 100n 0805 | C1804 / C49678 | **Basic** |
| AMS1117-3.3 (U2) | C6186 | **Basic**. The schematic says AP1117-33, which JLC no longer stocks; AMS1117-3.3 has the same SOT-223 pinout (1 GND, 2 Vout, 3 Vin, tab Vout) |
| STM32F103C8T6 (U3) | C8734 | ST original, extended part |
| 8 MHz crystal (Y2) | C3003245 | SMD5032-**4P**, 20 pF load, min order 5 pcs, extended part |
| LED red 1206 (D1) | C965822 | top emitting (avoid the "反贴" reverse-mount ones), extended part |

Three extended parts (STM32, crystal, LED) → about $3 each in one-off feeder setup. There is no Basic
alternative for any of them. Everything else is Basic and free to load.

**Y2 must be a 4-pad crystal, not an oscillator.** JLC also lists `C70542` as 8 MHz SMD5032-4P, but
that part is a CMOS oscillator with a Vcc pin — wrong for this circuit, which drives the STM32's
OSC_IN/OSC_OUT with 22 pF caps.
