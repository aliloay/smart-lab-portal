# Door node (MASTER_LAB01) enclosure - fit-test release 2026-10-20

Source of truth: `tools/cad/door_enclosure/params.json` (every number, with its source and confidence) +
`Build.cs` (SOLIDWORKS 2025 generator, `build.ps1 [all|coupon|body|panel|plate|assembly]`). Research:
`reports/Door enclosure component dimensions.md` (notes in `research_notes/Door enclosure component dimensions/`).
Drawings: `out/DoorEnclosure_Drawings.pdf` (generated from the same params by `drawings.py`).

**Verdict: READY FOR THE FIT-TEST PRINT - not yet for the final box.** Every opening comes from a datasheet or
the matching board variant, but several of them have not been checked against the parts the owner actually
has (see 4). The fit coupon checks all of them in one print (about 97 cm³). Print the box only after it passes.

## 1. What is in the box (owner, 2026-10-20)
Front: 1.8" ST7735 TFT, PN532 V3 (red, Ekostra), R307 fingerprint (Most), green + red 5 mm LED, active buzzer.
Inside: ESP32 30-pin on 2 mini breadboards (USB to the left wall), XL4016 buck with display, 1-channel 12 V relay
module, 470 µF 25 V, a driver breadboard (BC557 + resistors, LED / buzzer transistor), 2 lever connectors
(12 V, GND). Outside: the 12 V solenoid lock (on the door - cable only), MC-38 door contact (cable only), 12 V
supply cable. **No speaker / PAM8403** (removed - the tablet page plays the sounds). No PCB. Mains never enters
this box (12 V only).

## 2. Parts to print
| Part | Size (mm) | Material / orientation | Notes |
|---|---|---|---|
| FitCoupon | 180 x 150 x 4 (+12 cradle) | same as the panel, front DOWN | print FIRST |
| Body | 170 x 210 x 110, wall 3 (was 90 until 2026-10-20: deepened for wire room) | PETG (or PLA indoors), back DOWN, no supports | 4 corner columns with M3 inserts; keyholes; 4 cable entries; USB opening; vents |
| FrontPanel | 170 x 210 x 4 (+12 behind) | front DOWN on a smooth / textured sheet, no supports | engraved labels; mounts for TFT, PN532, R307, LEDs, buzzer |
| ElectronicsPlate | 142 x 156 x 4 | flat | M3 / tie slots everywhere, engraved placement labels |

Print settings (FDM, 0.4 mm nozzle): 0.2 mm layers, 4 walls (1.6 mm), 5 top/bottom layers, 25 % gyroid,
no supports needed (all overhangs are 90° holes < 17 mm or face-down features), brim for the body only if the
bed is not PEI. PLA 205-215 °C or PETG 235-245 °C. Elephant foot: 0.15 mm compensation on the panel's first
layer, otherwise the engraved text closes up.

## 3. Hardware (BOM)
| Qty | Item | Where | For |
|---|---|---|---|
| 12 | M3 x 5.7 brass heat-set insert (hole 4.0) | Most (size not published - measure) | 4 panel corners, 4 plate bosses, 4 spare |
| 4 | M3 x 10 cap screw | Most | front panel |
| 4 | M3 x 8 cap screw | Most | electronics plate |
| 6 | M2.5 x 6 self-tapping (PT/KA) screw | any | TFT (4), PN532 (2) |
| 8+ | M3 x 6-10 screw + nut, or cable ties 3.6 mm | Most | modules on the plate slots |
| 3 | PG7 cable gland + locknut (hole 12.5-12.8, cable 3-6.5) | electrical supplier (Most has none) | LOCK, DOOR, SPARE |
| 1 | M16 x 1.5 gland + locknut (hole 16.0-16.3, cable 4-8) | electrical supplier | DC IN 12 V |
| 2 | cable tie 2.5-3.6 mm | any | R307 retention through its cradle |
| 2 | 4 mm pan-head wall screw + plug | any | keyholes |
| 8+ | M3 flat washer (ISO 7089, 3.2 x 7 x 0.5) | Most | under the nuts on the 3.4 x 20 plate slots |
| 4 | M3 nylon spacer / standoff 5 mm | Most | under the relay and buck converter (solder pins on their underside must not press on the plate) |
| 4 | M3 x 12 screw (instead of M3 x 6-10) | Most | modules on 5 mm spacers: 4 plate + 5 spacer + 1.6 PCB + nut 2.4 |

## 4. Tolerance / evidence register (what each opening is based on)
| Feature | Value | Basis | Confidence | Checked on the coupon by |
|---|---|---|---|---|
| TFT window | 30 x 40 | active area 28.03 x 35.04 (QDTFT1801) + glass position margin | DATASHEET + CHOSEN | the real TFT on the coupon mount |
| TFT bosses | 4 x Ø4.2 x 2.4 on 28.5 x 52 | LCDWIKI MSP1803 holes Ø3.2 on 28.5 x 52; glass 2.4 ± 0.1 | VARIANT | screwing the TFT on |
| PN532 pocket | 43.6 x 41.4 x 2.5, skin 1.5 | Elechouse 42.7 x 40.4; clones 43 x 40 | VARIANT | the board drops in; a card reads through |
| PN532 islands | Ø6 on 27.8 x 25.2 (both diagonals) | Elechouse V4 STEP ("same holes as V3") | REFERENCE | the 2 screws line up |
| R307 pocket / cradle | 44.6 x 20.5 / h 12 | GROW R307 manual 44.1 x 20 x 23.5 | DATASHEET (no tolerances) | the module sits; if ~52 long -> R307S |
| R307 aperture | 21.4 x 19.4 at the sensor end | manual "window 19 x 21" (head face); sensing area 15 x 11.19 | DATASHEET (interpretation) | coupon 21.0 x 19.0 vs 21.4 x 19.4 |
| LED holes | Ø5.1 | 5.0 body / 5.9 flange (Kingbright family) | REFERENCE | 5.0 / 5.1 / 5.2 / 5.3 |
| Buzzer cradle | ID 12.5, sound holes 7 x Ø1.6 | TMB12A05 Ø12.0 ± 0.2; Most listing 12 x 9.5 | DATASHEET / VARIANT | 12.3 / 12.5 / 12.7 |
| Gland holes | PG7 12.6, M16 16.2 | KLS / ABB / RS PRO gland sheets | DATASHEET | 12.4 / 12.6 / 12.8 / 16.2 |
| Insert holes | Ø4.0 x 7 in Ø8-10 bosses | CNC Kitchen M3 x 5.7 table | DATASHEET (for CNC Kitchen; Most's insert unknown) | 3.9 / 4.0 / 4.2 |
| M2.5 pilots | Ø2.2 | chosen | CHOSEN | 2.0 / 2.2 / 2.4 |
| USB opening | 14 x 12 at y 95, z 28 | ESP32 51.5 x 28.5 (Most); breadboard height 8.5-10 | VARIANT + REFERENCE | dry fit of the plate before printing the body |
| Plate envelopes | see the drawing, sheet 3/4 | Most listings (XL4016 ~64 x 47 x 26, WAGO-clone 21 x 12.5 x 14.5), others REFERENCE | mixed | dry fit |
| Text | engraved 0.6, >= 5 mm, bold | engraved strokes >= 1 mm survive a 0.4 nozzle | REFERENCE | ENGR 5/7 vs RAISED 5/7 on the coupon |

**Engraved vs raised (decision):** engraved, panel printed front-down. Reasons: (1) the front then comes off the
bed - the flattest, cleanest face, which is what people see; (2) raised text would need the front facing up
(text on top) and shows layer lines and stringing between letters; (3) engraved letters cannot be knocked off
and do not catch dirt as raised edges do. The coupon prints both side by side; if the owner prefers the raised
look, set `"label_style": "raised"` and rebuild.

## 5. Virtual assembly
`out/DoorEnclosure_Assembly.SLDASM` / `.STEP`: body + front panel + plate + 14 component envelopes (each the
part's outline + clearance, positions in params `components`). SOLIDWORKS interference detection (touching
faces not counted) result: `out/interference.txt`. Wire space: the plate modules end at z = 40, the front
modules start at z = 85 - 45 mm for the wiring loom (depth 110; was 65 / 25 mm at depth 90). STL check (`check_stl.py`): every printed part closed, manifold, consistent
winding (`out/stl_check.json`).

## 6. Assembly order
1. Inserts: 4 in the body's corner columns, 4 in the plate bosses (soldering iron ~220 °C for PLA).
2. Plate: modules on the slots (screws or ties) on their engraved labels; ESP32 USB toward the left wall.
3. Front panel: LEDs from behind (flange stops them), buzzer into its cradle (a drop of hot glue), TFT on its
   4 bosses (M2.5 x 6), PN532 face-down on its islands (2 x M2.5 x 5), R307 head through the aperture, cable
   tie through the cradle slots over its back.
4. Glands in the bottom wall, cables in, tie them to the tie bars above the glands.
5. Plate into the body (4 x M3 x 8), wire, then the panel on (4 x M3 x 10). The panel is the service lid.

## 7. Measure on the real parts (with the coupon) - the only open items
TFT hole pattern and glass position · PN532 hole positions and PCB thickness, a card read through 1.5 mm ·
R307 length (44.1 or ~52) and head size · Most's M3 insert diameter · LED flange · the buzzer's diameter ·
the breadboards' height (8.5 or 10) for the USB opening · the gland holes of the glands actually bought.
