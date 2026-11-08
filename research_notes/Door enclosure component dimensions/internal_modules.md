# Door-controller internal modules: dimensions of the Most Electronics variants (mostelectronic.com)

Researched 2026-10-20. Label key:
- **DATASHEET VERIFIED**: from a manufacturer drawing or datasheet.
- **VARIANT MATCHED**: stated on the Most Electronics listing for that exact product.
- **REFERENCE ONLY**: from another seller or a community source for the same generic module. Clones differ.
- **UNVERIFIED**: no source found. Measure with calipers before printing.

Overall caveat: Most Electronics listings give at most an L x W (x H) outline. None of the listings I read gives mounting-hole positions or diameters. Every hole position below is REFERENCE ONLY or UNVERIFIED, so measure the physical parts before finalising the plate.

## Q1. Which exact variants does Most Electronics sell? (listings, titles, photos)

### Takeaway
Most sells three classic ESP32-WROOM-32 dev boards: an unspecified "ESP 32" board whose photo filename says 30-pin, a 30-pin CH340 board with USB-C, and a 38-pin CP2102 board with micro-USB. It also sells an XL4016 8 A buck converter with a voltmeter, an LM2596 board without a display (and a separate LM2596 with display), a 1-channel 12 V relay module (HW-307, active-low), a DC-022 panel jack, 5 mm / 5.08 mm screw terminals and "WAGO PCT-212..215" lever connectors. I found no listing for the 2-heatsink XL4016 version without a display, for KF301-branded terminals, or for WAGO 221-series connectors.

### Cited Findings
**ESP32 boards** (the search shows 61 ESP32 results; only the first page was read)
- "ESP 32 Development Board WiFi Bluetooth", SKU ME-10765, 299 EGP. The page states no pin count, USB type or dimensions. The photo filename is `esp32-development-kit-30pin_1024x1024.webp`, which suggests a 30-pin board, but the page text does not say so (UNVERIFIED). Photo: https://mostelectronic.com/wp-content/uploads/2022/08/esp32-development-kit-30pin_1024x1024.webp — [Most listing](https://mostelectronic.com/shop/arduino-development-boards/esp-32-development-board-wifi-bluetooth/)
- "ESP32 Development Board (WIFI and Bluetooth) with Ch340 USB Type-C", 379 EGP: 30 pins (2 x 15), **USB Type-C**, CH340C, ESP-WROOM-32 module, SOT-223 regulator, PCB antenna, **51.5 x 28.5 mm** (VARIANT MATCHED). Photo: https://mostelectronic.com/wp-content/uploads/2025/11/ESP32-Development-Board-WIFI-and-Bluetooth-with-Ch340-USB-Type-C.webp — [Most listing](https://mostelectronic.com/shop/arduino-development-boards/esp32-development-board-wifi-and-bluetooth-with-ch340-usb-type-c/)
- "ESP32-WROOM-32 Development Board 38-Pin with CP2102 – Mirco USB", 375 EGP: 38 pins, **micro-USB**, CP2102, EN and BOOT buttons, **48 x 26 mm** (VARIANT MATCHED). The URL slug says "esp32e-wroom ... ch340", which conflicts with the CP2102 title, so check the USB chip on arrival. Photo: https://mostelectronic.com/wp-content/uploads/2025/11/Screenshot-2026-06-21-122451.png — [Most listing](https://mostelectronic.com/shop/arduino-development-boards/esp32e-wroom-development-board-wifi-and-bluetooth-38-pin-with-ch340/)
- Also listed but not read: "ESP32-S 38Pin Development Board" — [Most](https://mostelectronic.com/shop/arduino-development-boards/esp32-s-38pin-development-board-wifi-and-bluetooth/)

**Buck converters**
- "XL4016 DC-DC Buck Converter 8A Step Down 4-36V to 1.25-36V with Display", SKU ME-23435, 190 EGP: **approx. 64 x 47 x 26 mm (L x W x H), 45 g** (VARIANT MATCHED). It has a 3-digit voltmeter and multi-turn pot. Terminals are labelled IN+, IN-, OUT+, OUT-. The listing says "pins are solder-in", meaning wire pads rather than screw terminals; check this on the real part. Rating: 5 A continuous, 8 A peak, 200 W max. The listing contradicts itself on input range (4-36 V in the spec, 4-40 V in the features). No mounting holes are listed. Photo: https://mostelectronic.com/wp-content/uploads/2025/04/4v-38v-to-125v-36v-8a-dc-dc-step-down-buck-power-supply-module-with-digital-voltmeter-xl4016-602171_480x.png.webp — [Most listing](https://mostelectronic.com/shop/dc-ac-converters/xl4016-dc-dc-buck-converter-8a-step-down-4-36v-to-1-25-36v-with-display/)
- In the "xl4016" search results, the only XL4016 product was the display version above. I found no separate "300 W / 2 heatsinks, no display" XL4016 listing. — [Most search](https://mostelectronic.com/?s=xl4016&post_type=product)
- "LM2596 DC-DC Adjustable Step-Down Converter (3A)", SKU ME-12901, 50 EGP: **43 x 21 x 14 mm** (VARIANT MATCHED). No holes are listed. Photo: https://mostelectronic.com/wp-content/uploads/2023/09/AD281-2.webp — [Most listing](https://mostelectronic.com/shop/dc-ac-converters/lm2596-dc-dc-adjustable-step-down-converter-3a/)
- Also sold, not read: "Step-Down Voltage Regulator with Display LM2596 3.2V-35V 3A" — [Most](https://mostelectronic.com/shop/dc-ac-converters/dc-dc-step-down-adjustable-voltage-converter-module-with-display-3a-lm2596/)

**Relay**
- "Relay Module 1 Channel (12Vdc)", SKU ME-32878, 34.90 EGP. The page gives no dimensions, holes or relay part number. Optocoupler is described only as "(model dependent)". The photo filename is `Relay-Module-1-Channel-Active-Low-Trigger-12V-HW-307.jpg`, which suggests board HW-307 with active-low trigger (UNVERIFIED from page text). Photo: https://mostelectronic.com/wp-content/uploads/2025/12/Relay-Module-1-Channel-Active-Low-Trigger-12V-HW-307.jpg — [Most listing](https://mostelectronic.com/shop/relay-solid-state-modules/relay-module-1-channel-12v-dc/)
- Alternatives at Most: "Relay Module Works on (5V/12V/24V) Signal" (66.90 EGP) and "Relay Module 12V With Timer 555". — [Most search](https://mostelectronic.com/?s=relay+module&post_type=product)

**Connectors**
- "Female DC Power 2.1mm Connector for Box Plastic (DC-022)", SKU ME-21179, 4.50 EGP: 5.5 mm OD / 2.1 mm pin, plastic+metal, rated 0.5 A. The page gives **no panel-hole size or thread**. Photo: https://mostelectronic.com/wp-content/uploads/2024/12/dc-022-55-21-power-socket-768x768-1.jpg — [Most listing](https://mostelectronic.com/shop/connectors/power-connectors/female-dc-power-2-1mm-connector-for-box-plastic/)
- "Terminal Block 2Pin 5mm Pitch", SKU ME-10261, 4.25 EGP. The spec table says **model CY350-3.5, 3.5 mm pitch**, which contradicts the 5 mm title. It also lists 300 V / 10 A, 24-18 AWG. The page shows a dimension image but no numeric values. — [Most listing](https://mostelectronic.com/shop/connectors/terminal-blocks/2-pin-pcb-mount-screw-terminals-block-pitch-5mm-r-3/)
- Other terminal listings: "Terminal Block 3Pin 5mm Pitch" (slug says KF126-5.0-3P), and "Pluggable Terminal Block 2 Pin / 3 Pin 5.08mm Pitch". No KF301-branded listing appeared on the first results page. — [Most search](https://mostelectronic.com/?s=terminal+block&post_type=product)
- "WAGO PCT-212 Parallel Wire Connector 2 Pin", SKU ME-31216, 5.90 EGP: **21 x 12.5 x 14.5 mm**, 0.08-2.5 mm², strip 9-10 mm, rated 32 A / 250 VAC (VARIANT MATCHED). PCT-213/214/215 (3/4/5-pole) and SPL-62 are also listed. "PCT-21x" is a generic lever-connector series name, not WAGO's "221-41x" part numbering. — [Most listing](https://mostelectronic.com/shop/connectors/wago-pct-212-parallel-wire-connector-2-pin/)

### Inferences
- At 190 EGP, the XL4016 Most sells is the common "XL4016 + voltmeter" board (64 x 47 class), not the 60 x 37 2-heatsink layout.
- The WAGO-branded "PCT-212" at 5.90 EGP is almost certainly a generic clone rather than a genuine WAGO 221-412. Its listed 21 x 12.5 x 14.5 mm outline is also larger than genuine 221-412 figures (about 13 x 8.3 x 18.6 mm). Design the plate for the Most numbers, or measure.

### Gaps
- Only the first page of each search was read. Other ESP32, relay or jack variants may exist on later pages.
- No Most listing gives mounting holes for any module.

## Q2. ESP32 boards: outline, holes, height, USB connector, antenna keep-out

### Takeaway
For the boards Most sells, the 30-pin USB-C board is listed at 51.5 x 28.5 mm and the 38-pin board at 48 x 26 mm (both VARIANT MATCHED). Espressif's own DevKitC V4 layout gives 48.2 x 27.9 mm. I found no source with verified mounting-hole coordinates for DOIT-style 30-pin boards.

### Cited Findings
- Most 30-pin CH340 USB-C board: 51.5 x 28.5 mm (VARIANT MATCHED) — [Most](https://mostelectronic.com/shop/arduino-development-boards/esp32-development-board-wifi-and-bluetooth-with-ch340-usb-type-c/)
- Most 38-pin CP2102 micro-USB board: 48 x 26 mm (VARIANT MATCHED) — [Most](https://mostelectronic.com/shop/arduino-development-boards/esp32e-wroom-development-board-wifi-and-bluetooth-38-pin-with-ch340/)
- Espressif ESP32-DevKitC V4 PCB layout: **48.2 x 27.9 mm** (DATASHEET VERIFIED, via search summary of the layout PDF; I could not render the PDF myself). CNX Software reports the same size and notes the antenna layout complicates the figure — [Espressif PCB layout PDF](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_pcb_layout.pdf); [CNX Software](https://www.cnx-software.com/2022/09/30/esp32-devkitc-v4-iot-development-board-ships-with-esp32-wroom-da-dual-antenna-module/)
- The official DevKitC uses **micro-USB**. The 32E/VE variants have a PCB antenna and 32UE/VIE an external connector. The user guide gives no keep-out guidance and points to the dimension drawing (PDF and DXF) — [Espressif DevKitC user guide](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html); drawing: https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_dimensions.pdf and https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_dimensions.dxf
- Mouser and Grid Connect list **54.4 x 27.9 mm** for ESP32-DevKitC-32E (REFERENCE ONLY; may include module/antenna overhang) — [Mouser](https://www.mouser.fr/en/ProductDetail/356-ESP32-DEVKITC32E); [Grid Connect](https://info.gridconnect.com/products/esp32-devkitc-32e-wroom-module-development-kit)
- DOIT DevKit V1 (30-pin) sizes conflict between sources (REFERENCE ONLY):
  - 51.8 x 28.2 mm per a user comment that links a real-size SVG with holes — [Mischianti](https://mischianti.org/doit-esp32-dev-kit-v1-high-resolution-pinout-and-specs/)
  - 51 x 25.4 mm — [Cirkit Designer](https://docs.cirkitdesigner.com/component/48217595-4d98-4eeb-9d6b-04d5d21310af/esp32-devkit-v1-30-pin)
  - The Fritzing part author says its hole positions are not verified against a real board — [Fritzing forum](https://forum.fritzing.org/t/doit-esp32-devkit-v1/6158)
- I found no source for the frequently quoted 51.45 x 28.33 mm figure (UNVERIFIED).

### Inferences
- Plan for about 52 x 29 mm for the 30-pin USB-C board and about 55 x 28 mm for the 38-pin board. The 38-pin listing's 48 mm length probably excludes the WROOM antenna overhang, as Espressif's 48.2 mm board size versus the 54.4 mm retail figure suggests. This is an inference; measure the part.
- Clone 30-pin boards typically have 4 corner holes (about Ø3 mm), and many 38-pin clones have none. Neither is sourced here (UNVERIFIED), so plan to hold the board by its headers in female header strips, or with a clip or rails, rather than by screws.
- Leave the WROOM PCB antenna end free of copper, metal and wires beyond the board edge. I found no numeric keep-out figure in a source this session.

### Gaps
- Not found: hole diameter and positions, height with headers, USB connector protrusion past the PCB edge, and a numeric antenna keep-out. The Espressif dimension PDF was downloaded but could not be rendered here, because no PDF renderer or pypdf is installed. Open it manually: https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_dimensions.pdf

## Q3. Buck converters (XL4016, LM2596): outline, holes, height, terminals

### Takeaway
The Most XL4016 with display is listed at about 64 x 47 x 26 mm, and the Most LM2596 at 43 x 21 x 14 mm (both VARIANT MATCHED). I found no sourced hole spacing for either. For the LM2596, one seller gives two holes 6 mm from the ends, and a printable mount uses M3 screws (REFERENCE ONLY).

### Cited Findings
- XL4016 with display (Most): about 64 x 47 x 26 mm, 45 g. IN+/IN-/OUT+/OUT- are solder pads per the listing. No holes are listed (VARIANT MATCHED) — [Most](https://mostelectronic.com/shop/dc-ac-converters/xl4016-dc-dc-buck-converter-8a-step-down-4-36v-to-1-25-36v-with-display/)
- XL4016 chip datasheet: 180 kHz, 1.25 V FB, thermal shutdown and current limit. The datasheets conflict on rating: Rev 1.3 gives 12 A and 8-36 V, older copies give 8 A and 8-40 V. RθJA is 30 °C/W with no heatsink (DATASHEET VERIFIED, chip only, no module mechanics) — [XL4016 datasheet (robu mirror)](https://test.robu.in/wp-content/uploads/2020/09/XL4016-datasheet.pdf); [radiolocman](https://www.radiolocman.com/datasheet/pdf.html?di=185685)
- Module design notes (REFERENCE ONLY):
  - Two heatsinks are used, one on the XL4016 and one on the Schottky diode.
  - The buck IC measured 116 °C at 8 A in still 22 °C air, with no extra airflow.
  - The 300 W rating is marketing; listings say 200 W.
  — [Schematix forum](https://schematix.co.nz/forum/how-to-s/buck-converter-8a-cv); [Zbotic guide](https://zbotic.in/xl4016-buck-converter-high-current-8a-adjustable-power-supply-guide/)
- LM2596 (Most): 43 x 21 x 14 mm (VARIANT MATCHED) — [Most](https://mostelectronic.com/shop/dc-ac-converters/lm2596-dc-dc-adjustable-step-down-converter-3a/)
- LM2596 board, REFERENCE ONLY:
  - Two mounting holes, 6 mm from the end — [Robojax listing](https://robojax.com/products.php?pid=455)
  - A printable mount uses 2x M3x10 screws and nuts — [Printables buck converter mount](https://www.printables.com/model/1255372-buck-converter-mount)
  - The KAmod LM2596 PDF has a dimensions section, not opened — [Kamami wiki](https://wiki.kamamilabs.com/extensions/JZPDFGen/pdf/KAmod%20LM2596-2052.pdf)

### Inferences
- The XL4016 runs hot at 8 A, so leave space above the heatsinks and a vent path in the enclosure. For a door-lock supply drawing well under 5 A, the heat load is far lower. That last point is engineering judgement, not a source.
- Use standoffs at least 5 mm tall under the XL4016, because through-hole leads and the display pins protrude underneath (UNVERIFIED).

### Gaps
- Not found: XL4016 hole diameter and spacing, terminal coordinates, and the 60 x 37 x 26.8 / 65 x 47 figures from the brief. LM2596 hole spacing was not confirmed (the "30 x 16" figure is unsourced) and must be measured.

## Q4. 1-channel 12 V relay module: outline, holes, terminals

### Takeaway
The Most listing gives no dimensions. Generic SRD-relay 1-channel modules are commonly listed as 50 x 26 x 18.5 mm with 4 holes of Ø3.1 mm on a 44.5 x 20.5 mm rectangle. That is REFERENCE ONLY: Most's board is HW-307, which may differ.

### Cited Findings
- Most "Relay Module 1 Channel (12Vdc)": no dimensions, holes, relay part or confirmed optocoupler. The photo filename indicates HW-307, active-low — [Most](https://mostelectronic.com/shop/relay-solid-state-modules/relay-module-1-channel-12v-dc/)
- Generic module: about 50 x 26 x 18.5 mm, 4 holes Ø3.1 mm, 44.5 x 20.5 mm pitch (REFERENCE ONLY; the Newegg page is a 2-channel listing quoting the same figures) — [Newegg](https://www.newegg.ca/p/297-00TY-00013); [1-ch listing](https://plastiquealaloupe.fondationtaraocean.org/products/12v-1-channel-relay-module-using-bidirectional-optocoupler-i/210254300/)
- SRD-12VDC-SL-C relay body is 15.6 x 19.2 mm with a height of 15.8 mm, rated 10 A AC/DC (distributor data, REFERENCE ONLY rather than a Songle drawing) — [LCSC C30431](https://www.lcsc.com/product-detail/C30431.html)

### Inferences
- The relay body (15.8 mm) plus a 1.6 mm PCB plus solder tails gives about 18.5 mm overall, which agrees with the generic figure. Inference only.

### Gaps
- Not found: HW-307 drawing, hole positions for Most's board, and screw-terminal offset from the board edge. Measure. No Songle PDF was opened.

## Q5. DC-022 barrel jack, screw terminals, WAGO lever connectors

### Takeaway
None of these are datasheet-verified. DC-022 panel-hole figures conflict (7.8 mm for DC-022B versus 11-12 mm for DC-022), so print a test coupon or measure the thread. KF301 5.08 mm 2-pin blocks are commonly listed as 10 x 7.5 x 14 mm. Genuine WAGO 221-412 is about 13.1 x 8.3 x 18.6 mm, but Most sells "PCT-212" at 21 x 12.5 x 14.5 mm.

### Cited Findings
- Most DC-022: 5.5/2.1 mm, 0.5 A. No hole or thread is given (VARIANT MATCHED) — [Most](https://mostelectronic.com/shop/connectors/power-connectors/female-dc-power-2-1mm-connector-for-box-plastic/)
- DC-022 panel hole sizes conflict (all REFERENCE ONLY):
  - DC-022B: 7.8 mm hole, panel up to 3 mm thick — [Sigmanortec](https://sigmanortec.ro/en/panel-female-jack-55x21mm-dc-022b)
  - DC-022: "11 mm to 12 mm" hole — [Makerlab](https://www.makerlab.ph/products/5pcs-dc-022-with-nut-female-dc-power-crown-jack-5-5-2-1mm)
  - DC-022: 12 mm cut-out, panel up to 7 mm — [Hubtronics](https://hubtronics.in/dc-022-dc-jack)
  - No source gives a thread spec.
- KF301-2P: 5.08 mm pitch, 10 L x 7.5 W x 14 H mm, 16 A, M2.5 screws, PBT UL94V-0 (REFERENCE ONLY, retailer data). Another listing gives 10 x 10 x 18 mm for a different variant — [Sigmanortec KF301-2P](https://sigmanortec.ro/en/pcb-connector-2-pins-kf301-2p-5mm); [Robojax](https://robojax.com/products.php?pid=726); [Grobotronics](https://grobotronics.com/screw-terminals-5.08mm-pitch-2-pin-16a-green.html?sl=en)
- Most's "5mm" 2-pin block is actually listed as CY350-3.5 with 3.5 mm pitch in its spec table — [Most](https://mostelectronic.com/shop/connectors/terminal-blocks/2-pin-pcb-mount-screw-terminals-block-pitch-5mm-r-3/)
- Genuine WAGO 221-412 figures (REFERENCE ONLY, distributor data; WAGO's own datasheet was not opened):
  - W 13.1 x H 8.3 x D 18.6 mm — [Octopart](https://octopart.com/ja/part/wago/221-412); [Toolbrothers](https://toolbrothers.nl/en/products/wago-221-412-connecting-terminal-2-x-4-mm-100-pieces)
  - 13.2 x 18.6 x 8.4 mm with axes swapped — [element14](https://nz.element14.com/wago/221-412/terminal-block-pluggable-2pos/dp/2534732)
  - H 8.4 x W 13.2 x D 18.8 mm — [elektrikshop.de](https://www.elektrikshop.de/compact-2-leiter-klemme-mit-betaetigungshebel-221-412-wago.html)
- Most's "WAGO PCT-212": 21 x 12.5 x 14.5 mm, 0.08-2.5 mm², strip 9-10 mm (VARIANT MATCHED) — [Most](https://mostelectronic.com/shop/connectors/wago-pct-212-parallel-wire-connector-2-pin/)

### Inferences
- For the DC-022 bought from Most, measure the thread OD and print a test coupon with 8, 11 and 12 mm holes. The "with nut" DC-022 variants in these listings mostly quote 11-12 mm.
- Most's pluggable "5.08 mm" blocks are likely a better match for a 5.08 mm grid than the misnamed "5mm" CY350-3.5 block.
- Lever connectors are usually held in a printed pocket or with a zip-tie slot, not screwed down. Size pockets to the Most PCT figures plus about 0.3 mm clearance (judgement).

### Gaps
- No manufacturer drawings were obtained for DC-022, KF301 (Xinya etc.) or the WAGO 221 series this session. Height and wire-entry axis for KF301 are not confirmed. Measure every connector before committing the plate.
