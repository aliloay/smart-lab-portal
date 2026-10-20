# Front-panel component dimensions for the door-access controller (Most Electronics parts)

Researched 2026-10-20. All dimensions in mm.

Confidence labels:
- **DATASHEET VERIFIED**: read directly from the manufacturer drawing for the same part.
- **VARIANT MATCHED**: from a drawing for a board or part whose photo or pinout matches the Most listing, but the drawing is not from Most.
- **REFERENCE ONLY**: from a drawing for the same part family, or from a reseller listing.
- **UNVERIFIED**: inferred or measured off a scaled drawing. Measure the real part with calipers before printing.

How the drawings were read: drawings embedded as images were extracted from the PDFs. The vector drawings (QDTFT1801 page 4, Kingbright page 1) were rendered with pdf.js in Edge and then read.

## 1. Which exact variant does Most Electronics sell?

### Takeaway
Most sells four relevant parts:
- **Fingerprint sensor:** the classic GROW R307 "split type" black body with a sloped prism head and a 6-wire flying-lead cable. It has **no flange and no mounting ears**.
- **Display:** the red "1.8 TFT SPI 128*160 V1.1" board. It has 4 corner holes, an 8-pin header, a 4-pin SD header on the opposite short edge, and a full-size SD socket on the back. This matches the LCDWIKI MSP1803 layout.
- **LEDs:** generic 5 mm diffused LEDs with a flange.
- **Buzzers:** generic 12 x 9.5 mm magnetic buzzers labelled "HXD".

### Cited Findings
**Fingerprint sensor**
- Listing "Fingerprint Module R307", SKU ME-30297, 849 EGP, category Sensors. The page gives only these specs: UART, 1000 templates, 3.6–6 V, anti-fake detection, LED indication. It gives no dimensions — [Most R307](https://mostelectronic.com/shop/sensors/fingerprint-module-r307/)
- The product photo (`wp-content/uploads/2025/10/Fingerprint-Module-R307.jpg`) shows:
  - a black rectangular body with a separate sloped prism head and a dark sensing window;
  - a 6-wire cable (red, black, yellow, green, white, grey) ending in a white 6-pin housing; the pitch cannot be read from the photo;
  - no visible ears or flange.
  
  This matches the GROW R307 "Split type" outline — [Most R307 photo](https://mostelectronic.com/wp-content/uploads/2025/10/Fingerprint-Module-R307.jpg)

**Display**
- Listing "TFT LCD Display Module SPI Interface 1.8 Inch 128*160", SKU ME-38699, 245 EGP. It names the ST7735 driver, 4-wire SPI, a 3.3 V LDO plus level shifter, and a "microSD card holder". It gives no dimensions — [Most TFT](https://mostelectronic.com/shop/displays-lcd-7-seg-led/tft-lcd-display-module-spi-interface-1-8-inch-128160/)
- Its pin table is: 1 VCC, 2 GND, 3 CS, 4 RESET, 5 A0, 6 SDA, 7 SCK, 8 LED — [Most TFT](https://mostelectronic.com/shop/displays-lcd-7-seg-led/tft-lcd-display-module-spi-interface-1-8-inch-128160/)
- The photo (`uploads/2026/06/Screenshot-2026-06-21-212730.png`) shows:
  - a red PCB printed "1.8 TFT SPI 128*160 V1.1";
  - 4 corner holes;
  - an 8-pin right-angle header labelled LED/SCK/SDA/A0/RESET/CS/GND/VCC;
  - SD_SCK/SD_MISO/SD_MOSI/SD_CS pads on the opposite short edge;
  - a **full-size SD socket** on the back. The text says "microSD", so the text and photo disagree.
  
  [Most TFT photo](https://mostelectronic.com/wp-content/uploads/2026/06/Screenshot-2026-06-21-212730.png)

**LEDs**
- Listings "Led Red Color (5mm)" (SKU ME-9825, 0.49 EGP) and "Led Green Color (5mm)" give no mechanical data — [Most red LED](https://mostelectronic.com/shop/displays-lcd-7-seg-led/leds-displays-lcd-7-seg-led/led-red-color-5mm/), [Most green LED](https://mostelectronic.com/shop/displays-lcd-7-seg-led/leds-displays-lcd-7-seg-led/led-green-color-5mm/)
- The red LED photo shows a diffused red dome with a flange collar and long leads, with no brand marking — [photo](https://mostelectronic.com/wp-content/uploads/2022/08/LED-Red-Color-5mm.jpg)

**Buzzers**
- "Small Buzzer 5V" (SKU ME-32997): 5 V, 85 dB, 30 mA max, 2.3 kHz ±500 Hz, diameter 12 mm, height 9.5 mm, THT, "continuous tone generator". The page does not say active or passive — [Most 5 V buzzer](https://mostelectronic.com/shop/components/buzzers-mic-piezo/small-buzzer-5v-2/)
- "Magnetic Buzzer 12V 12mm 2 Pin" (SKU ME-19495): same 12 mm diameter and 9.5 mm height, 12 V, 85 dB, 30 mA — [Most 12 V buzzer](https://mostelectronic.com/shop/components/buzzers-mic-piezo/magnetic-buzzer-12v-12mm-2-pin/)
- There are also two "Magnetic Buzzer 6V 12mm 2 Pin" listings and a "Buzzer Alarm 3-24V 95dB" listing — [search results](https://mostelectronic.com/?s=buzzer&post_type=product)
- All buzzer listings share one photo: a black cylinder with a white "HXD REMOVE SEAL AFTER WASHING" seal and 2 pins. It does not show the model number or which pin is longer — [photo](https://mostelectronic.com/wp-content/uploads/2022/08/Buzzer.jpg)

### Inferences
- **Buzzer type:** "continuous tone generator" at a fixed 2.3 kHz means the buzzers are active (self-oscillating) magnetic buzzers, in the same 12 x 9.5 class as TMB12A05 / HXD 12095.
- **Passive buzzer module:** the Most buzzer search showed **no passive buzzer module** (KY-006 style).
- **R307 sold variant:** Most sells the original R307 form, not the R307S or the AS608 "ZFM-20 / Adafruit 751" style. The firmware's use of the AS608 protocol at 57600 baud is a protocol fact and does not imply AS608 geometry.

### Gaps
- No part numbers or manufacturer names are given for the LEDs or buzzers.
- Whether the sold buzzer is HXD, HNDZ/Huaneng, or another maker cannot be confirmed from one photo.
- Most has no listing for a passive buzzer module.

## 2. What do manufacturer drawings give for each dimension (with tolerance)?

### Takeaway
Three parts have drawings with dimension values:
- **R307:** body 44.10 x 20 x 23.50 (GROW manual p.2, no tolerance stated).
- **TFT:** PCB 34.50 x 58.00, Ø3.20 holes on a 28.50 x 52.00 grid. The QDTFT1801 glass is 34.70±0.2 x 46.70±0.2 x 2.40±0.1, with a 28.03 x 35.04 active area.
- **Buzzer (TMB12A05):** Ø12.0±0.2 x 9.5±0.2, pins 7.6±0.2 apart.

For the 5 mm LED, the Kingbright T-1 3/4 drawing gives body Ø5, **flange Ø5.9**, 8.6 long, tolerance ±0.25.

### Cited Findings

#### 2a. GROW R307 (Hangzhou Grow, User Manual Ver 1.20, Feb 2011)
Source: [GROW R307 manual](https://cdn.hackaday.io/files/1911088176364672/r307-fingerprint-module-user-manual.pdf)

| Item | Value | Source location | Label |
|---|---|---|---|
| Overall length (sensor end to back end, connector not included) | **44.10** | p.2 drawing, bottom view | DATASHEET VERIFIED (matches Most photo shape) |
| Width | **20** | p.2 bottom view | DATASHEET VERIFIED |
| Height (base to top of prism head) | **23.50** | p.2 side view | DATASHEET VERIFIED |
| Spec-table "Module" size | 44.1 x 20 x 23.5 ("Outline Dimention: Split type") | p.1 table | DATASHEET VERIFIED |
| Sensing window (aperture in top view) | **15 (across the 20 width) x 11.19 (along the length)** | p.2 top view | DATASHEET VERIFIED |
| Side notches (one each side) | depth **1.50**; front edge **22.90** from the sensor-end face. The **3.45** and **12** dims in the top view are the notch / side-recess extents along the length, but which feature each one locates is ambiguous in the drawing | p.2 | DATASHEET VERIFIED values; interpretation UNVERIFIED |
| Prism head details | **2.76** (thickness of the head's vertical top face), **2.30** (step between head and body) | p.2 side view | DATASHEET VERIFIED values; interpretation UNVERIFIED |
| Underside PCB / connector | **1.05** PCB-to-connector step, **3.20** connector drop below base, **4.70** connector set-back from the back face | p.2 side view | DATASHEET VERIFIED values; interpretation UNVERIFIED |
| Tolerance | Not stated anywhere in the manual | — | Gap |

More from the manual:
- The spec table also says **"Window dimension 19mm*21mm"**. This conflicts with the 15 x 11.19 window in the drawing; it most likely describes the whole prism-head face — [GROW manual p.1](https://cdn.hackaday.io/files/1911088176364672/r307-fingerprint-module-user-manual.pdf)
- Connector pinout J1: 1 = 5V, 2 = GND, 3 = TXD, 4 = RXD, 5 = Touch, 6 = 3.3V (finger-detect supply). USB pads 7–10 sit on a separate pad set. The default baud rate is 57600 — [GROW manual p.3](https://cdn.hackaday.io/files/1911088176364672/r307-fingerprint-module-user-manual.pdf)
- The manual's back-PCB layout image shows four corner holes on the rear PCB and the 6-pin connector along one edge. **It gives no hole dimensions** — [GROW manual](https://cdn.hackaday.io/files/1911088176364672/r307-fingerprint-module-user-manual.pdf)
- **Mounting:** the R307 has **no flange or ears**, so there is no flange hole diameter or spacing to report. The drawing offers only two retention features: the side notches and, possibly, the rear-PCB corner holes.

#### 2b. 1.8" ST7735 red module
Board drawing: LCDWIKI MSP1803 — [LCDWIKI MSP1803 page](http://www.lcdwiki.com/1.8inch_SPI_Module_ST7735S_SKU:MSP1803), [dimension drawing MSP1803-005.png](https://www.lcdwiki.com/images/8/87/MSP1803-005.png).
Glass drawing: QDTFT1801 spec v1.1 — [QDTFT1801 spec](https://www.lcdwiki.com/res/MSP1803/QDTFT1801_specification_v1.1.pdf).

| Item | Value | Source | Label |
|---|---|---|---|
| PCB W x H | **34.50 x 58.00** | MSP1803-005 drawing; user manual "Module PCB Size 34.5x58.0" | VARIANT MATCHED |
| Mounting holes | 4 holes, **Ø3.20** | MSP1803-005 | VARIANT MATCHED |
| Hole centre spacing | **28.50 (across) x 52.00 (along)** | MSP1803-005 | VARIANT MATCHED |
| Hole centre to PCB edge | **3.00** from each adjacent edge | MSP1803-005 | VARIANT MATCHED |
| Main header J2 | 8 pins, **2.54** pitch, along one short edge (VCC, GND, CS, RESET, A0, SDA, SCK, LED) | MSP1803-005; pin order matches the Most table | VARIANT MATCHED |
| Header lateral position | The drawing gives a **2.50** dimension on the GND pin, but what it references is unclear. Scaling the drawing puts pin 1 (VCC) about 8.6 mm and pin 8 about 26.4 mm from the left long edge, centred on the edge row near the holes | MSP1803-005 (scaled) | UNVERIFIED |
| SD header J4 | 4 pins (SD_CS, SD_MOSI, SD_MISO, SD_SCK), 2.54 pitch, on the opposite short edge | MSP1803-005; matches the Most photo | VARIANT MATCHED |
| Glass/backlight outline (LCM) | **34.70±0.2 (W) x 46.70±0.2 (H) x 2.40±0.1 (D)**, FPC not included | QDTFT1801 p.3 table and p.4 drawing | DATASHEET VERIFIED for the panel; VARIANT MATCHED for the Most board |
| TFT glass | 41.42 x 31.83 | QDTFT1801 p.4 | DATASHEET VERIFIED (panel) |
| Colour-filter (CF) area | 38.39 x 31.83 | QDTFT1801 p.4 | DATASHEET VERIFIED (panel) |
| Active area | **28.03 (W) x 35.04 (H)**; pixel 0.219 x 0.219 | QDTFT1801 p.3/p.4; MSP1803 manual | DATASHEET VERIFIED (panel) |
| Active-area offset, long axis | AA edge **3.00** from the backlight edge at the end opposite the FPC (TFT glass edge 1.32 from the same backlight edge). So the FPC-side margin is 46.70 − 3.00 − 35.04 = **8.66** | QDTFT1801 p.4 (3.00 and 1.32 read; 8.66 derived) | DATASHEET VERIFIED values; 8.66 derived |
| Active-area offset, short axis | AA edge **3.33** from one long backlight edge (TFT glass 1.43 from it). So the other margin is 34.70 − 3.33 − 28.03 = **3.34**: effectively centred | QDTFT1801 p.4 (3.34 derived) | DATASHEET VERIFIED values; 3.34 derived |
| Drawing general tolerance | ±0.20 for unmarked dimensions (note 7) | QDTFT1801 p.4 | DATASHEET VERIFIED |
| Glass position on the PCB | Scaling MSP1803-005 puts the glass about **6.0 from the J4 (SD-header) edge** and **about 5.2 from the J2 (8-pin) edge**. The glass (34.70) is nominally 0.2 wider than the PCB (34.50) | MSP1803-005 (scaled, not dimensioned) | UNVERIFIED |
| Total thickness with header and SD socket | 34.5 x 58 x 7.5 mm, "about 13 mm including pins" | AZ-Delivery-type listing ([Uniktek](https://take.app/uniktek/p/cm7kxqkvn00fsgv7g2c7dm9xh)); other listings give 34 x 56 x 6.5 with Ø2 holes ([Othoba](https://othoba.com/18-inch-spi-tft-lcd-display-module-dishantech-bd-940367)) | REFERENCE ONLY |

#### 2c. 5 mm LED (Kingbright T-1 3/4 family drawing, L-53SRD-5V, spec DSAD0630 rev V.3A, p.1)
Source: [Kingbright L-53SRD-5V](https://static.rapidonline.com/pdf/55-0846.pdf). All values: REFERENCE ONLY, because the Most LED is unbranded.

| Item | Value |
|---|---|
| Body diameter | **Ø5** |
| Flange diameter | **Ø5.9** |
| Length, dome tip to the flange's lead side | **8.6** |
| Flange thickness | **1** |
| Resin / meniscus protrusion below the flange | **1.0 max** |
| Lead size | **0.5 square** |
| Lead pitch | **2.54** |
| Lead length | **27 min** |
| Tolerance | ±0.25 unless noted |

- Reseller listings for L-53 parts give "5 x 8.6 mm" — [RS L-53SRC-C](https://au.rs-online.com/web/p/leds/2471713/)

#### 2d. Active buzzer TMB12A05 (Jiangsu Huaneng / "HNDZ", datasheet p.2)
Source: [TMB12A05 datasheet (Electrokit)](https://www.electrokit.com/upload/quick/0a/0c/a15b_41037353-tds.pdf). The TMB12A12 (12 V) sheet uses the same drawing layout: [TMB12A12](https://www.electrokit.com/upload/quick/e9/37/a268_41037354-tds.pdf).

| Item | Value |
|---|---|
| Diameter | **Ø12.0±0.2** |
| Height | **9.5±0.2** (body, pins not included) |
| Pin spacing | **7.6±0.2** |
| Pin diameter | **Ø0.6±0.05** |
| Pin lengths | **4.0** and **5.5** below the body; (+) is the longer pin. There is also a 0.5 base step |
| Sound hole | Central, on the top face |
| Unmarked tolerance | ±0.5 |

Electrical data from the datasheet table: rated 5 V, operating 3–7 V, resonance 2400±300 Hz; the text-column extraction also gives 30 mA and 95 (most likely the dB figure). This is DATASHEET VERIFIED for the TMB12A05 and REFERENCE ONLY for the Most part.

Other 12 x 9.5 sources:
- The Star Micronics TMB-05/TMB-12 series uses the same 12 x 9.5 outline — [Star TMB05 sheet](https://datasheets.ibselectronics.com/TMB05-Star-Micronics-datasheet-10127983.pdf)
- The Most listings independently state 12 mm diameter and 9.5 mm height — [Most 5 V buzzer](https://mostelectronic.com/shop/components/buzzers-mic-piezo/small-buzzer-5v-2/)

### Inferences
**R307 front panel**
- The sensor must be presented through a rectangular cutout around the prism head, retained from behind by a cradle using the 1.5 mm side notches. There is no flange to bolt.
- A head cutout of about 20.4 x (head length) would clear the body width with 0.2 per side. This is an inference only; the head length along the body is not dimensioned. Measure the head's footprint on the real part.

**TFT front panel**
- Window = active area 28.03 x 35.04 plus about 0.5 per side, so about 29.0 x 36.0. This follows the QDTFT1801 note that the bezel edge sits 0.2–0.5 mm outside the viewing area.
- Place the window 3.00 + 0.5 from the glass edge at the SD-header end. Its true position relative to the PCB holes is set by where the glass is bonded, which is unverified.
- Standoffs on the 28.50 x 52.00 grid. Use M3 clearance (Ø3.2) or M2.5.
- Panel inner face to PCB front: about 2.4 mm (glass) plus adhesive.

**LED holes**
- Flange Ø5.9 > body Ø5.0. A through-hole of **about 5.1–5.2 mm** (FDM prints holes undersize) lets the dome pass while the flange stops it from behind. Use a 6.2–6.5 mm counterbore on the back if the flange should sit flush.
- For snap/press-fit without a holder, use 5.0 and test-print a gauge.

**Buzzer**
- Cradle ID about 12.4–12.6 (12.0 + 0.2 tolerance + print clearance).
- Put a sound port in the panel in front of the central hole. For a generic part, the 7.6 pitch matters only if the buzzer sits on a PCB.

### Gaps
- R307: no tolerances in the GROW manual. No dimensioned rear-PCB hole positions or diameter. Connector pitch (JST 1.25 vs SH 1.0) is not stated in the manual and cannot be read from the photo — UNVERIFIED; measure it.
- TFT: the glass-to-PCB offset and the header lateral offset are not dimensioned in the MSP1803 drawing; the scaled values are UNVERIFIED. PCB thickness, SD socket height and header height are not in any primary source found.
- LED: no datasheet exists for the unbranded Most LEDs. Clone flanges are commonly 5.6–6.0, but I found no source for the clones specifically.
- Buzzer: the HXD-branded drawing was not found. Pin pitch for the sold part is unverified (the TMB12A05 gives 7.6±0.2).

## 3. Where do clone variants differ?

### Takeaway
The big fingerprint risk is buying an R307S or an AS608/"ZFM-20"-style module in place of the classic R307. These use different outlines:
- **classic R307:** 44.1 x 20 x 23.5, no ears;
- **R307S:** 52 x 20 x 22 per resellers;
- **Adafruit 751 style:** 56 x 20 x 21.5 with a 14 x 18 window.

For the 1.8" TFT, clones differ in PCB length (56 vs 58), hole size (Ø2 vs Ø3 / Ø3.2) and SD socket type. Adafruit #358 is a different board.

### Cited Findings
- R307S: module size 52 x 20 x 22, image capture surface 15 x 11 — [Hubtronics R307S](https://hubtronics.in/sensors/grow-r307s-fingerprint-module)
- R307 resellers also give 52 x 20 x 22 with an 11 x 15 effective area. This conflicts with GROW's own 44.1 x 20 x 23.5 for the R307 — [Hubtronics R307 USB/UART](https://hubtronics.in/r307-usb-uart-fingerprint-sensor?tag=usb2.0); [GROW manual](https://cdn.hackaday.io/files/1911088176364672/r307-fingerprint-module-user-manual.pdf)
- Generic "R307" listings give a 14 x 18 window — [Hackster R307 project](https://www.hackster.io/rau7han/diy-fingerprint-door-lock-system-040249)
- Adafruit 751 (AS608 / ZFM-style optical sensor): full size 56 x 20 x 21.5; "exposed dimensions (when placed in box) 21 x 21 x 21 mm, triangular"; window 14 x 18; mounting holes not specified — [Adafruit 751](https://www.adafruit.com/product/751)
- The RAK12001 (a WisBlock board built around a GROW sensor) lists a "19 x 21" window. This is not the bare R307 outline — [RAK12001 datasheet](https://docs.rakwireless.com/product-categories/wisblock/rak12001/datasheet/)
- 1.8" TFT clone outlines found in listings:

  | Listing | Board size | Holes |
  |---|---|---|
  | Othoba | 34 x 56 x 6.5 | 4 holes, Ø2 |
  | TinyTronics (Waveshare-listed) | 57 x 34 | Ø3.0 |
  | Eckstein (MSP1803) | 34.5 x 58.0 | — |

  Sources: [Othoba](https://othoba.com/18-inch-spi-tft-lcd-display-module-dishantech-bd-940367), [TinyTronics](https://www.tinytronics.nl/shop/en/displays/tft/waveshare-1.8-inch-tft-lcd-display-128*160-pixels-spi), [Eckstein MSP1803](https://eckstein-shop.de/18-inch-TFT-LCD-Display-Modul-8Pin-ST7735S-128x160-SPI-for-Arduino-with-SD-Card-Slot-EN)
- The MSP1803 board drawing and the Most "V1.1" photo show the same features: 4 corner holes, 8-pin VCC…LED header on one short edge, 4-pin SD header on the other — [MSP1803-005](https://www.lcdwiki.com/images/8/87/MSP1803-005.png); [Most photo](https://mostelectronic.com/wp-content/uploads/2026/06/Screenshot-2026-06-21-212730.png)
- **Buzzers:** the TMB12A05 (Huaneng) and Star TMB series share the 12 x 9.5 outline. The Most photo shows "HXD" branding, a different maker — [TMB12A05](https://www.electrokit.com/upload/quick/0a/0c/a15b_41037353-tds.pdf); [Most buzzer photo](https://mostelectronic.com/wp-content/uploads/2022/08/Buzzer.jpg)

### Inferences
- **R307:** design the cradle for 44.1 x 20 x 23.5. If the owner's unit measures about 52 long, it is an R307S-type body. The window and width are similar (15 x 11 in both), but length and height differ.
- **TFT:** the "34 x 56 / Ø2" boards are a different (older, 2 mm-hole) clone. The Most "V1.1" photo matches the 34.5 x 58 MSP1803 layout, but confirm with calipers: measure hole spacing (expect 28.5 x 52.0) and hole size (expect 3.2).
- **Adafruit #358:** a different 1.8" breakout (different PCB outline and pinout). Do not use its drawing for this part. This comes from the task brief; I did not fetch the #358 drawing in this session.

### Gaps
- No manufacturer (GROW) drawing for the R307S or the AS608 was found, so their notch and head geometry is unknown.
- I found no photo-with-ruler measurement of the Most units.
- The fastest way to settle every UNVERIFIED value is to measure the owner's actual parts with calipers: R307 length, connector pitch, TFT hole spacing, glass offset, and thickness stack.
