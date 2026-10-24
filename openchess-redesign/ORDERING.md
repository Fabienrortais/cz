# Ordering the board

Files are in `manufacturing/`:

| File | Use |
|---|---|
| `openchess-board-gerbers.zip` | Upload as the PCB (JLCPCB, PCBWay, any fab). Contains copper, mask, paste, silk, edge cuts, Excellon drill + map. |
| `openchess-board-bom-jlcpcb.csv` | JLCPCB BOM format (Comment, Designator, Footprint, LCSC Part #). `-nobattery` versions omit the IP5306 block. |
| `openchess-board-cpl-jlcpcb.csv` | JLCPCB pick-and-place (Designator, Mid X, Mid Y, Layer, Rotation). |
| `BOM.md` | Human-readable BOM with manufacturer part numbers (for PCBWay or hand assembly). |
| `*.pdf` | Schematic and layer plots for review. |

## Pre-order checklist (status 2026-10-24)

| Item | Status | What is left for you |
|---|---|---|
| Hall switch H1-H64 | HUAXIN HX3144ESO, JLCPCB/LCSC **C558880** (unipolar, open-collector, 2.5-24 V, operate 6-10 mT, release 4-8 mT: more sensitive than the A3144). Pin order used on the board: 1 = VCC, 2 = OUT, 3 = GND. | Open the datasheet PDF linked on the C558880 page and confirm "Pin 1 VCC, Pin 2 Output, Pin 3 GND" (one mirror shows a garbled figure with 2/3 swapped). If it is 1 VCC / 2 GND / 3 OUT instead, change `SENSOR["pins"]` in `tools/design.py` and rebuild; a wrong order does not damage anything but no square would be detected. |
| Column PNP Q1-Q8 | S8550 2TY, **C2147** (extended). The earlier C2150 was wrong: C2146 and C2150 are both NPN. | nothing |
| Auto-reset NPN Q9/Q10 (module variant) | S8050 J3Y, **C2146** (basic) | nothing |
| 74HCT595 U4 | Nexperia 74HCT595D,112, **C70468** (extended). Do not substitute 74HC595 (C5947): its 3.5 V input threshold is marginal with the ESP32. | nothing |
| 74AHCT1G125 U5 | TI SN74AHCT1G125DBVR, **C7484** (extended; C7468 is the non-T part, avoid). | check stock |
| ESP32-WROOM-32E U1 (module variant) | **C701341** (N4, 4 MB) confirmed | nothing |
| CH340C, AMS1117-3.3, IP5306 | C84681, C6186, C181692 confirmed | nothing |
| WS2812B D1-D64 | Worldsemi WS2812B-B/T **C2761795** confirmed (MSL 5a: JLCPCB may add a baking note) | nothing |
| Connectors | USB-C TYPE-C-31-M-12 C165948, JST-XH C158012, JST-PH C131337, tactile TS-1187A C318884 confirmed | tactile switch stock fluctuates; any 6x6 mm SMD tactile with the TL3342 footprint works |
| 0603/0805 passives | 10k C25804, 1k C21190, 5.1k C23186, 100nF C14663, 1uF C15849, 10uF C15850, 22uF C45783, green LED C72043 confirmed | **330R C23138 unverified**: check it is 330 ohm (C23140 is 33 ohm) |
| Polyfuse F1 | BHFUSE BSMD1812-300-16V **C883162** (3 A hold, 1812) or JDTfuse ASMD1812-300 C135366 | check which one JLCPCB stocks |
| Bulk caps C75/C76 | 470 uF, D8 x L10 SMD. Candidate RVT1C471M0810 (16 V) **C3341**, not confirmed on JLCPCB | search "470uF 8x10" in JLCPCB parts, any 470 uF >= 6.3 V in D8xL10.2 |
| Inductor L1 (battery block) | Sunlord SWPA6045S1R0NT **C96955** or CENKER CKCS6045-1uH/N C354627 (1 uH, 5 A, 6x6 mm). Board footprint = Taiyo Yuden NR-60xx (pads 1.6 x 5.7 mm, 4.7 mm apart). | compare the land pattern in the Sunlord/CENKER datasheet with those pads; if their pads are wider, pick NR6045T1R0N (Taiyo Yuden) instead |
| JP1 header | any 2.54 mm 1x3 male header + jumper cap (no LCSC number set) | let JLCPCB pick one, or hand-solder it |
| NodeMCU row spacing (nodemcu variant) | design uses 22.86 mm | measure centre-to-centre of the two pin rows on your board; if 25.4 mm set `DEV_ROW_SPACING = 25.4` and rebuild |
| Placement rotations | CPL follows KiCad's zero-rotation convention | in the JLCPCB preview rotate SOT-23 / SOIC / electrolytics if pin 1 or polarity looks wrong |

## Battery block: fit it or not

The IP5306 block is optional on both variants and the board is fully usable
without it:

- **USB-C / J2 only (no battery):** order with
  `*-bom-jlcpcb-nobattery.csv` + `*-cpl-jlcpcb-nobattery.csv` (U6, L1,
  C77-C79, J5, SW3 left off; JP1 kept), then put the jumper cap on **JP1 1-2**
  (or solder a wire between those two pins). The fuse output then feeds the
  5 V bus directly, exactly like a board without the block.
- **With battery:** order the full BOM/CPL, plug a 1S Li-ion/LiPo with a
  JST-PH plug into J5 (+ on pin 1, check your pack's polarity), jumper
  **JP1 2-3**. USB-C charges the cell and powers the board through the IP5306;
  SW3 short press = on, long press = off. Do not feed J2 while on 2-3.
- You can also assemble the block now and still run on USB only: with JP1 on
  1-2 the IP5306 only charges whatever is on J5 and never powers the bus.

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
