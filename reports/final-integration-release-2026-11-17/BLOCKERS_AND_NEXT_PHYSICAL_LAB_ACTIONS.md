# Blockers and next physical lab actions

Machine-readable list: `blockers.csv`.

## P0: owner, before anyone else uses the portal
1. **Change the two published default passwords** (admin@giu-uni.de, ramy@giu-uni.de):
   `docker compose exec backend python set_password.py <email>`. Verified still in use on 18 Nov.

## GIU IT administrator
2. **S2PC136 firewall:** allow inbound on the relay ports (from the Smart_Lab / lab subnet only) so PC_01..PC_16 reach the relay. Then run `Test-NetConnection 10.30.11.136 -Port 8000` from PC_01. Do not report student PCs online before this passes.
3. **GPO / SmartScreen** prompt for the unsigned kit scripts on fresh lab PCs: "Run with PowerShell" per the deployment guide, or IT whitelisting.

## Next lab visit (hardware, owner present)
4. **Flash firmware** (source in this release, compiled on core 3.3.12; NOT flashed). For each board: read the current image back first with esptool, flash, then check the boot log and the portal.
   - BIN_NODE_1 (SmartLab_Consumable_Bin): HTTP retry backoff.
   - REUSE_BIN_1 (SmartLab_Reusable_Bin_Modular): Wi-Fi sleep off after reconnect.
   - **ESP32-CAM: build with core 3.2.1 only** (3.3.12 breaks camera init). Core 3.2.1 is no longer installed on this laptop; installing it needs the owner's OK. The known-good image is backups/esp32cam-20261018/esp32cam_core321_kept.merged.bin.
   - Master portal-1.1 (NFC recovery) remains the owner's door decision.
5. **Camera 1 floor anchor:** add a point near (x=1.4, y=3.2), re-calibrate (residual 0.50 m now), then the live acceptance tests 1-3, 6 and 8 in the camera audit.
6. **Live two-camera run** with both services (:5100 / :5101) and labelled ground truth, to measure ID switches after 25 s / 3 min. Simulation says 1 switch and 1 fragment each.
7. **Door / tablet / TFT** checks: RFID, QR, fingerprint, face, relay, reed, buzzer, LEDs, tablet outage screen.
8. **UR5e / FANUC live telemetry** and twin staleness display (read-only).
9. **Device-sample-to-portal latency** (needs the nodes); software push-to-paint is 26 ms median.
10. **Legacy sketch** firmware/SmartLab_Reusable_Bin uses the same REUSE_BIN_1 id with LAB_ID "BENCH". Never flash it; the Modular project is the current one. Consider marking the folder legacy.

## Owner (software, not allowed for agents)
11. **n8n:** add retryOnFail on the "Check In Backend" nodes. Keep the Knowledge workflows off while the knowledge service is off.
12. **Push** the release branch when satisfied. Agents do not push.
