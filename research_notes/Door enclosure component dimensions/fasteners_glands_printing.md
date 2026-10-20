# Fasteners, cable glands and FDM printing tolerances for the 3D-printed door enclosure (170 x 210 x 90 mm, PLA/PETG, 3 mm wall)

Research date 2026-10-20. Confidence labels: DATASHEET VERIFIED (manufacturer or reseller copy of the manufacturer table), REFERENCE ONLY (secondary guide or table), UNVERIFIED (not confirmed by a fetched source; general knowledge only, check before use).

## Q1. M3 heat-set inserts, M3 clearance holes, and screw head diameters

### Takeaway
For CNC Kitchen / Ruthex-type M3 x 5.7 x 4.6 inserts, use a 4.0 mm straight hole about 1 mm deeper than the insert (about 6.7 mm blind), with at least 1.6 mm of wall around it. That gives a boss of at least 7.2 mm OD; 8 mm is a sensible design value. M3 clearance holes are 3.2 / 3.4 / 3.6 mm (close / medium / free). Heads: ISO 4762 is 5.5 mm and ISO 7380 is 5.7 mm. Sources disagree on the ISO 10642 countersunk head size.

### Cited Findings
- CNC Kitchen table (DATASHEET VERIFIED, reproduced on the 3DJake product page). M3 Standard: L 5.7, insert D1 4.6, centre point D2 3.9, **hole D3 4.0, min wall W 1.6**. M3 Short: L 3.0, 4.6 / 3.9 / **4.0 / 1.6**. M3 "Voron": L 4.0, D1 5.0, D2 4.25, **hole 4.4, wall 1.3** — [3DJake CNC Kitchen M3 Standard](https://www.3djake.com/cnc-kitchen/threaded-inserts-m3-standard); [3DJake M3 Short](https://3djake.ch/en-CH/cnc-kitchen/threaded-inserts-m3-short)
- A reseller lists the "Threaded Insert M3 - 5.7x4.6mm" as length 5.7 mm, OD 4.6 mm (REFERENCE ONLY) — [Grobotronics](https://grobotronics.com/threaded-insert-m3-5-7x4-6mm.html?sl=en)
- CNC Kitchen blog: blind holes should be "slightly deeper than the length of the insert (approx. 1 mm)". Through holes need not be longer than the insert. Holes should be straight (not tapered) and normally need no chamfer. Their M3 hole-size test part spans 4.0–4.4 mm in CAD because printed holes come out undersize, so test on your own printer (REFERENCE ONLY, manufacturer blog) — [CNC Kitchen tips for heat-set inserts](https://www.cnckitchen.com/blog/tipps-amp-tricks-fr-gewindeeinstze-im-3d-druck-3awey); test parts: [Printables hole-size test](https://www.printables.com/model/1648510-hole-size-test-for-heat-set-inserts)
- Installation: heat the insert 10–20 °C above the print temperature, melt about 90 % in with the iron, then press the rest flush with a flat tool (DATASHEET VERIFIED, 3DJake/CNC Kitchen page) — [3DJake](https://www.3djake.com/cnc-kitchen/threaded-inserts-m3-standard)
- Another supplier advises a finished hole of about 4–4.5 mm for M3 heat-setting (REFERENCE ONLY) — [Gogo:Tronics](https://sparks.gogo.co.nz/catalog/Hardware-270/M3-3mm-Thread-Insert-Nut-Extra-Grip-Centering-Heat-Set-10-Inserts--Pack-903.html)
- Generic M3 knurled inserts vary in size: one 150-piece kit lists a 4.9 mm OD ([Grobotronics kit](https://grobotronics.com/threaded-insert-assortment-kit-m3-150pcs.html?sl=en)), and another listing gives 6 mm long, 5 mm OD ([Lowe's](https://www.lowes.com/pd/-/8273518)) (REFERENCE ONLY)
- JLC3DP's insert service uses a different, smaller insert (OD 4.0, L 3.0, hole 3.6) and requires a 3.0 mm minimum wall around the insert hole (REFERENCE ONLY, vendor rule) — [JLC3DP threaded insert service](https://jlc3dp.com/help/article/threaded-insert-service)
- The Ruthex technical-data page could not be fetched (404). I found no Ruthex datasheet numbers directly. One retailer lists a Ruthex M3 at 4.6 mm OD, and another gives a conflicting "3 mm" OD (UNVERIFIED) — search result summary of [Grobotronics Ruthex M3](https://grobotronics.com/ruthex-threaded-insert-m3-pack-of-70.html?sl=en)
- M3 clearance holes 3.2 / 3.4 / 3.6 mm (close / medium / free) and M4 4.3 / 4.5 / 4.8 mm. The source does not map its column names to the ISO 273 "fine/medium/coarse" names (REFERENCE ONLY, secondary table) — [Optimas tapping sizes](https://optimas.com/technical-resources/tapping-sizes/). ISO 273:1979 itself is paywalled; ISO says it was last reviewed and confirmed in 2024 — [ISO 273](https://www.iso.org/standard/4183.html)
- ISO 7380 M3 button head: dk 5.7 mm, k 1.65 mm (REFERENCE ONLY) — [Engineers Edge ISO 7380](https://engineersedge.com/iso_socket_button_head.htm)
- ISO 4762 / DIN 912 M3 socket head cap: dk 5.5 mm, k 3.0 mm (DATASHEET VERIFIED, supplier spec) — [Accu ISO 4762 M3x8](https://accu-components.com/fr/vis-a-tete-cylindrique-a-douille-metrique/3818-SSCF-M3-8-A2)
- ISO 10642 M3 countersunk: a Würth listing gives head diameter 5.81 mm and height 1.86 mm. The commonly quoted 6.72 mm (the theoretical sharp-edge maximum) was NOT confirmed by a fetched source. ISO 10642 heads differ from DIN 7991 (CONFLICT, REFERENCE ONLY) — [Würth ISO 10642 M3x6](https://eshop.wurth.ae/Countersunk-screw-with-hexagon-socket-head-ISO-10642-steel-88-plain-SCR-ISO10642-088-HS2-M3X6/008703%206.sku/en/US/AED)

### Inferences
- Design values (inferred from the above). Insert hole Ø4.0 mm in CAD (try 4.0–4.2 if your printer runs small), depth 6.7–7.0 mm blind. Boss OD = 4.6 + 2 x 1.6 = 7.8 mm minimum, so use 8 mm, plus a fillet or ribs to the wall. If the generic Most Electronics M3 inserts turn out to be 5 mm OD, measure them first. A wider insert would need a hole of about 4.4 mm and a boss of about 8–9 mm.
- Lid screws into the inserts: clearance hole 3.4 mm (medium) works well in FDM, because printed holes shrink. Counterbore for ISO 4762: Ø6.0–6.5 mm x 3.2 mm deep (dk 5.5 + clearance). Counterbore for ISO 7380: Ø6.2–6.5 mm x 1.9 mm. For countersunk heads, model a 90° countersink to about Ø6.5 mm and test-fit, because the head sizes conflict.
- A 3 mm wall cannot fully house a 5.7 mm insert. The inserts belong in bosses or corner pillars, not the plain wall.

### Gaps
- Ruthex's own M3 datasheet values (hole, depth, wall) were not retrieved; the page returned 404.
- McMaster 94180A333 page returned no content.
- ISO 273 primary table (paywalled) and an authoritative ISO 10642 dk value were not obtained.

## Q2. Cable glands PG7, PG9, M12x1.5, M16x1.5 (nylon)

### Takeaway
Panel holes: PG7 12.5–12.8 mm, PG9 15.2–15.5 mm, M12 12.0–12.3 mm, M16 16.0–16.3 mm. Cable ranges: about 3–6.5 mm (PG7 / M12) and 4–8 mm (PG9 / M16). Wrench sizes are 15–16 mm (PG7 / M12) and 19 mm (PG9 / M16). In a 3 mm printed wall, use a plain clearance hole plus the supplied locknut and sealing O-ring, not a printed thread.

### Cited Findings
- KLS8-0609L datasheet (DATASHEET VERIFIED):
  - PG7: cable 3–6.5 mm, mounting hole 12.5–12.8 mm, wrench 16 mm
  - PG9: cable 4–8 mm, hole 15.2–15.5 mm, wrench 19 mm
  - M12x1.5: cable 3–6.5 mm, hole 12–12.3 mm, wrench 16 mm
  - M16x1.5: cable 4–8 mm, hole 16–16.3 mm, wrench 19 mm

  Source: [KLS datasheet (Ozdisan)](https://cdn.ozdisan.com/ETicaret_Dosya/513402_8698866.PDF)
- The joint length "H" disagrees between KLS sheets (PG7 22 mm vs 65 mm), so check the drawing of the exact part (CONFLICT) — [KLS8-0627 (ChipDip)](https://static.chipdip.ru/lib/163/DOC045163496.pdf)
- RND 465 series (DATASHEET VERIFIED): M12 3–6.5 mm / bore 12.3. M16 4–8 / 16.3. PG7 3–6.5 / 12.8. PG9 4–8 / 15.5. Spanner 15/16 mm for PG7 and M12, 19 mm for PG9 and M16 — [RND cable glands TDS](https://www.triopak.fi/files/product/RND%20Components/RND-cable-glands-strain-p10_eng_tds.pdf)
- RS PRO EGRNL (DATASHEET VERIFIED): PG7 hole 12.5–12.8 mm, cable 3.5–6 mm. PG9 hole 15.2–15.5 mm, cable 4–8 mm — [RS PRO datasheet](https://docs.rs-online.com/0389/A700000007247832.pdf)
- ABB CC-PG7-G nylon gland, IP68: cable 3–6.5 mm, **thread length 8 mm** — [ABB eCatalog](https://empower.abb.com/ecatalog/ec/EN_NA/p/CC-PG7-G)
- Clamping ranges on other PG7 glands (REFERENCE ONLY):
  - Bud IPG-2227: 3.05–6.1 mm, IP66 — [Digi-Key](https://www.digikey.com/en/products/detail/bud-industries/IPG-2227-BPG/5291516)
  - Alpha Wire PPS7: 3–6.5 mm, includes gasket and locknut — [Digi-Key](https://www.digikey.com/en/products/detail/alpha-wire/PPS7-BK080/8552693)
  - Adafruit PG-7: 3.0–4.3 mm (0.118–0.169 in) — [Adafruit 762](https://www.adafruit.com/products/762)

### Inferences
- The thread length (about 8 mm for PG7) is much longer than a 3 mm wall, so the locknut will have plenty of thread to clamp on. A printed internal PG/M thread in 3 mm of PLA would give only about 2 thread turns at 1.5 mm pitch (PG7 pitch is about 1.27 mm, UNVERIFIED) and would be weak and leaky. So use a clearance hole plus the locknut, with the O-ring on the outside face.
- Model the holes at the top of each range, plus about 0.2 mm for FDM shrink: PG7 Ø12.9–13.0, PG9 Ø15.6, M12 Ø12.4, M16 Ø16.4. Leave a flat spot-face around each hole at least one wrench size across (16 or 19 mm), and more if possible, so the nut and O-ring seat flat.
- Prefer M12 or M16 metric glands for new designs. The metric hole is simply the thread size, and the thread has the same pitch across sizes.

### Gaps
- No Lapp Skintop or Jacob primary datasheet was fetched; the values above come from KLS, RND, RS PRO and ABB.
- Locknut across-flats for the nylon locknuts was not separately confirmed (it is usually close to the gland wrench size; UNVERIFIED).

## Q3. Does Most Electronics (mostelectronic.com) sell cable glands, heat-set inserts and M3 standoffs?

### Takeaway
Yes for M3 knurled brass inserts, M3 copper hex spacers and M3 screws. No cable glands turned up in the site search ("cable gland" returned only cables and connectors). The insert listing gives no dimensions, so measure the inserts before finalising the hole size.

### Cited Findings
- "M3 Knurled Brass Threaded Insert Nut", 5.00 EGP (was 7.78). The search listing shows no length or OD. M4 (6.00 EGP) and M5 (6.99 EGP) are also sold — [Most Electronics product](https://mostelectronic.com/shop/cnc-3d-printer-parts/m3-knurled-brass-threaded-insert-nut/); [site search "insert"](https://mostelectronic.com/?s=insert&post_type=product)
- Copper M/F hex spacers: M3x6 (5.00 EGP), M3x10 (5.50), M3x15 (6.50), M3x20 (7.50), M3x30 (8.00) — [M3x6](https://mostelectronic.com/shop/pcb/hex-spacer-m3x6-m-f-copper/), [M3x10](https://mostelectronic.com/shop/pcb/hex-spacer-m3x10-m-f-copper/), [M3x15](https://mostelectronic.com/shop/pcb/spacers/hex-spacer-m3x15-m-f-copper/), [M3x20](https://mostelectronic.com/shop/pcb/spacers/hex-spacer-m3x20-m-f-copper/), [M3x30](https://mostelectronic.com/shop/pcb/spacers/hex-spacer-m3x30-m-f-copper/)
- PLA+ printed hex spacers M3x30 / x40 / x50 (2.00–3.25 EGP) — [M3x30 PLA](https://mostelectronic.com/shop/3d-printed-products/hex-spacer-m3x30-pla/)
- M3 screws: M3x10 (+ head, 1.25 EGP); Allen head M3x12 (1.25), M3x15, M3x20 (1.50), M3x25 (1.75); M3x30 (+ head, 1.75). Also M2x10/12/16/20 and M5x12 Allen. The listing does not say which head standard (ISO 4762 vs other) — [M3x12](https://mostelectronic.com/shop/cnc-3d-printer-parts/screws-fastners/screw-m3x12mm-hexagonal-head/), [M3x20](https://mostelectronic.com/shop/cnc-3d-printer-parts/screws-fastners/screw-m3x20mm-hexagonal-head/); the "Screws & fastners" category holds 63 items per [site search](https://mostelectronic.com/?s=insert&post_type=product)
- Search for "cable gland" on the site returned 159 results, none of them glands (cables, MC4 connectors, drag chain 10x10 mm) — [site search](https://mostelectronic.com/?s=cable+gland&post_type=product)

### Inferences
- Cable glands will probably have to come from electrical or industrial suppliers in Egypt (glands are standard electrical-panel stock). That is not confirmed by a fetched source (UNVERIFIED). A fallback is a printed strain-relief grommet or a rubber grommet.
- Hex spacer across-flats (usually 5 mm for M3 brass spacers) is not stated on the site (UNVERIFIED); measure before modelling PCB bosses.

### Gaps
- Only the first page of results was checked for screws. Later pages (2–7) may hold M3 nuts, M4 screws or other spacer lengths.
- The insert's length and OD are not published; physical measurement is needed.

## Q4. FDM tolerances, text, elephant foot, orientation (0.4 mm nozzle)

### Takeaway
Sources disagree on fit clearances: Xometry gives 0.2–0.3 mm for a sliding fit, while JLC3DP's FDM minimum assembly clearance is 0.5 mm. Vertical holes print undersize by an amount that depends on printer, material and size, so print a test coupon. Text: embossed at least 0.8 mm stroke and 0.5 mm high; engraved at least 1.0 mm stroke and 0.5–1.0 mm deep. Chamfer bed-touching edges 45° against elephant foot.

### Cited Findings
- Xometry FDM guide (third-party-hosted, REFERENCE ONLY):
  - Clearances: about 0.5 mm for an "interference" fit and 0.2–0.3 mm for a sliding fit
  - Embossed text: 0.8 mm stroke, 0.5 mm height
  - Engraved text: 1.0 mm stroke, 0.5 mm depth

  Source: [xometry.pro guide](https://xometry.pro/en/?p=22061)
- JLC3DP: minimum assembly clearance 0.5 mm for FDM (0.2 mm for SLA). Engraved or embossed detail for FDM is 1.0 mm wide and 1.0 mm deep (REFERENCE ONLY) — [JLC3DP design guideline](https://jlc3dp.com/help/article/3d-printing-design-guideline)
- IPFL gives 0.8 mm minimum detail for FDM (REFERENCE ONLY) — [IPFL guidelines](https://www.ipfl.co.uk/3d-printing/design-guidelines/)
- With a 0.4 mm nozzle, strokes under about 0.5 mm are unreliable (REFERENCE ONLY, vendor blog) — [Sovol text/logo guide](https://www.sovol3d.com/blogs/news/3d-printing-text-and-logos-how-to-emboss-engrave-and-print-clean-details)
- Hubs (REFERENCE ONLY) — [Hubs FDM design guide](https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/):
  - Vertical holes print undersized, depending on "printer, slicing software, hole size and material". Print undersize and drill if critical; small holes are affected most.
  - Elephant foot can protrude beyond the specified size. Fix it with a 45° chamfer or radius on edges touching the bed.
  - Overhangs up to 45° need no support, and bridges under 5 mm sag little.
  - Rotating the part so horizontal holes become vertical removes the need for support.
  - Parts are weakest across layers, so align the build direction with the loads.

### Inferences
- Use about 0.2 mm per side for slide fits of printed-to-bought parts on a tuned printer, 0.3–0.5 mm for printed-to-printed parts, and print a hole-gauge coupon in the actual PLA or PETG first. The 0.2–0.4 mm range in the brief sits in the Xometry band but below the JLC3DP rule.
- Print the box open side up (the 170 x 210 face on the bed). Lid text that faces the bed should be engraved at least 0.6 mm deep with at least 1.0 mm strokes and at least 5 mm character height. Put it at least about 1 mm in from edges, or the elephant foot can close small counters. A 0.4–0.6 mm deep, 1 mm stroke is the practical minimum (inferred from 0.8–1.0 mm stroke guidance). Embossed text on top surfaces prints most cleanly.
- I found no source for "height at least 5 mm"; it is a reasonable legibility choice (UNVERIFIED).

### Gaps
- Prusa or Ultimaker knowledge-base pages were not fetched, so there is no Prusa number for elephant-foot size or hole compensation.
- No Protolabs FDM text figures were found.

## Q5. PN532 13.56 MHz read range through 1–3 mm PLA/PETG

### Takeaway
I found no measured data for PN532 range against plastic wall thickness. Non-metallic plastic is expected to be largely transparent at 13.56 MHz. Evidence is only anecdotal, so the design should be tested with 1, 2 and 3 mm coupons. Keep metal, including screws and inserts, away from the antenna.

### Cited Findings
- Adafruit PN532 board: the antenna is designed for up to about 10 cm, "the maximum range possible" with 13.56 MHz. It can be mounted behind a plastic plate with standoffs and read through a non-metal barrier; no thickness limit is given (REFERENCE ONLY) — [Mouser / Adafruit 789](https://www.mouser.com/new/adafruit/adafruit-pn532-rfid-nfc-controller-shield/)
- NXP PN5321 page lists a typical read distance of 70 mm (part and antenna dependent) — [NXP PN5321A3HN](https://nxp.com/part/PN5321A3HN)
- Hobbyist report (likely a clone module): about 1.5 in (about 38 mm) range, and "the plastic enclosure doesn't seem to stifle the connection at all"; thickness not stated (UNVERIFIED anecdote) — [Hackaday.io log](https://test.hackaday.io/project/183583-working-teeny-tiny-turntable/log/202360-1-15-22-got-the-nfc-reader-hooked-up)
- A printed PN532 enclosure keeps a 0.5 mm top and bottom layer "for best RFID read" while thickening the side walls (REFERENCE ONLY) — [Printables PN532 enclosure](https://www.printables.com/model/101157-pn532-enclosure-with-wirecable-access)

### Inferences
- Thin the wall over the antenna to about 1–1.5 mm (a pocket from the inside) as a low-cost margin. Keep brass inserts and screws more than about 10 mm from the antenna loop (UNVERIFIED rule of thumb).
- Hardware rule: report only measured read distances (owner's bring-up rule).

### Gaps
- No quantitative study of PLA or PETG attenuation at 13.56 MHz was found.

## Q6. Keyhole slot dimensions for wall-mounting with 4 mm screws

### Takeaway
I found no standard for keyhole slots. Sources show a narrow slot just wider than the shank (about 4–4.8 mm) and an entry hole larger than the head (about 9–9.5 mm). The screw head stands about 4–5 mm off the wall.

### Cited Findings
- A printed keyhole hanger takes screw heads up to 9 mm diameter with a 4 mm-wide key slot (REFERENCE ONLY) — [Thangs keyhole hanger](https://thangs.com/designer/peaberry/3d-model/Keyhole%2520Hanger%2520%2528Single%2520%2526%2520Double%2529-46684)
- CMT keyhole router bit: 3/8 in (9.5 mm) entry, 4.8 mm (3/16 in) slot, and an undercut channel under the surface (REFERENCE ONLY) — [Canadian Woodworker CMT bit](https://www.canadianwoodworker.com/?p=25553)
- Screw heads should stand about 4 mm off the wall ([AudioCodes Mediant 500L wall mounting](https://techdocs.audiocodes.com/session-border-controller-sbc/mediant-500l-sbc/hardware-manual/Content/HW/M500LSBC/Wall%20Mounting.htm)) or about 5 mm ([Vaisala manual](https://docs.vaisala.com/r/M211863EN-B/en-US/GUID-117F2FA4-E5AD-4C0A-AAA0-70EF96267850)) (REFERENCE ONLY)
- The screw should project by the thickness of the material around the narrow slot plus 1–2 mm (REFERENCE ONLY) — [EngineerFix keyhole hanger screws](https://engineerfix.com/how-to-install-keyhole-hanger-screws/)

### Inferences
- For 4 mm screws (pan or round heads of about 7–8 mm, UNVERIFIED), the suggested printed keyhole is:
  - entry Ø9–10 mm
  - slot width 4.6–5.0 mm (4 mm shank plus FDM clearance), slot length 10–12 mm
  - an undercut pocket behind the slot (head Ø + 1 mm wide, head height + 1 mm deep), so the box sits flush and the head cannot slip out
  - keep at least 3 mm of material either side of the slot (inferred from the 3 mm wall)

  Two keyholes about 120–150 mm apart near the top of the 210 mm side would spread the load. The slots should point downward.

### Gaps
- No manufacturer standard for keyhole geometry was found. The head diameter of local 4 mm wood or wall-plug screws must be measured.
