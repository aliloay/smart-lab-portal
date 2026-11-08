# Measure five parts before printing the door box

Only three of the eleven door-controller components have manufacturer drawings that give dimensions: the **GROW R307 fingerprint sensor (44.10 x 20 x 23.50 mm, no flange, no ears)**, the **ST7735 1.8" TFT glass (34.70±0.2 x 46.70±0.2 x 2.40±0.1 mm, active area 28.03 x 35.04 mm)**, and a reference active buzzer (**Ø12.0±0.2 x 9.5±0.2 mm**). Everything else, including every mounting-hole position on every internal module, is at best a store-listed outline (VARIANT MATCHED) or another seller's figure (REFERENCE ONLY). The best hole data found for the PN532 comes from Elechouse's V4 CAD model: **42.68 x 40.38 mm, two Ø3.05 mm holes on a 27.80 x 25.20 mm diagonal**. Elechouse says V4 has the same shape and holes as V3, but the red Ekostra board is a clone. The fastener, gland and print figures are on firmer ground. CNC Kitchen M3 inserts need a **Ø4.0 mm hole with a 1.6 mm minimum wall**. PG7/M12/PG9/M16 glands need panel holes of **12.5–12.8 / 12.0–12.3 / 15.2–15.5 / 16.0–16.3 mm**. FDM clearances run 0.2–0.5 mm depending on the source. In practice the front panel (R307, TFT, LEDs, buzzer) can be drafted now. The internal plate (ESP32, XL4016, relay, PN532 standoffs, DC jack, terminals) cannot be finalised until about a dozen caliper measurements are taken, listed in the last section. The speaker/PAM8403 was removed by the owner and is not covered here.

Confidence labels used throughout:

| Label | Meaning |
|---|---|
| **DATASHEET VERIFIED** | Read from the manufacturer's own drawing or table for that part |
| **VARIANT MATCHED** | Stated on the store listing for the exact product bought, or taken from a drawing whose board layout matches the store photo |
| **REFERENCE ONLY** | Another seller, a related model, or a community source; clones differ |
| **UNVERIFIED** | Inferred, scaled off a drawing, or anecdotal; measure it |

## The front panel can be drafted from three real drawings

**R307 fingerprint sensor.** Most Electronics sells "Fingerprint Module R307" (ME-30297) without dimensions. Its photo shows the classic GROW "split type" part: a black body with a separate sloped prism head, a 6-wire lead ending in a white 6-pin housing, and **no flange or mounting ears** ([Most R307](https://mostelectronic.com/shop/sensors/fingerprint-module-r307/)). GROW's manual (Ver 1.20) gives the body as **44.10 long x 20 wide x 23.50 high** (connector excluded) and a sensing aperture of **15 x 11.19 mm** in the top view. It shows side notches **1.50 mm deep** whose front edge sits **22.90 mm** from the sensor-end face. It states **no tolerances** ([GROW R307 manual](https://cdn.hackaday.io/files/1911088176364672/r307-fingerprint-module-user-manual.pdf)). These are DATASHEET VERIFIED values. The manual's own spec table also lists a "window dimension 19mm*21mm". That figure conflicts with the drawn aperture and most likely describes the whole prism-head face. Some secondary dimensions are printed on the drawing but their meaning is UNVERIFIED: 3.45 and 12 (notch extents), 2.76 and 2.30 (head steps), and 1.05, 3.20 and 4.70 (connector drop and set-back). The rear PCB shows four corner holes with no dimensions.

Watch for the wrong module turning up. Resellers sell the R307S at **52 x 20 x 22** ([Hubtronics R307S](https://hubtronics.in/sensors/grow-r307s-fingerprint-module)). The AS608/ZFM-style Adafruit 751 is **56 x 20 x 21.5 with a 14 x 18 window** ([Adafruit 751](https://www.adafruit.com/product/751)). A unit that measures about 52 mm long is therefore not the classic R307. Without ears, the R307 has to sit in a rectangular cutout around the prism head (about 20.4 mm wide, giving 0.2 mm per side; UNVERIFIED) and be held from behind by a cradle that engages the 1.5 mm notches.

**1.8" ST7735 TFT (red "1.8 TFT SPI 128*160 V1.1").** The Most listing (ME-38699) gives no dimensions. Its photo shows four corner holes, an 8-pin header (VCC, GND, CS, RESET, A0, SDA, SCK, LED) on one short edge, SD pads on the other, and a full-size SD socket on the back, even though the listing text says "microSD" ([Most TFT](https://mostelectronic.com/shop/displays-lcd-7-seg-led/tft-lcd-display-module-spi-interface-1-8-inch-128160/)). That layout matches LCDWIKI's MSP1803 drawing: PCB **34.50 x 58.00 mm**, four **Ø3.20** holes on a **28.50 x 52.00 mm** grid, each **3.00 mm** from its adjacent edges, and **2.54 mm** headers. These figures are VARIANT MATCHED ([MSP1803 drawing](https://www.lcdwiki.com/images/8/87/MSP1803-005.png)).

The panel datasheet (QDTFT1801 v1.1) is DATASHEET VERIFIED for the glass. The backlight outline is **34.70±0.2 x 46.70±0.2 x 2.40±0.1 mm**, the active area is **28.03 x 35.04 mm**, and unmarked dimensions carry **±0.20**. The active area starts **3.00 mm** from the backlight edge opposite the FPC, which leaves an 8.66 mm margin on the FPC side, and is effectively centred across the width (3.33 / 3.34 mm) ([QDTFT1801 spec](https://www.lcdwiki.com/res/MSP1803/QDTFT1801_specification_v1.1.pdf)). Two things are not dimensioned in any source and are UNVERIFIED: where the glass is bonded on the PCB (scaled at about 6.0 mm from the SD edge and 5.2 mm from the header edge), and the stack height. One listing gives the board as 34.5 x 58 x 7.5 mm and "about 13 mm including pins" ([Uniktek](https://take.app/uniktek/p/cm7kxqkvn00fsgv7g2c7dm9xh)). Other clones are 34 x 56 with Ø2 holes ([Othoba](https://othoba.com/18-inch-spi-tft-lcd-display-module-dishantech-bd-940367)), so the hole grid must be confirmed. A practical window is the active area plus about 0.5 mm per side, roughly **29.0 x 36.0 mm**.

**5 mm LEDs and buzzer.** Most's red and green 5 mm LEDs are unbranded, diffused and flanged, with no data ([Most red LED](https://mostelectronic.com/shop/displays-lcd-7-seg-led/leds-displays-lcd-7-seg-led/led-red-color-5mm/)). The Kingbright T-1¾ drawing gives **body Ø5, flange Ø5.9, 8.6 mm to the flange, 1 mm flange thickness, 2.54 mm lead pitch, ±0.25** ([Kingbright L-53SRD-5V](https://static.rapidonline.com/pdf/55-0846.pdf)). This is REFERENCE ONLY. A **5.1–5.2 mm** panel hole lets the dome pass and stops the flange from behind; a 6.2–6.5 mm rear counterbore seats the flange flush.

Most lists its 5 V buzzer as **12 mm diameter x 9.5 mm high**, 2.3 kHz, "continuous tone generator", which means it is active (VARIANT MATCHED outline) ([Most 5 V buzzer](https://mostelectronic.com/shop/components/buzzers-mic-piezo/small-buzzer-5v-2/)). The shared photo is branded "HXD". The nearest drawing found, Huaneng's TMB12A05, gives **Ø12.0±0.2 x 9.5±0.2, pins 7.6±0.2 apart, Ø0.6 pins, (+) is the longer pin** ([TMB12A05](https://www.electrokit.com/upload/quick/0a/0c/a15b_41037353-tds.pdf)). This is REFERENCE ONLY for the HXD part. A cradle ID of 12.4–12.6 mm with a sound port over the central hole covers it.

## The PN532's hole pattern comes from a V4 CAD file, not a V3 drawing

Ekostra sells "PN532 NFC RFID Read/Write Module V3 Kit" (EK506, 265 EGP) at **42.7 x 40.4 x 4**. The site labels these as "cm", which is a unit error: they are the Elechouse mm figures. The listing has an SMD mode switch, gives 5–7 cm range, and states no hole size (VARIANT MATCHED) ([Ekostra PN532](https://ekostra.com/product/pn532-nfc-rfid-read-write-module-v3-kit/)). The Elechouse V3 manual confirms only the overall **42.7 x 40.4 x 4 mm** and has no drawing (DATASHEET VERIFIED). It also gives HSU/I2C/SPI switch settings of OFF-OFF / ON-OFF / OFF-ON and says the right-angle headers come loose ([Elechouse V3 manual](https://www.elechouse.com/elechouse/images/product/PN532_module_V3/PN532_%20Manual_V3.pdf)). Elechouse calls V4 a "drop-in replacement" with the "same shape, same mounting holes" ([Elechouse V4](https://www.elechouse.com/product/pn532-nfc-rfid-module-v4/)).

Parsing the V4 STEP model gives the following, all REFERENCE ONLY for the red clone ([V4 3D zip](https://www.elechouse.com/wp-content/uploads/2022/04/ELECHOUSE_PN532_V4_3D.zip)):

| Feature | Value (mm, from top-left corner) |
|---|---|
| Outline | 42.68 x 40.38, corner radius 3.39 |
| Hole A | Ø3.048 at X 7.39, Y 7.59 |
| Hole B | Ø3.048 at X 35.19, Y 32.79 (diagonally opposite) |
| Hole spacing | dX 27.80, dY 25.20, diagonal 37.52 |
| Hole keep-out | Ring of 10 vias; use nylon standoffs, about 6 mm OD max |
| 8-pin SPI header | 2.54 pitch, 6.49 in from top edge, X 15.10–32.88 |
| 4-pin I2C/HSU header | 2.54 pitch, 6.39 in from left edge, Y 16.38–24.00 |
| PCB thickness | Model shows 0.41 (not credible), so measure it |

A red V3 seller independently quotes **43 x 40 x 3.5 mm with 3 mm holes** ([Bastelgarage](https://www.bastelgarage.ch/pn532-nfc-rfid-module-v3-set-with-rfid-card-and-key)). The outline is therefore solid, but clone hole spacing could drift by fractions of a millimetre, so slot the standoff holes or oversize them by 0.5 mm. No measured data exists for read range through PLA or PETG. One printed PN532 enclosure keeps a **0.5 mm** wall over the antenna "for best RFID read" ([Printables PN532 enclosure](https://www.printables.com/model/101157-pn532-enclosure-with-wirecable-access)). NXP quotes a typical **70 mm** read distance, depending on the antenna ([NXP PN5321](https://nxp.com/part/PN5321A3HN)). Thinning the front wall to 1–1.5 mm over the antenna and keeping screws and brass inserts away from it is cheap insurance. The actual range must be measured through test coupons, in line with the owner's hardware rule.

## Internal modules have outlines but not a single sourced hole pattern

No Most listing gives mounting-hole positions for any internal module, and this is the central gap in the design. The table summarises what exists.

| Part (Most listing) | Outline (mm) | Label | Holes / notes |
|---|---|---|---|
| ESP32 30-pin CH340, USB-C | **51.5 x 28.5** | VARIANT MATCHED ([Most](https://mostelectronic.com/shop/arduino-development-boards/esp32-development-board-wifi-and-bluetooth-with-ch340-usb-type-c/)) | No holes listed; DOIT-style figures conflict (51.8 x 28.2 vs 51 x 25.4) ([Mischianti](https://mischianti.org/doit-esp32-dev-kit-v1-high-resolution-pinout-and-specs/)) |
| "ESP 32 Development Board" (ME-10765) | not stated | UNVERIFIED | Only the photo filename says "30pin" ([Most](https://mostelectronic.com/shop/arduino-development-boards/esp-32-development-board-wifi-bluetooth/)) |
| Espressif DevKitC V4 (reference) | **48.2 x 27.9** | DATASHEET VERIFIED, from a summary of the PDF ([Espressif layout](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_pcb_layout.pdf)) | Retail lists 54.4 x 27.9 including the antenna ([Mouser](https://www.mouser.fr/en/ProductDetail/356-ESP32-DEVKITC32E)) |
| XL4016 8 A buck with voltmeter (ME-23435) | **≈64 x 47 x 26, 45 g** | VARIANT MATCHED ([Most](https://mostelectronic.com/shop/dc-ac-converters/xl4016-dc-dc-buck-converter-8a-step-down-4-36v-to-1-25-36v-with-display/)) | No holes; IN/OUT are solder pads per the listing |
| Relay module 1-ch 12 V (ME-32878, HW-307 per photo filename) | not stated | UNVERIFIED ([Most](https://mostelectronic.com/shop/relay-solid-state-modules/relay-module-1-channel-12v-dc/)) | Generic: 50 x 26 x 18.5, 4 x Ø3.1 on 44.5 x 20.5, REFERENCE ONLY ([Newegg](https://www.newegg.ca/p/297-00TY-00013)) |
| Breadboard 170-tie (ME-29142, SYB-170 per image) | not stated | UNVERIFIED ([Most](https://mostelectronic.com/shop/read-boards-accessories/breadboard-170-tie-point/)) | Sellers range 45 x 34.5 x 8.5 to 48 x 36.5 x 10, e.g. **47 x 36.5 x 10** ([Grobotronics](https://grobotronics.com/breadboard-170-black.html?sl=en)); adhesive back, joinable |
| DC-022 5.5/2.1 jack (ME-21179) | not stated | VARIANT MATCHED (0.5 A, no hole size) ([Most](https://mostelectronic.com/shop/connectors/power-connectors/female-dc-power-2-1mm-connector-for-box-plastic/)) | Panel hole conflicts: **7.8 mm** (DC-022B) ([Sigmanortec](https://sigmanortec.ro/en/panel-female-jack-55x21mm-dc-022b)) vs **12 mm** ([Hubtronics](https://hubtronics.in/dc-022-dc-jack)) |
| "WAGO PCT-212" lever connector (ME-31216) | **21 x 12.5 x 14.5** | VARIANT MATCHED ([Most](https://mostelectronic.com/shop/connectors/wago-pct-212-parallel-wire-connector-2-pin/)) | A clone; genuine WAGO 221-412 is ≈13.1 x 8.3 x 18.6 ([Octopart](https://octopart.com/ja/part/wago/221-412)) |
| "Terminal Block 2Pin 5mm" (ME-10261) | not stated | VARIANT MATCHED: spec table says **CY350-3.5, 3.5 mm pitch** ([Most](https://mostelectronic.com/shop/connectors/terminal-blocks/2-pin-pcb-mount-screw-terminals-block-pitch-5mm-r-3/)) | KF301-2P 5.08 reference: 10 x 7.5 x 14 ([Sigmanortec](https://sigmanortec.ro/en/pcb-connector-2-pins-kf301-2p-5mm)) |

A few of these listings contradict themselves and are traps. The "5mm" terminal block is really a 3.5 mm-pitch CY350. The XL4016 page gives two different input ranges. The 38-pin ESP32 URL says CH340 while its title says CP2102. The Most lever connector is larger in every direction than a genuine WAGO. The XL4016 also matters thermally: one test measured the buck IC at **116 °C at 8 A** in still 22 °C air ([Schematix](https://schematix.co.nz/forum/how-to-s/buck-converter-8a-cv)). The door load is far below that, but the board still needs headroom above its heatsinks and a vent path. Because none of the holes are sourced, retention should not depend on them: put the ESP32 in female header strips or rails, put the lever connectors in printed pockets with about 0.3 mm clearance, and let the breadboard use its adhesive back. Screw-mounted bosses should go only on boards whose holes have been measured.

## Fastener, gland and print numbers are datasheet-grade

CNC Kitchen's table, reproduced by 3DJake, gives the M3 standard insert (L 5.7, OD 4.6) a **Ø4.0 hole and a 1.6 mm minimum wall**. The M3 short insert (L 3.0) uses the same hole and wall. The "Voron" insert (L 4.0, OD 5.0) uses a **Ø4.4 hole and 1.3 mm wall**. The table is DATASHEET VERIFIED ([3DJake CNC Kitchen M3](https://www.3djake.com/cnc-kitchen/threaded-inserts-m3-standard)). Blind holes should be about 1 mm deeper than the insert ([CNC Kitchen](https://www.cnckitchen.com/blog/tipps-amp-tricks-fr-gewindeeinstze-im-3d-druck-3awey)), which gives about **6.7 mm** depth and a boss of at least 7.8 mm OD, so 8 mm in practice. A 5.7 mm insert therefore cannot sit in the 3 mm wall itself; it needs bosses or corner pillars. Most sells "M3 Knurled Brass Threaded Insert Nut" without dimensions, along with copper M3 hex spacers in 6/10/15/20/30 mm lengths and M3 Allen screws ([Most insert](https://mostelectronic.com/shop/cnc-3d-printer-parts/m3-knurled-brass-threaded-insert-nut/)). Generic inserts reach **4.9–5 mm OD** ([Grobotronics kit](https://grobotronics.com/threaded-insert-assortment-kit-m3-150pcs.html?sl=en)), so measure the insert before setting the hole size.

M3 clearance holes are **3.2 / 3.4 / 3.6 mm** for close / medium / free fit ([Optimas](https://optimas.com/technical-resources/tapping-sizes/)). Head sizes are **5.5 mm (ISO 4762, k 3.0)** ([Accu](https://accu-components.com/fr/vis-a-tete-cylindrique-a-douille-metrique/3818-SSCF-M3-8-A2)) and **5.7 mm (ISO 7380, k 1.65)** ([Engineers Edge](https://engineersedge.com/iso_socket_button_head.htm)), which point to counterbores of about Ø6.0–6.5 mm. ISO 10642 countersunk heads are uncertain: Würth lists 5.81 mm, while the commonly quoted 6.72 mm was not confirmed ([Würth](https://eshop.wurth.ae/Countersunk-screw-with-hexagon-socket-head-ISO-10642-steel-88-plain-SCR-ISO10642-088-HS2-M3X6/008703%206.sku/en/US/AED)). Model a countersink to about Ø6.5 mm and test-fit it.

The cable-gland figures agree across three manufacturers (KLS, RND and RS PRO), all DATASHEET VERIFIED ([KLS](https://cdn.ozdisan.com/ETicaret_Dosya/513402_8698866.PDF); [RND](https://www.triopak.fi/files/product/RND%20Components/RND-cable-glands-strain-p10_eng_tds.pdf); [RS PRO](https://docs.rs-online.com/0389/A700000007247832.pdf)):

| Gland | Panel hole | Cable range | Wrench |
|---|---|---|---|
| PG7 | 12.5–12.8 | 3–6.5 | 15–16 |
| M12x1.5 | 12.0–12.3 | 3–6.5 | 15–16 |
| PG9 | 15.2–15.5 | 4–8 | 19 |
| M16x1.5 | 16.0–16.3 | 4–8 | 19 |

ABB gives a PG7 thread length of **8 mm** ([ABB CC-PG7-G](https://empower.abb.com/ecatalog/ec/EN_NA/p/CC-PG7-G)). That is far more than the 3 mm wall, so the right build is a plain clearance hole (top of range plus about 0.2 mm, e.g. M16 at Ø16.4) with the supplied locknut and a flat spot-face at least one wrench size across. A printed thread is the wrong choice. Most Electronics turned up no glands in its search ([Most search](https://mostelectronic.com/?s=cable+gland&post_type=product)), so they must come from an electrical supplier.

For FDM, the sources disagree. Xometry gives **0.2–0.3 mm** for a sliding fit and **0.8 mm stroke / 0.5 mm height** for embossed text ([Xometry](https://xometry.pro/en/?p=22061)). JLC3DP sets a **0.5 mm** minimum assembly clearance and 1.0 mm text detail ([JLC3DP](https://jlc3dp.com/help/article/3d-printing-design-guideline)). Hubs notes that vertical holes print undersize by an amount that depends on printer and material, and recommends a **45° chamfer** on bed-facing edges against elephant foot and no support for overhangs up to 45° ([Hubs](https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/)). Because of these disagreements, a printed hole-gauge coupon in the actual filament has to settle the clearance values. For wall-mounting keyholes no standard exists. References show a 4 mm slot under a 9 mm head entry ([Thangs keyhole hanger](https://thangs.com/designer/peaberry/3d-model/Keyhole%2520Hanger%2520%2528Single%2520%2526%2520Double%2529-46684)) and a 9.5 mm entry with a 4.8 mm slot ([CMT bit](https://www.canadianwoodworker.com/?p=25553)), with the screw head standing about **4–5 mm** off the wall ([Vaisala](https://docs.vaisala.com/r/M211863EN-B/en-US/GUID-117F2FA4-E5AD-4C0A-AAA0-70EF96267850)).

## The caliper list before the final print

Each item below is UNVERIFIED in every source found, and a wrong value in any of them breaks the print:

| Part | Measure | Expected (source) |
|---|---|---|
| R307 | Overall length (44.1 = R307, ~52 = R307S); prism-head footprint; notch position; rear-PCB holes; connector pitch (1.25 vs 1.0) | 44.10 x 20 x 23.50 (GROW) |
| TFT | Hole grid and hole Ø; glass offset from each PCB edge; total stack with header and SD socket | 28.50 x 52.00, Ø3.2 (MSP1803) |
| LEDs | Flange Ø (clones are often 5.6–6.0) | Ø5.9 (Kingbright) |
| Buzzer | Diameter, pin pitch, which pin is (+) | Ø12 x 9.5, 7.6 pitch (TMB12A05) |
| PN532 | Hole spacing and Ø, PCB thickness, height with headers, DIP-switch and antenna area | 27.80 x 25.20, Ø3.05 (V4 CAD) |
| ESP32 | Which board was bought, outline including antenna overhang, holes (if any), USB-C protrusion, height with pins | 51.5 x 28.5 (Most) |
| XL4016 | Hole Ø and spacing, terminal positions, underside lead height | ≈64 x 47 x 26 (Most) |
| Relay HW-307 | Outline, holes, terminal offset from edge | ~50 x 26 x 18.5, 44.5 x 20.5 (generic) |
| Breadboard | Outline with dovetails, height, presence of M2 holes | ~47 x 36.5 x 10 (sellers) |
| DC-022 jack | Thread OD; print 8 / 11 / 12 mm test holes | 7.8 or 12 (conflict) |
| Terminals and lever connectors | Pitch (3.5 vs 5.08), outlines | CY350-3.5; 21 x 12.5 x 14.5 |
| M3 insert, hex spacers, local wall screws | Insert OD and length; spacer across-flats; screw head Ø | 4.6 x 5.7 (CNC Kitchen) |

## Conclusion

The enclosure splits into two design problems. The front panel is defined mainly by drawn, toleranced parts: the R307 body and notches, the TFT active area, and the 12 x 9.5 buzzer. It can be modelled now, with the R307-versus-R307S length as the one check that decides whether the fingerprint cradle works at all. The interior is defined by clone boards whose store listings give outlines and nothing else. There the risk is less about a slightly wrong number and more about designing around a feature (a hole, a pitch, a gland the store does not stock) that the bought part does not have.

The best plan is to make the interior tolerant of that ignorance. Hold the ESP32 by its headers, put the lever connectors in pockets, use slotted holes for the PN532, and size bosses only from measured parts. Then spend one test print on a coupon that carries the insert holes, the DC-jack holes, the LED holes, a gland hole and 1/2/3 mm PN532 windows. A single coupon resolves the remaining printer-specific and RF questions with real measurements instead of seller figures.
