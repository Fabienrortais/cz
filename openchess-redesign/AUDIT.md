# OpenChess audit (joojoooo/OpenChess, as of October 2026)

Scope: the upstream project at https://joojoooo.github.io/OpenChess/ and
https://github.com/joojoooo/OpenChess (firmware, build guide, electronics).
This audit answers "can we redesign it completely as our own PCB?" (yes, see
`README.md` in this folder) and lists what is good, what is weak, and what we kept.

## 1. What OpenChess is

- A DIY smart chess board: 64 hall-effect sensors detect magnets glued into
  the pieces, 64 WS2812B LEDs show legal moves, an ESP32 runs the game logic,
  Stockfish (via an online API) and Lichess over WiFi, plus a web UI.
- It is a fork of the Concept-Bytes board. The author replaced the original
  PCB with a 3D-printed "plastic PCB" that is hand-wired.
- Licence: MIT for the open parts. The Bluetooth board emulation (ChessConnect
  / Chessup / Yizhi BLE profiles) is **closed-source** and only shipped in the
  pre-built firmware binaries, behind a paid unlock. This matters for a
  hardware redesign: if you want that feature you must stay electrically
  compatible with the pre-built firmware (same scanning scheme, configurable
  GPIOs only).

## 2. Firmware (src/)

| Area | Finding |
|---|---|
| Toolchain | PlatformIO, Arduino framework, targets `esp32dev` and `esp32-s3-devkitc-1`. Libraries: NeoPixelBus, ArduinoJson, ESPAsyncWebServer/AsyncTCP, NimBLE. Web assets minified and stored on LittleFS. |
| Board driver (`board_driver.*`) | Bit-banged 74HC595 (SER/SRCLK/RCLK with 10 us delays), one column powered at a time, 100 us settle, then 8 row GPIOs read with `digitalRead()`; LOW = piece present. 125 ms debounce, 40 ms between scans. `srInvertOutputs` flag selects PNP (active-low) or NPN/direct drive. |
| GPIO defaults | LED data IO32; SR SER IO33, SRCLK IO14, RCLK IO26; rows IO4,16,17,18,19,21,22,23. All changeable at runtime from the WebUI and stored in NVS, so a new PCB does **not** need a firmware fork as long as it uses the same 74HC595 + 8 row-input scheme. |
| Calibration | LED order and row/column wiring are learned at first boot (serial-guided calibration). Any physical LED order / wiring order works. |
| Robustness | The driver prints a warning that a 74HC595 output cannot power 8 sensors; the WebUI warns to configure pins before wiring. Good. Sensor reads are polled, no interrupts, so timing is not critical. |
| Risk for our design | The scan assumes **continuous-time** hall switches that are valid ~100 us after power is applied. Micro-power "sampled" omnipolar switches (DRV5032, AH1806, SL1603...) wake up far too slowly (ms to tens of ms) and would read as empty squares. We therefore keep an A3144/44E-class continuous-time switch. |

## 3. Electronics as built upstream

| Item | Upstream | Assessment |
|---|---|---|
| Sensor board | 3D-printed frame, 64 TO-92 A3144, bare wire buses hand-soldered (roughly 200 joints), tape for insulation | The single biggest cost in time and the main source of failures (shorts, cold joints). A real PCB removes all of it. |
| LEDs | WS2812B strip (30 LED/m, 33.3 mm pitch) cut into 8 pieces and re-wired | Works, but 5 V/GND/data re-soldered 7 times; strip adhesive fails over time (author adds spacers). |
| Column drive | 74HC595 outputs directly feeding 8 sensors (original design) | Over the 35 mA/pin and 70 mA/package limit. Author now recommends PNP transistors (we use them). |
| Level shifting | None in the author's build; "4-channel level shifter" listed as recommended | 3.3 V data into 5 V WS2812B is below the 0.7*VDD VIH spec; 3.3 V into a 5 V 74HC595 is also marginal (VIH 3.5 V). Works by luck. We use 74HCT595 (TTL thresholds) and a 74AHCT1G125 for the LED data. |
| Hall switch | A3144 (unipolar, Bop ~ 35 mT typ) | Needs strong magnets with correct polarity plus iron discs under every square to spread the field. Cheap and continuous-time, which is why it works with this firmware. Kept (SMD variant). |
| Row pull-ups | "10-100k" to 3.3 V | 10k is right; 100k makes the lines slow/noisy over long wires. We use 10k. |
| Power | 5 V from the ESP32 dev board's USB, extra USB-C socket wired in | 64 WS2812B at full white draw up to 3.8 A; no bulk capacitance, no fuse, thin wires. We add a polyfuse, 2 x 470 uF, a 4 mm bus and an optional 5 V/4 A input. |
| Controller | Perfboard with ESP32 dev board, 74HC595, resistors | Fine for a prototype. We integrate ESP32-WROOM-32E, CH340C USB-UART with auto-reset, and 3.3 V LDO on the main board. |
| Mechanical | Board must fit a 8-12 mm thick PCB sandwich under the printed top | Our board is 1.6 mm; the top plate (printed or laser-cut) only needs 12 mm disc pockets and LED windows. |

## 4. Verdict

Can it be redesigned completely? Yes, and it is worth doing: all of the
pain is in the hand wiring, and the electrical weaknesses (shift-register
overload, missing level shifting, no power distribution) are easy to fix on a
PCB while staying 100 % compatible with the upstream firmware, including the
pre-built binaries with BLE emulation.

What we deliberately did **not** change:

- The scanning architecture (74HC595 column power switching + 8 open-collector
  row lines). Alternatives such as 8 x 74HC165 input registers or omnipolar
  sampled sensors would need a firmware fork and would lose the closed-source
  BLE feature.
- The magnet + iron disc approach. Omnipolar continuous-time switches with
  lower Bop exist, but their availability at LCSC for assembly is poor and the
  pinouts vary. The footprint is a plain SOT-23 so a drop-in with the same
  pinout can be substituted later.

## 5. Open points to check before ordering

1. The exact hall-switch part and its SOT-23 pin order (vendor specific!). The
   generator takes the pin map as a parameter; see `README.md`.
2. LCSC part numbers in the BOM are from memory and marked "verify"; the
   session that produced these files had no access to lcsc.com/jlcpcb.com.
3. JLCPCB component rotation offsets (check their placement preview).
4. The board is 340 x 374 mm; confirm the instant quote and shipping weight.
