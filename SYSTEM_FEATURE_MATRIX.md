# System feature matrix

Classification on 10 Nov 2026: **Implemented and verified** (tested in software and/or recorded on hardware) · **Implemented, not fully tested** · **Partially implemented** · **Prototype** · **Proposed** · **Deprecated** · **Unverified**.

| Capability | Status | Evidence |
|---|---|---|
| Two-factor door access (QR/NFC + fingerprint/face) | Implemented and verified | Bench log 5 Oct 2026; access audit records; backend tests |
| Fail-secure lock, relay boot fix | Implemented and verified | Owner test 8 Nov 2026 |
| Booking with time-bound QR credentials | Implemented and verified | Backend tests; portal |
| Session traceability (entry; exit only when observed) | Implemented and verified | Backend tests; trace pages |
| Camera person detection (YOLO26s) and tracking | Implemented and verified | 297 vision tests; benchmark; lab recording |
| Access ↔ camera cross-check (no door entry, more seen than entered) | Implemented and verified | Lab recording 7 Oct 2026; backend tests |
| Identity association (door, face, look evidence) | Implemented, not fully tested | Lab runs; accuracy not formally measured |
| Two-camera name sharing | Implemented, not fully tested | Simulation tests only |
| Equipment zones (moved, missing, motion) | Implemented and verified | Vision tests; lab |
| Environment monitoring (DHT22, PIR, MQ-2, flame) | Implemented and verified (bench) | Bench log 5 Oct 2026; range/distance not measured |
| Consumables weighing and counting | Implemented, not fully tested | Device used; calibration table empty |
| Reusables NFC check-out with servo lid | Prototype | Partial bench run 9 Oct 2026 |
| Unified portal (operations, labs, security, equipment, inventory, reports) | Implemented and verified | Frontend build; e2e scripts; lab use |
| Lab PC monitoring, screen wall, screen sharing, exam mode | Implemented, not fully tested | 40 PC-agent tests; lab day 4 Nov 2026; PowerShell kit only syntax-checked |
| UR5e digital twin (read-only) | Implemented and verified | Lab recording and photo, Oct 2026; 43 robot tests |
| FANUC twin (read-only) | Implemented, live-verified once | 14 Oct 2026 at 192.168.1.100, about 3 samples/s; J2/J3 coupling to confirm by pose |
| Robot motion control | Proposed (guarded, unavailable) | Adapters stay UNAVAILABLE until commissioning sign-off |
| AI lab assistant (local, tool-calling, instant answers) | Implemented and verified | Backend tests; local runs |
| Knowledge agent over the Obsidian vault | Implemented and verified | 49 tests; live answer 8 Nov 2026 |
| Voice in/out (local) | Implemented, not fully tested | Local runs; offline run pending |
| n8n automation (23 workflows) | Implemented and verified (exports, endpoints) | Endpoint cross-check; earlier live runs |
| Phone Scan the lab (AR overlays) | Implemented, not fully tested | Headless phone-size test; real phone not measured |
| Offline operation (no internet) | Implemented, not fully tested | Code review; offline run pending |
| OPC UA server | Partially implemented | Loopback only |
| PLC integration, MQTT broker, Raspberry Pi | Proposed (early design only) | Not in the running system |
