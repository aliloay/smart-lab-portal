# Owner actions and hardware test plan

Each step is one verified action at a time. Record what was actually measured; never use estimated numbers.

## A. At home (before GIU)

### A1. Door: 1N4007 flyback diode (F-24)

1. **Power down everything:** unplug the 12 V lock supply and the master's USB/5 V. Wait 30 s.
2. **Identify the lock coil terminals** at the relay output.
3. **Fit the 1N4007 in parallel with the lock coil:**
   - **Cathode (striped end) to the +12 V side.**
   - Anode to the side switched by the relay.
   - Keep the leads short, at the lock or directly at the relay contacts.
   - Insulate with heat-shrink.
4. **Check before powering:** a multimeter in diode mode across the coil should read about 0.5–0.7 V in one direction and open in the other.
5. **Power the master first, then the lock supply.** Confirm the TFT idle screen and that the portal shows MASTER_LAB01 online, rfid ✔.
6. **Test with the owner present, at the door, using the normal access flow only:**
   - Present a valid card, so the master opens the door.
   - Let it relock. Present the card again within 5 s.
   - Repeat **20 cycles**. Log the time, granted/denied, and any "RFID not responding" alert.
   - The serial logger on COM6 timestamps the events (`D:\SmartLabData\firmware_backup\master_serial_*.log`).
7. **Pass criterion:** 20/20 with no PN532 freeze. If a freeze occurs, record the cycle number and the log lines, then stop.
8. **Buzzer:** fit it after the diode passes, then test a single denied card.

### A2. Consumables bin (F-10)

1. Look at the cup. Remove everything, then read the portal's "mass" on the bin card. It should equal the cup tare.
2. If it does not, use the portal's guided calibration ("tare empty") and record the new tare.
3. **Valid zero:** the empty cup should show "0 left". This must not raise an "offline" or "error" state.
4. **Disconnected load cell:**
   - Power off, unplug the HX711 sensor cable, power on.
   - Expect `hx711:false` → a component alert and "sensor unavailable", **not** "0 left".
   - Re-plug.
5. **Node offline:** unplug the bin's power. After 90 s expect OFFLINE, with the last count shown as old (timestamp), not as live.
6. **Resistor flapping:** leave 10 resistors untouched for 10 min. Count the "1 pcs added/taken" notifications; expected 0.

### A3. Software (no hardware)

1. **Push** the 5 local commits after review. Keep the MP4s out of git.
2. **F-01 token fix:** a developer task. Deploy only with the backend tests green.
3. **Assistant GPU (F-05):** unload the models (`ollama stop qwen3:1.7b` and `qwen2.5:1.5b`) while the cameras are idle, then re-measure 5 questions. Expected (historical) about 5 s.
4. **Approve or keep the pending user** for the demo (your decision 20 Nov).
5. **Backups:** choose the retention periods. Enable `BACKUP_PASSPHRASE` if you want encrypted dumps (store the passphrase offline).
6. **Vault:** approve excluding `docs/knowledge/obsidian/**` from the sync, then rebuild the index once.
7. **Update CLAUDE.md:** model and device lines (F-18).

## B. At GIU (physical attendance required)

### B1. Network first

1. Check Hemaly's PC (S2PC136): its Smart_Lab NIC must not use .100–.103. Set a static .110 (or a router DHCP reservation).
2. `ping 192.168.1.100` (FANUC) and `ping 192.168.1.102` (UR5e) from the laptop's Ethernet. Both must answer, and `arp -a` must show the robot MACs, not Hemaly's PC.

### B2. Robots (read-only; a qualified operator is present; no commands)

1. The operator powers on the controllers. Do not change their mode.
2. Start `start_ur5e_monitor.bat` and `start_fanuc_monitor.bat`.
3. Confirm the portal twins move only when the operator jogs from the pendant. Record the sample rate and `last_seen` age.
4. Confirm the portal shows control **UNAVAILABLE** (`ROBOT_CONTROL=off`).

### B3. Cameras

Follow TWO_CAMERA_ARCHITECTURE_AND_BENCHMARK_PLAN.md:

- Baseline frame age and FPS.
- 1/2/4 people.
- Dead-zone gaps of 1/3/10/30 s × 5 repeats.
- Handoff with feet visible and hidden.
- Assistant questions during camera load (gate → CPU).

### B4. PCs

1. Update PC-10 to agent 1.0.
2. Confirm the PC-11 sticker matches GIULAB20-PC14.
3. Start the relay and confirm all 10 heartbeats are fresh.
4. Run one screen share and one broadcast. Confirm the auto-end 90 s after the presenter leaves.
5. **Do not** send "message all" or a shutdown without the lab owner's consent.

### B5. AR

On your phone over HTTPS:

1. Log detection latency (capture → box) for the UR5e, FANUC, the nodes and one PC, about 50 samples.
2. Confirm a PC box asks for its QR. Confirm the robot card shows live joints with a fresh timestamp.

### B6. Face server

Re-enrol or retrain USER5 and USER7 if those people are present (F-21).

## C. Before the defense: wording checklist

- **Pose:** "box-geometry body-part visibility, no keypoint model".
- **AR model:** "v8 ft_y11s".
- **PCs:** "10 GIU machines plus the admin laptop".
- **AI:** "local qwen2.5:1.5b / qwen3:1.7b, CPU unless the cameras are idle".
- **Status labels:** mark every result live, historical or simulated.
