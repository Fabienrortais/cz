"""
OpenChess PCB redesign - single source of truth for the design.

Everything (schematic, PCB, BOM, pick-and-place) is generated from this file.
Coordinates are in millimetres; PCB origin is the top-left corner of the board,
X grows to the right, Y grows DOWN (KiCad convention).

Chess convention used everywhere:
  file  f = 0..7  -> a..h  (left to right when looking at the board from White's side)
  rank  r = 0..7  -> 1..8  (rank 1 is nearest the controller strip at the bottom)
  square index  i = r*8 + f   (a1 = 0, b1 = 1, ..., h8 = 63)
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# Board parameters (edit these and re-run the build to regenerate everything)
# ----------------------------------------------------------------------------
import os as _os
# VARIANT "module"  : ESP32-WROOM-32E soldered on the board + CH340C USB-UART + LDO (fully assembled board)
# VARIANT "nodemcu" : two 19-pin sockets for a plug-in 38-pin dev board (NodeMCU-32S, ESP32 DevKitC V4, ...)
VARIANT = _os.environ.get("OPENCHESS_VARIANT", "module")
PROJECT = "openchess-board" + ("" if VARIANT == "module" else "-" + VARIANT)
# Optional Li-ion battery block (IP5306 charger + 5 V boost, JST-PH battery, 3-pin power-select jumper).
# Set OPENCHESS_BATTERY=0 to leave it out entirely (JP1 then disappears and the fuse feeds the bus directly).
BATTERY = _os.environ.get("OPENCHESS_BATTERY", "1") != "0"
BATTERY_REFS = ("U6", "L1", "C77", "C78", "C79", "J5", "JP1", "SW3")
OUT_SUFFIX = "" if VARIANT == "module" else "-" + VARIANT

PITCH = 40.0        # square pitch in mm (upstream OpenChess uses 33.33 mm, 30 LED/m strip)
MARGIN = 10.0       # copper-free-ish margin around the 8x8 grid
STRIP_H = 42.0 if VARIANT == "module" else 56.0   # controller strip height below rank 1

# Plug-in dev board (nodemcu variant): antenna end at the left, USB end to the right.
DEV_ROW_SPACING = 22.86   # mm between the two pin rows. NodeMCU-32S: 22.86 (0.9"), ESP32-DevKitC V4: 25.4 (1.0") - MEASURE YOURS
DEV_X0 = 5.0              # x of the first (antenna-end) pin
DEV_Y0_OFFSET = 19.0      # top pin row, offset from the top of the strip
# 38-pin order (top view, antenna up, USB down): left column top->bottom, right column top->bottom
DEV_LEFT = ["+3V3", "NC_EN", "NC_VP", "NC_VN", "NC_IO34", "NC_IO35", "IO32", "IO33", "NC_IO25", "IO26", "NC_IO27",
            "IO14", "NC_IO12", "GND", "NC_IO13", "NC_SD2", "NC_SD3", "NC_CMD", "+5V"]
DEV_RIGHT = ["GND", "IO23", "IO22", "NC_TX0", "NC_RX0", "IO21", "GND", "IO19", "IO18", "NC_IO5", "IO17", "IO16",
             "IO4", "NC_IO0", "NC_IO2", "NC_IO15", "NC_SD1", "NC_SD0", "NC_CLK"]
GRID_X0 = MARGIN    # left edge of square a
GRID_Y0 = MARGIN    # top edge of rank 8
BOARD_W = 8 * PITCH + 2 * MARGIN
STRIP_Y = MARGIN + 8 * PITCH + 2.0      # top of the controller strip
BOARD_H = STRIP_Y + STRIP_H

# Matrix routing geometry (relative to each square centre)
COL_DX = -6.0        # x offset of the B.Cu column (switched 5V) trace
BUS_DX = +6.0        # x offset of the B.Cu vertical +5V bus (2 mm wide)
ROW_DY = +2.5        # y offset of the F.Cu row (sensor OUT) trace
LED_DY = +9.0        # LED centre below the square centre
DISC_DIA = 12.0      # iron disc diameter (silkscreen reference circle)
ROWBUS_X0 = 3.5      # x of the first B.Cu row-bundle trace in the left margin
ROWBUS_PITCH = 0.8

# Track widths (mm)
W_SIG = 0.3
W_COL = 0.5
W_BUS = 2.0
W_MAINBUS = 4.0
VIA_D = 0.6
VIA_DRILL = 0.3
CLEARANCE = 0.2

# ----------------------------------------------------------------------------
# Hall sensor selection.  The SOT-23 "44E"-class parts have VENDOR-SPECIFIC
# pinouts!  Set pins to match the datasheet of the exact part you order.
# ----------------------------------------------------------------------------
SENSOR = dict(
    value="HX3144ESO",                           # HUAXIN, unipolar, open-collector, 2.5-24 V, continuous-time
    lcsc="",                                     # fill in from jlcpcb.com/parts (search "HX3144ESO")
    pins={"VCC": "1", "OUT": "2", "GND": "3"},   # HX3144ESO: 1=VCC 2=OUT(OC) 3=GND  (verify!)
    # Alternative examples (CHECK datasheet before use):
    #   Diodes AH3144E-SA, Allegro A1104 (SOT-23W)...  -> different pin order
)

# ESP32 GPIO assignment == OpenChess firmware defaults (board_driver.h), so the
# pre-built firmware works unchanged.  Set "SR_INVERT_OUTPUTS" = PNP in the WebUI.
GPIO = dict(
    LED_DATA="IO32", SR_SER="IO33", SR_CLK="IO14", SR_LATCH="IO26",
    ROW=["IO4", "IO16", "IO17", "IO18", "IO19", "IO21", "IO22", "IO23"],
)

def _kicad_share(kind):
    """Locate the KiCad symbol/footprint libraries for whatever KiCad version is installed."""
    env = _os.environ.get(f"KICAD_{kind.upper()}_DIR")
    if env:
        return env
    for v in ("10", "9", "8", "7"):
        env = _os.environ.get(f"KICAD{v}_{kind.upper()}_DIR")
        if env and _os.path.isdir(env):
            return env
    sub = "footprints" if kind == "footprint" else "symbols"
    for base in ("/usr/share/kicad", "/usr/local/share/kicad",
                 "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
                 "C:/Program Files/KiCad/10.0/share/kicad", "C:/Program Files/KiCad/9.0/share/kicad",
                 "C:/Program Files/KiCad/8.0/share/kicad", "C:/Program Files/KiCad/7.0/share/kicad"):
        if _os.path.isdir(_os.path.join(base, sub)):
            return _os.path.join(base, sub)
    raise RuntimeError(f"KiCad {sub} library not found; set KICAD_{kind.upper()}_DIR")

FP_LIB = _kicad_share("footprint")
SYM_LIB = _kicad_share("symbol")


@dataclass
class Part:
    ref: str
    symbol: str                 # "Lib:Name"
    footprint: str              # "Lib:Name"
    value: str
    pins: Dict[str, str]        # pad/pin number -> net name
    x: float = 0.0
    y: float = 0.0
    rot: float = 0.0
    layer: str = "F"
    lcsc: str = ""
    mpn: str = ""
    desc: str = ""
    sch: Tuple[float, float] = (0.0, 0.0)   # schematic placement (mm)
    uuid: str = ""
    extra: dict = field(default_factory=dict)


def sq_center(f: int, r: int) -> Tuple[float, float]:
    """Centre of square (file f, rank r) on the PCB."""
    cx = GRID_X0 + PITCH * (f + 0.5)
    cy = GRID_Y0 + PITCH * (7 - r + 0.5)
    return cx, cy


def sq_name(f: int, r: int) -> str:
    return "abcdefgh"[f] + str(r + 1)


def led_chain_order() -> List[Tuple[int, int]]:
    """Serpentine order of the WS2812B chain: a1..h1, h2..a2, a3..h3, ..."""
    order = []
    for r in range(8):
        files = range(8) if r % 2 == 0 else range(7, -1, -1)
        for f in files:
            order.append((f, r))
    return order


def build_parts() -> List[Part]:
    P: List[Part] = []
    Ys = STRIP_Y

    # ---------------- 8x8 matrix: sensors, LEDs, LED decoupling caps ----------
    for r in range(8):
        for f in range(8):
            i = r * 8 + f
            cx, cy = sq_center(f, r)
            P.append(Part(
                ref=f"H{i+1}", symbol="OpenChess:HALL_SWITCH_SOT23",
                footprint="Package_TO_SOT_SMD:SOT-23", value=SENSOR["value"],
                pins={SENSOR["pins"]["VCC"]: f"COL{f}", SENSOR["pins"]["OUT"]: f"ROW{r}",
                      SENSOR["pins"]["GND"]: "GND"},
                x=cx, y=cy, rot=0, lcsc=SENSOR["lcsc"], mpn=SENSOR["value"],
                desc=f"Hall switch, square {sq_name(f, r)}", extra=dict(square=(f, r))))
    for k, (f, r) in enumerate(led_chain_order()):
        cx, cy = sq_center(f, r)
        rot = 180 if r % 2 == 0 else 0     # even ranks run left->right (DIN on the left)
        din = "LED_DATA" if k == 0 else f"LED{k}"
        dout = f"LED{k+1}" if k < 63 else "NC_LED_END"
        P.append(Part(
            ref=f"D{k+1}", symbol="LED:WS2812B",
            footprint="LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm", value="WS2812B",
            pins={"1": "+5V", "2": dout, "3": "GND", "4": din},
            x=cx, y=cy + LED_DY, rot=rot, lcsc="C2761795", mpn="WS2812B-B/T",
            desc=f"RGB LED #{k+1}, square {sq_name(f, r)}", extra=dict(square=(f, r), chain=k)))
        # decoupling cap next to the LED (position computed in gen_pcb from pad geometry)
        P.append(Part(
            ref=f"C{k+1}", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric",
            value="100nF", pins={"1": "+5V", "2": "GND"}, x=cx, y=cy + LED_DY, rot=rot,
            lcsc="C14663", mpn="CL10B104KB8NNNC", desc=f"LED decoupling, square {sq_name(f, r)}",
            extra=dict(square=(f, r), chain=k, led_cap=True)))

    # ---------------- Controller strip ---------------------------------------
    H = BOARD_H
    if VARIANT == "module":
        esp_pins = {
            "1": "GND", "2": "+3V3", "3": "EN", "4": "NC_VP", "5": "NC_VN", "6": "NC_IO34", "7": "NC_IO35",
            "8": "IO32", "9": "IO33", "10": "NC_IO25", "11": "IO26", "12": "NC_IO27", "13": "IO14",
            "14": "NC_IO12", "15": "GND", "16": "NC_IO13", "17": "NC17", "18": "NC18", "19": "NC19",
            "20": "NC20", "21": "NC21", "22": "NC22", "23": "NC_IO15", "24": "NC_IO2", "25": "IO0",
            "26": "IO4", "27": "IO16", "28": "IO17", "29": "NC_IO5", "30": "IO18", "31": "IO19",
            "32": "NC32", "33": "IO21", "34": "RXD0", "35": "TXD0", "36": "IO22", "37": "IO23",
            "38": "GND", "39": "GND",
        }
        P.append(Part(ref="U1", symbol="RF_Module:ESP32-WROOM-32E", footprint="RF_Module:ESP32-WROOM-32",
                      value="ESP32-WROOM-32E", pins=esp_pins, x=16.0, y=Ys + 24.0, rot=180,
                      lcsc="C701341", mpn="ESP32-WROOM-32E-N4", desc="ESP32 WiFi/BLE module (4 MB flash)"))
        P.append(Part(ref="C65", symbol="Device:C", footprint="Capacitor_SMD:C_0805_2012Metric", value="10uF",
                      pins={"1": "+3V3", "2": "GND"}, x=36.0, y=Ys + 18.0, rot=90, lcsc="C15850", desc="ESP32 3V3 bulk"))
        P.append(Part(ref="C66", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric", value="100nF",
                      pins={"1": "+3V3", "2": "GND"}, x=31.0, y=Ys + 30.0, rot=90, lcsc="C14663", desc="ESP32 3V3 decoupling"))
        P.append(Part(ref="R19", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="10k",
                      pins={"1": "+3V3", "2": "EN"}, x=31.0, y=Ys + 18.0, rot=90, lcsc="C25804", desc="EN pull-up"))
        P.append(Part(ref="C67", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric", value="1uF",
                      pins={"1": "EN", "2": "GND"}, x=31.0, y=Ys + 22.0, rot=90, lcsc="C15849", desc="EN reset delay"))
        P.append(Part(ref="R20", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="10k",
                      pins={"1": "+3V3", "2": "IO0"}, x=31.0, y=Ys + 26.0, rot=90, lcsc="C25804", desc="IO0 pull-up"))
        P.append(Part(ref="SW1", symbol="Switch:SW_Push", footprint="Button_Switch_SMD:SW_SPST_TL3342", value="RESET",
                      pins={"1": "EN", "2": "GND"}, x=56.0, y=H - 6.0, rot=0, lcsc="C318884", mpn="TS-1187A-B-A-B", desc="Reset button"))
        P.append(Part(ref="SW2", symbol="Switch:SW_Push", footprint="Button_Switch_SMD:SW_SPST_TL3342", value="BOOT",
                      pins={"1": "IO0", "2": "GND"}, x=46.0, y=H - 6.0, rot=0, lcsc="C318884", mpn="TS-1187A-B-A-B", desc="Boot button"))
        # 3.3 V LDO
        P.append(Part(ref="U2", symbol="Regulator_Linear:AMS1117-3.3", footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2",
                      value="AMS1117-3.3", pins={"1": "GND", "2": "+3V3", "3": "+5V"}, x=118.0, y=H - 18.0, rot=0,
                      lcsc="C6186", mpn="AMS1117-3.3", desc="3.3V 1A LDO"))
        P.append(Part(ref="C68", symbol="Device:C", footprint="Capacitor_SMD:C_0805_2012Metric", value="10uF",
                      pins={"1": "+5V", "2": "GND"}, x=112.0, y=H - 11.0, rot=0, lcsc="C15850", desc="LDO input"))
        P.append(Part(ref="C69", symbol="Device:C", footprint="Capacitor_SMD:C_0805_2012Metric", value="10uF",
                      pins={"1": "+3V3", "2": "GND"}, x=124.0, y=H - 11.0, rot=0, lcsc="C15850", desc="LDO output"))
        # USB-serial bridge + auto-reset (DevKitC circuit)
        P.append(Part(ref="U3", symbol="Interface_USB:CH340C", footprint="Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", value="CH340C",
                      pins={"1": "GND", "2": "TXD0_U", "3": "RXD0_U", "4": "CH_V3", "5": "USB_D+", "6": "USB_D-", "7": "NC_U3_7",
                            "8": "NC_U3_8", "9": "NC_U3_9", "10": "NC_U3_10", "11": "NC_U3_11", "12": "NC_U3_12",
                            "13": "DTR", "14": "RTS", "15": "NC_U3_15", "16": "+5V"},
                      x=78.0, y=H - 22.0, rot=90, lcsc="C84681", mpn="CH340C", desc="USB to UART (no crystal needed)"))
        P.append(Part(ref="C71", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric", value="100nF",
                      pins={"1": "+5V", "2": "GND"}, x=70.0, y=H - 26.0, rot=0, lcsc="C14663", desc="CH340 VCC decoupling"))
        P.append(Part(ref="C72", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric", value="100nF",
                      pins={"1": "CH_V3", "2": "GND"}, x=86.0, y=H - 26.0, rot=0, lcsc="C14663", desc="CH340 V3 decoupling"))
        P.append(Part(ref="Q9", symbol="Transistor_BJT:MMBT3904", footprint="Package_TO_SOT_SMD:SOT-23", value="S8050",
                      pins={"1": "DTR_R", "2": "RTS", "3": "EN"}, x=66.0, y=H - 16.0, rot=0, lcsc="C2146", mpn="S8050", desc="Auto-reset"))
        P.append(Part(ref="Q10", symbol="Transistor_BJT:MMBT3904", footprint="Package_TO_SOT_SMD:SOT-23", value="S8050",
                      pins={"1": "RTS_R", "2": "DTR", "3": "IO0"}, x=70.0, y=H - 16.0, rot=0, lcsc="C2146", mpn="S8050", desc="Auto-boot"))
        P.append(Part(ref="R21", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="10k",
                      pins={"1": "DTR", "2": "DTR_R"}, x=66.0, y=H - 12.0, rot=0, lcsc="C25804", desc="Auto-reset base"))
        P.append(Part(ref="R22", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="10k",
                      pins={"1": "RTS", "2": "RTS_R"}, x=70.0, y=H - 12.0, rot=0, lcsc="C25804", desc="Auto-boot base"))
        usb_dp, usb_dm = "USB_D+", "USB_D-"
        row_pullup_y = (Ys + 20.0, Ys + 23.0)
    else:
        # Plug-in dev board: two 1x19 sockets. Top row = dev board's right column, bottom row = left column
        # (board rotated antenna-left, USB-right, component side up).
        y_top = Ys + DEV_Y0_OFFSET
        P.append(Part(ref="J3", symbol="Connector_Generic:Conn_01x19", footprint="Connector_PinSocket_2.54mm:PinSocket_1x19_P2.54mm_Vertical",
                      value="DEV_TOP", pins={str(i + 1): n for i, n in enumerate(DEV_RIGHT)}, x=DEV_X0, y=y_top, rot=0,
                      lcsc="", mpn="1x19 female header 2.54 mm", desc="Dev board socket, top row (GND,23,22,TX,RX,21,GND,19,18,5,17,16,4,0,2,15,SD1,SD0,CLK)"))
        P.append(Part(ref="J4", symbol="Connector_Generic:Conn_01x19", footprint="Connector_PinSocket_2.54mm:PinSocket_1x19_P2.54mm_Vertical",
                      value="DEV_BOTTOM", pins={str(i + 1): n for i, n in enumerate(DEV_LEFT)}, x=DEV_X0, y=y_top + DEV_ROW_SPACING, rot=0,
                      lcsc="", mpn="1x19 female header 2.54 mm", desc="Dev board socket, bottom row (3V3,EN,VP,VN,34,35,32,33,25,26,27,14,12,GND,13,SD2,SD3,CMD,5V)"))
        usb_dp, usb_dm = "NC_USB_D+", "NC_USB_D-"
        row_pullup_y = (Ys + 24.0, Ys + 27.0)

    # Row pull-ups (10k to 3V3)
    for r in range(8):
        P.append(Part(ref=f"R{9+r}", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="10k",
                      pins={"1": "+3V3", "2": f"ROW{r}"}, x=40.0 + 2.2 * (r % 4), y=row_pullup_y[r // 4], rot=90,
                      lcsc="C25804", desc=f"ROW{r} pull-up"))

    # LED data level shifter 3.3V -> 5V
    P.append(Part(ref="U5", symbol="74xGxx:74AHCT1G125", footprint="Package_TO_SOT_SMD:SOT-23-5", value="74AHCT1G125",
                  pins={"1": "GND", "2": "IO32", "3": "GND", "4": "LED_DATA_5V", "5": "+5V"},
                  x=42.0, y=Ys + 9.5, rot=0, lcsc="", mpn="SN74AHCT1G125DBVR", desc="WS2812B data level shifter"))
    P.append(Part(ref="C74", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric", value="100nF",
                  pins={"1": "+5V", "2": "GND"}, x=46.5, y=Ys + 9.5, rot=90, lcsc="C14663", desc="U5 decoupling"))
    P.append(Part(ref="R23", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="330",
                  pins={"1": "LED_DATA_5V", "2": "LED_DATA"}, x=38.0, y=Ys + 5.0, rot=0, lcsc="C23138", desc="LED data series"))

    # Power input: USB-C (5V/3A) + optional external 5V, polyfuse, bulk caps
    P.append(Part(ref="J1", symbol="Connector:USB_C_Receptacle_USB2.0_16P",
                  footprint="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", value="USB-C",
                  pins={"A1": "GND", "A4": "VBUS", "A5": "CC1", "A6": usb_dp, "A7": usb_dm, "A8": "NC_SBU1",
                        "A9": "VBUS", "A12": "GND", "B1": "GND", "B4": "VBUS", "B5": "CC2", "B6": usb_dp,
                        "B7": usb_dm, "B8": "NC_SBU2", "B9": "VBUS", "B12": "GND", "S1": "GND"},
                  x=78.0, y=H - 3.9, rot=0, lcsc="C165948", mpn="TYPE-C-31-M-12", desc="USB-C receptacle 16P"))
    P.append(Part(ref="R17", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="5.1k",
                  pins={"1": "CC1", "2": "GND"}, x=70.0, y=H - 8.0, rot=0, lcsc="C23186", desc="USB CC1 pull-down"))
    P.append(Part(ref="R18", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="5.1k",
                  pins={"1": "CC2", "2": "GND"}, x=87.0, y=H - 8.0, rot=0, lcsc="C23186", desc="USB CC2 pull-down"))
    P.append(Part(ref="F1", symbol="Device:Polyfuse", footprint="Fuse:Fuse_1812_4532Metric", value="3A PTC",
                  pins={"1": "VBUS", "2": "VUSB5" if BATTERY else "+5V"}, x=99.0, y=H - 11.0, rot=90, lcsc="",
                  mpn="MF-MSMF300-2 / BSMD1812-300", desc="Resettable fuse 3A hold (USB path)"))
    if BATTERY:
        # IP5306: 5 V in -> charges a 1S Li-ion; boosts the battery to 5 V / 2.4 A on VOUT. JP1 selects the bus source.
        P.append(Part(ref="U6", symbol="OpenChess:IP5306", footprint="Package_SO:HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm_ThermalVias",
                      value="IP5306", pins={"1": "VUSB5", "2": "NC_LED1", "3": "NC_LED2", "4": "NC_LED3", "5": "KEY", "6": "BAT",
                                            "7": "LX", "8": "VBOOST", "9": "GND"},
                      x=232.0, y=H - 16.0, rot=0, lcsc="C181692", mpn="IP5306", desc="Li-ion charger (2.1 A) + 5 V boost (2.4 A), power-bank IC"))
        P.append(Part(ref="L1", symbol="Device:L", footprint="Inductor_SMD:L_Taiyo-Yuden_NR-60xx", value="1uH 4A",
                      pins={"1": "LX", "2": "BAT"}, x=242.0, y=H - 16.6, rot=0, lcsc="", mpn="NR6028T1R0N / CD63 1uH >=4A",
                      desc="Boost inductor 1 uH, >= 4 A sat, 6x6 mm"))
        P.append(Part(ref="C77", symbol="Device:C", footprint="Capacitor_SMD:C_0805_2012Metric", value="22uF",
                      pins={"1": "VUSB5", "2": "GND"}, x=226.3, y=H - 21.5, rot=90, lcsc="C45783", desc="IP5306 VIN cap"))
        P.append(Part(ref="C78", symbol="Device:C", footprint="Capacitor_SMD:C_0805_2012Metric", value="22uF",
                      pins={"1": "BAT", "2": "GND"}, x=252.0, y=H - 15.5, rot=90, lcsc="C45783", desc="IP5306 BAT cap"))
        P.append(Part(ref="C79", symbol="Device:C", footprint="Capacitor_SMD:C_0805_2012Metric", value="22uF",
                      pins={"1": "VBOOST", "2": "GND"}, x=242.0, y=H - 23.0, rot=0, lcsc="C45783", desc="IP5306 VOUT cap"))
        P.append(Part(ref="J5", symbol="Connector_Generic:Conn_01x02", footprint="Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical",
                      value="BATTERY", pins={"1": "BAT", "2": "GND"}, x=262.0, y=H - 5.0, rot=0, lcsc="C131337", mpn="B2B-PH-K-S",
                      desc="1S Li-ion / LiPo battery, JST-PH 2.0 mm (+ on pin 1, check your pack!)"))
        P.append(Part(ref="JP1", symbol="Connector_Generic:Conn_01x03", footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
                      value="PWR SEL", pins={"1": "VUSB5", "2": "+5V", "3": "VBOOST"}, x=193.46, y=H - 8.5, rot=90, lcsc="C2337",
                      mpn="1x3 header + jumper", desc="Power select: 1-2 = USB direct (no battery), 2-3 = battery/boost (IP5306)"))
        P.append(Part(ref="SW3", symbol="Switch:SW_Push", footprint="Button_Switch_SMD:SW_SPST_TL3342", value="PWR",
                      pins={"1": "KEY", "2": "GND"}, x=276.0, y=H - 6.0, rot=0, lcsc="C318884", mpn="TS-1187A-B-A-B",
                      desc="IP5306 KEY: short press = boost on, long press = off"))
    P.append(Part(ref="J2", symbol="Connector_Generic:Conn_01x02", footprint="Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical",
                  value="5V IN", pins={"1": "+5V", "2": "GND"}, x=118.0, y=H - 5.0, rot=0, lcsc="C158012",
                  mpn="B2B-XH-A", desc="External 5V/4A input (optional, bypasses fuse)"))
    P.append(Part(ref="C75", symbol="Device:C_Polarized", footprint="Capacitor_SMD:CP_Elec_8x10", value="470uF 10V",
                  pins={"1": "+5V", "2": "GND"}, x=104.0, y=H - 20.0, rot=90, lcsc="", mpn="470uF/10V SMD 8x10",
                  desc="5V bulk capacitor"))
    P.append(Part(ref="C76", symbol="Device:C_Polarized", footprint="Capacitor_SMD:CP_Elec_8x10", value="470uF 10V",
                  pins={"1": "+5V", "2": "GND"}, x=94.0, y=H - 20.0, rot=90, lcsc="", mpn="470uF/10V SMD 8x10",
                  desc="5V bulk capacitor"))
    P.append(Part(ref="DL1", symbol="Device:LED", footprint="LED_SMD:LED_0603_1608Metric", value="PWR",
                  pins={"1": "GND", "2": "PWRLED"}, x=136.0, y=H - 6.0, rot=0, lcsc="C72043", desc="Power LED (green)"))
    P.append(Part(ref="R24", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="1k",
                  pins={"1": "+3V3", "2": "PWRLED"}, x=136.0, y=H - 10.0, rot=0, lcsc="C21190", desc="Power LED series"))

    # Column drivers: 74HCT595 + 8x (1k + PNP high-side switch), one PNP under each column
    P.append(Part(ref="U4", symbol="74xx:74HCT595", footprint="Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", value="74HCT595",
                  pins={"1": "SRQ1", "2": "SRQ2", "3": "SRQ3", "4": "SRQ4", "5": "SRQ5", "6": "SRQ6", "7": "SRQ7",
                        "8": "GND", "9": "NC_U4_9", "10": "+5V", "11": "IO14", "12": "IO26", "13": "GND",
                        "14": "IO33", "15": "SRQ0", "16": "+5V"},
                  x=170.0, y=H - 18.0, rot=90, lcsc="", mpn="SN74HCT595DR / 74HCT595D", desc="Column shift register (HCT = 3.3V-input compatible)"))
    P.append(Part(ref="C73", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric", value="100nF",
                  pins={"1": "+5V", "2": "GND"}, x=170.0, y=H - 10.0, rot=0, lcsc="C14663", desc="U4 decoupling"))
    for f in range(8):
        cx, cy = sq_center(f, 0)
        qx = cx + COL_DX
        P.append(Part(ref=f"Q{f+1}", symbol="Transistor_BJT:MMBT3906", footprint="Package_TO_SOT_SMD:SOT-23", value="S8550",
                      pins={"1": f"SRQ{f}_R", "2": "+5V", "3": f"COL{f}"}, x=qx, y=Ys + 7.0, rot=90,
                      lcsc="C2150", mpn="S8550", desc=f"Column {'abcdefgh'[f]} high-side PNP switch", extra=dict(col=f)))
        P.append(Part(ref=f"R{f+1}", symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="1k",
                      pins={"1": f"SRQ{f}", "2": f"SRQ{f}_R"}, x=qx - 0.95, y=Ys + 10.5, rot=90,
                      lcsc="C21190", desc=f"Column {'abcdefgh'[f]} base resistor", extra=dict(col=f)))

    # Mounting holes (M3)
    holes = [(5, 5), (BOARD_W / 2, 5), (BOARD_W - 5, 5), (BOARD_W - 5, STRIP_Y / 2),
             (BOARD_W - 5, BOARD_H - 5), (BOARD_W / 2 + 40, BOARD_H - 5), (BOARD_W / 2 - 40, BOARD_H - 5)]
    for k, (hx, hy) in enumerate(holes):
        P.append(Part(ref=f"MH{k+1}", symbol="Mechanical:MountingHole", footprint="MountingHole:MountingHole_3.2mm_M3",
                      value="M3", pins={}, x=hx, y=hy, desc="Mounting hole"))
    return P


# Net aliases: schematic-level nets that are electrically the same net.
# The firmware/USB wiring: ESP32 TXD0 -> CH340 RXD, CH340 TXD -> ESP32 RXD0.
NET_ALIASES = {"TXD0_U": "RXD0", "RXD0_U": "TXD0"}
NET_ALIASES.update({gpio: f"ROW{r}" for r, gpio in enumerate(GPIO["ROW"])})


def canonical_net(n: str) -> str:
    return NET_ALIASES.get(n, n)


def all_nets(parts: List[Part]) -> Dict[str, List[Tuple[str, str]]]:
    nets: Dict[str, List[Tuple[str, str]]] = {}
    for p in parts:
        for pin, net in p.pins.items():
            nets.setdefault(canonical_net(net), []).append((p.ref, pin))
    return nets


POWER_NETS = {"+5V", "+3V3", "GND", "VBUS"}

if __name__ == "__main__":
    parts = build_parts()
    nets = all_nets(parts)
    print(f"board {BOARD_W} x {BOARD_H} mm, strip at y={STRIP_Y}")
    print(f"{len(parts)} parts, {len(nets)} nets")
    for n, pins in sorted(nets.items()):
        if len(pins) == 1 and not n.startswith("NC"):
            print("WARNING single-pin net", n, pins)
