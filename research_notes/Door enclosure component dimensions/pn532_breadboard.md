# Door enclosure component dimensions: PN532 NFC V3 (Ekostra) and 170-tie-point mini breadboard (Most Electronics)

Research date: 2026-10-20. Labels used on every number:
- DATASHEET VERIFIED: stated by the original designer (Elechouse) in its manual or CAD file.
- VARIANT MATCHED: stated by the exact store listing for the part the owner bought (Ekostra / Most Electronics).
- REFERENCE ONLY: from another seller or a related model (for example the Elechouse V4 CAD, which Elechouse says has the same shape and holes as V3).
- UNVERIFIED: inference or anecdote; needs a caliper check on the owner's board.

Important correction to the brief: the Elechouse PN532 V3 user manual (Rev B, Nov 2013) does NOT contain a dimension drawing. It gives only the overall size. The only dimensioned source found is the Elechouse V4 STEP model (V4 is declared a drop-in replacement with the same shape and mounting holes). Hole positions below come from that STEP file, which I parsed.

## 1. PN532 NFC RFID Module V3: exact store listing and dimensions per source

### Takeaway
Ekostra sells "PN532 NFC RFID Read/Write Module V3 Kit" (SKU EK506, 265.00 EGP) and lists 42.7 x 40.4 x 4 (mm, though the site's unit label says "cm"), matching the Elechouse V3 manual. The Elechouse V4 CAD model has the same 42.68 x 40.38 mm outline with R3.39 corners and two diagonally opposite 3.05 mm holes. This gives the best hole data available, but it should be checked with calipers on the red Ekostra clone.

### Cited Findings
- Ekostra listing: "PN532 NFC RFID Read/Write Module V3 Kit", product id 1961, SKU EK506, price 26500 in minor units (265.00 EGP), in stock, weight 6 g. Dimensions field: length 42.7, width 40.4, height 4. The site renders this as "42,7 x 40,4 x 4 cm", which is clearly a unit-label error in the store; the numbers are the Elechouse mm figures. Mode selection: "SMD toggle switch". Communication distance: "5cm ~ 7cm". The description also says "Built-in PCB Antenna, with 4cm~6cm communication distance" (the text contradicts itself). Package: "1 x PN532 NFC RFID Wireless Module V3". The listing gives no colour, hole size or drawing. VARIANT MATCHED. Read from the WooCommerce store API, because the HTML page is behind a Cloudflare challenge — [Ekostra product](https://ekostra.com/product/pn532-nfc-rfid-read-write-module-v3-kit/); [Ekostra store API](https://ekostra.com/wp-json/wc/store/products?search=pn532)
- Elechouse V3 manual: "Smaller: the size now is as small as 42.7mm*40.4mm*4mm". The same manual, under Features, also says "Small size: 43mm*41mm*4mm" (a rounded figure). It has no dimension drawing, no hole data and no PCB thickness. Revision B, Nov. 5th 2013, "Modify information for V3". DATASHEET VERIFIED (overall size only) — [Elechouse PN532 V3 manual PDF](https://www.elechouse.com/elechouse/images/product/PN532_module_V3/PN532_%20Manual_V3.pdf) (text read from the identical copy at [Components101](https://components101.com/sites/default/files/component_datasheet/PN532%20NFC%20RFID%20Module%20Datasheet.pdf))
- Elechouse V3 manual, mode switch (2-channel SMD toggle): HSU = OFF/OFF (default), I2C = ON/OFF, SPI = OFF/ON. The I2C and HSU signals share one header (I2C labels printed on the front, HSU labels on the back). There is also a 1.27 mm-pitch hole row for the less-used pins. "The bended male pins come with the NFC board", meaning right-angle headers are supplied loose. "make sure the wires go across the antenna lines in 90 degree". DATASHEET VERIFIED — [Elechouse V3 manual](https://www.elechouse.com/elechouse/images/product/PN532_module_V3/PN532_%20Manual_V3.pdf)
- Elechouse V4 product page: V4 is "a drop-in replacement for V3" with the "same shape, same mounting holes, same interface". It links a 3D model, ELECHOUSE_PN532_V4_3D.zip. REFERENCE ONLY (manufacturer claim) — [Elechouse PN532 V4](https://www.elechouse.com/product/pn532-nfc-rfid-module-v4/)
- Measurements from the Elechouse V4 STEP file (3D_NFC_EASY_SHIELD_V4.1_2025-12-13.step, units mm; parsed from the "Board" solid). Coordinates are measured from the board's top-left corner as the model lies, with X to the right and Y downward. REFERENCE ONLY for the red V3 clone — [Elechouse V4 3D zip](https://www.elechouse.com/wp-content/uploads/2022/04/ELECHOUSE_PN532_V4_3D.zip)
  - PCB outline: 42.68 x 40.38 mm, corner radius 3.39 mm.
  - Board solid thickness in the model: 0.41 mm. This looks like EasyEDA's export of the core or a placeholder, not a believable 1.0-1.6 mm FR4 board. Do not use it as the PCB thickness.
  - Mounting holes: 2 holes, 3.048 mm diameter (the model value; nominally 3 mm, so M2.5 or M3 clearance), placed on diagonally opposite corners:
    - Hole A centre at X 7.39, Y 7.59 (7.39 mm from the left edge, 7.59 mm from the top edge).
    - Hole B centre at X 35.19, Y 32.79 (7.49 mm from the right edge, 7.59 mm from the bottom edge).
    - Centre-to-centre spacing: dX 27.80 mm, dY 25.20 mm, diagonal 37.52 mm.
    - Each hole is ringed by 10 vias of 0.56 mm diameter (a copper keep-out ring, so use plastic or nylon standoffs, about 6 mm OD maximum).
  - 8-pin header row (0.81 mm holes, 2.54 mm pitch) parallel to the top edge, 6.49 mm in from it, with pin centres from X 15.10 to X 32.88. This is the SPI header (V3 labels: SCK, MISO, MOSI, SS, VCC, GND, IRQ, RSTO).
  - 4-pin header column (0.81 mm holes, 2.54 mm pitch) parallel to the left edge, 6.39 mm in from it, with pin centres from Y 16.38 to Y 24.00. This is the I2C/HSU header (GND, VCC, SDA/TXD, SCL/RXD).
  - 10-hole row at 1.27 mm pitch (0.70 mm holes) at Y 30.73, X 17.96 to 29.39 (the less-used pins).
- Bastelgarage (red V3 kit listing): "Dimension PN532 module: 43 x 40 x 3.5 mm", "Diameter mounting holes: 3mm", "Color: Red". REFERENCE ONLY — [Bastelgarage](https://www.bastelgarage.ch/pn532-nfc-rfid-module-v3-set-with-rfid-card-and-key)
- EasyElecModule: 42.7 x 40.5 mm in its dimensions table and 42.7 x 40.4 mm in its datasheet section, H 4 mm. REFERENCE ONLY — [EasyElecModule](https://easyelecmodule.com/product/pn532-nfc-rfid-v3-module/)
- Read distance: Elechouse V3 gives 5-7 cm (up from 4-6 cm on V2), with flexible Mifare S50/Ultralight tags up to 5 cm. The V4 page's table lists V3 Mifare at 5-6 cm and V4 at 6-8 cm (PVC cards). DATASHEET VERIFIED (free air) — [V3 manual](https://www.elechouse.com/elechouse/images/product/PN532_module_V3/PN532_%20Manual_V3.pdf); [V4 page](https://www.elechouse.com/product/pn532-nfc-rfid-module-v4/)
- Plastic in front of the antenna: no measured PLA-attenuation data was found. One enclosure designer uses 0.5 mm top and bottom walls "for best RFID read" (anecdote) — [Printables PN532 enclosure](https://www.printables.com/model/101157-pn532-enclosure-with-wirecable-access); [MyMiniFactory copy](https://www.myminifactory.com/object/3d-print-pn532-enclosure-with-cable-access-190174)
- The Fritzing community part for the Elechouse V3 is wrong to scale (its header pitch works out to about 2.1 mm instead of 2.54 mm) and has no mounting holes, so it is not usable for the enclosure — [Fritzing forum part](https://forum.fritzing.org/t/pn532-elechouse-rfid-nfc-module-v3-pn532-elechouse-rfid-nfc-module/28418)

### Inferences
- The overall figures converge (42.7 x 40.4 DATASHEET VERIFIED; CAD 42.68 x 40.38). Design the pocket at about 43.4 x 41.1 mm (0.3-0.4 mm clearance per side for FDM). UNVERIFIED tolerance; standard practice.
- "4 mm" (Elechouse) and "3.5 mm" (Bastelgarage) are the board's height with SMD parts and no headers soldered. With the supplied right-angle headers, the pins stick out sideways past the board edge rather than adding height. With straight headers, add the header length. No source gives this, so measure it. UNVERIFIED.
- With headers on the top edge (8-pin) and the left edge (4-pin), the antenna loop is most likely in the remaining right and lower area. The manual's advice to cross antenna lines at 90 degrees shows that the header wires run over antenna copper. The exact antenna footprint was not extracted. UNVERIFIED; check against the owner's board or a photo.
- PLA and PETG are RF-transparent at 13.56 MHz. Read range loss is driven by the air gap more than by the plastic, so the cover thickness counts directly against the 5-7 cm range. A 1.0-2.0 mm PLA face (giving a total gap of roughly 2-3 mm) should leave several cm of range. That is engineering judgement, not a measurement: UNVERIFIED. Keep metal (screws, ESP32 shield, relay, lock) away from the antenna face.
- Red clone (HW-147) versus blue boards: no source with clone-specific hole data was found. Both Bastelgarage (red) and Elechouse say "3 mm" holes, but spacing on a clone may shift by fractions of a mm, so use slotted holes or 0.5 mm oversize. UNVERIFIED.

### Gaps
- No manufacturer 2D drawing for V3. The holes, header positions and corner radius come from the V4 CAD file only.
- PCB thickness: not stated anywhere; the CAD's 0.41 mm is suspect. Measure it (it is probably 1.0-1.6 mm).
- Total height with straight versus right-angle headers, and the location of the DIP switch: not extracted from the CAD (the component placement under the "SW1" part was not resolved to board coordinates).
- Antenna copper area and its keep-out: not extracted.
- No measured read range through PLA of a given thickness.
- The Ekostra photo (wp-content/uploads/2026/05/1737709779_pn53220nfc20...jpg) was not inspected for the HW-147 marking.

## 2. Breadboard 170 Tie Point (Most Electronics): exact listing and dimensions

### Takeaway
Most Electronics lists "Breadboard 170-Tie Point" (SKU ME-29142, 10.00 EGP, six colours) with an adhesive back and "can be connected together". It gives no dimensions, but its image file is named "...SYB-170...", so it is the generic SYB-170. SYB-170 sizes vary between sellers from 45 x 34.5 to 48 x 36.5 mm, with heights of 8.5-10 mm. Measure the actual board.

### Cited Findings
- Most Electronics listing: name "Breadboard 170-Tie Point", SKU ME-29142, price 10.00 EGP. Colours: Black, Blue, Peak green, Red, White, Yellow. "Because it has an adhesive backing, the breadboard can be mounted on surfaces or inside enclosures. Also, multiple units can be connected together". The dimension fields are empty. The image is Breadboard-170-Tie-points-SYB-170-300x300-1.jpg. The listing does not mention mounting holes or dovetails. VARIANT MATCHED (adhesive back, joinable); dimensions not given — [Most Electronics product](https://mostelectronic.com/shop/read-boards-accessories/breadboard-170-tie-point/); [store API](https://mostelectronic.com/wp-json/wc/store/products?search=breadboard%20170)
- Grobotronics SYB-170-BK: "47 x 36.5 x 10mm", "peel and stick adhesive backing". REFERENCE ONLY — [Grobotronics](https://grobotronics.com/breadboard-170-black.html?sl=en)
- Pololu 170-point breadboard: 1.85" x 1.38" (47.0 x 35.0 mm), per a search-result snippet; the page itself was not fetched. REFERENCE ONLY — [DigiKey Pololu 1491](https://www.digikey.de/en/products/detail/pololu/1491/11586863)
- Phipps Electronics SYB-170: 45 x 34.5 x 8.5 mm with M2 screw holes, per a snippet; the page returned 403. REFERENCE ONLY — [Phipps](https://www.phippselectronics.com/product/syb-170-white-mini-solderless-breadboard-pack-of-3/)
- Robu.in SYB-170: 48 x 35 x 10 mm with two M2 mounting holes, per a snippet. REFERENCE ONLY — [Robu.in](https://st.robu.in/?p=52916)
- Sigmanortec SYB-170: about 47 x 35 mm, joinable in series along its edges, per a snippet; the page returned 403. REFERENCE ONLY — [Sigmanortec](https://sigmanortec.ro/en/breadboard-170-points-syb-170-red)
- Typical layout: 17 columns x 10 holes (A-J) split by a centre channel, 2.54 mm pitch, no power rails, per a search summary. REFERENCE ONLY — [Core Electronics](https://core-electronics.com.au/170-point-breadboard-red.html.plain.md)
- Pololu's larger breadboards use "tabs" on two sides and "compatible slots" on the other two (an interlocking dovetail style), shown on its 400-point page. This is a related model, not the 170 — [Pololu 351](https://www.pololu.com/product/351)

### Inferences
- The likely physical board is about 46-47 x 34.5-35 x 8.5-10 mm. Pocket it at about 48 x 36.5 mm with 10 mm depth, or mount it with its adhesive on a flat floor. UNVERIFIED until measured.
- The "can be connected together" wording, plus the SYB-170 type, implies dovetail tabs and slots on the short and long sides, which make the outer footprint about 1 mm larger. Leave clearance or trim the tabs. UNVERIFIED.
- Whether the owner's unit has the two small M2 corner holes some SYB-170 batches have is unknown. Do not design around screws without checking.

### Gaps
- No manufacturer drawing for SYB-170 was found.
- Most Electronics gives no dimensions, hole data or dovetail details.
- The Pololu, Phipps, Robu and Sigmanortec figures come from search snippets (several pages returned 403), so they are not independently fetched.
