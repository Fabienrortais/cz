# Ordering the board

Files are in `manufacturing/`:

| File | Use |
|---|---|
| `openchess-board-gerbers.zip` | Upload as the PCB (JLCPCB, PCBWay, any fab). Contains copper, mask, paste, silk, edge cuts, Excellon drill + map. |
| `openchess-board-bom-jlcpcb.csv` | JLCPCB BOM format (Comment, Designator, Footprint, LCSC Part #). |
| `openchess-board-cpl-jlcpcb.csv` | JLCPCB pick-and-place (Designator, Mid X, Mid Y, Layer, Rotation). |
| `BOM.md` | Human-readable BOM with manufacturer part numbers (for PCBWay or hand assembly). |
| `*.pdf` | Schematic and layer plots for review. |

## JLCPCB

1. Order > PCB: upload the gerber zip. Settings: 2 layers, 1.6 mm FR-4,
   1 oz copper, HASL (or ENIG), any colour, "Remove order number: specify
   location" is not needed. Confirm the detected size (340 x 374 mm).
2. Enable "PCB Assembly", Economic, top side, then upload the BOM and CPL
   CSVs.
3. In the part-matching step, fix every line whose LCSC number is empty or
   out of stock (search by the manufacturer part number in `BOM.md`):
   - Hall switch H1-H64: search "HX3144ESO" or another SOT-23 continuous-time
     unipolar Hall switch; **confirm its pin order matches design.py**
     (VCC=1, OUT=2, GND=3 by default) before ordering.
   - 74HCT595 (SOIC-16), 74AHCT1G125 (SOT-23-5), 470 uF SMD electrolytic
     8 x 10 mm, 3 A 1812 polyfuse, 6 x 6 tactile switches (SW_SPST_TL3342 /
     TS-1187A), USB-C HRO TYPE-C-31-M-12, JST B2B-XH-A.
4. Check the placement preview. KiCad and JLCPCB disagree on the zero
   rotation of some packages (SOT-23, SOIC, electrolytics): if a preview shows
   pin 1 or the polarity mark in the wrong corner, use the rotate buttons in
   the preview. Our matrix parts are all on the top side.
5. Expect a note that the board exceeds their standard panel; large boards
   are produced individually.

Rough cost (check the instant quote, prices change):

| Item | Estimate |
|---|---|
| 5 bare PCBs 340 x 374 mm, 2 layer | 60-120 USD |
| Assembly of 2 boards (setup + ~800 joints + parts: 64 LEDs, 64 Hall switches, ESP32, misc.) | 90-150 USD |
| Shipping (about 1.5-2 kg) | 30-70 USD |

Cost levers: order fewer assembled boards (JLCPCB minimum is 2), drop the
optional parts (J2, DL1/R24), or regenerate with `PITCH = 33.33` (board
286 x 320 mm, about 30 % less area).

## PCBWay

Upload the same gerber zip (choose "Gerber, KiCad" if asked). For assembly
upload `BOM.md` converted to their template (columns: Item, Designator, Qty,
Manufacturer, Mfg Part #, Description, Package) and the CPL CSV; PCBWay
sources parts from any distributor so the MPN column is what matters.

## Assembly / bring-up checklist

1. Before fitting the ESP32 side: apply 5 V to J2, check 3.3 V at C69 and the
   power LED.
2. Flash the OpenChess firmware over USB-C; open the WebUI, set the shift
   register type to PNP.
3. Run the sensor test (red square in the start menu) with one magnet; every
   square must trigger. If a whole file is dead check Q1-Q8/R1-R8; if a whole
   rank is dead check the 10k pull-up of that row and the ESP32 pin.
4. Run the LED calibration.
5. Glue the 12 mm iron discs on the top plate centred on the silkscreen
   circles, and the magnets S-pole down in the pieces (as upstream).
