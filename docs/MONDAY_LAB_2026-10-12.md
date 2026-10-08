# Lab checklist, Monday 2026-10-12: camera, robots, network

Everything below was built and software-tested at home on 2026-10-08. Nothing
in this list has been physically verified yet. Do the steps in order, one at a
time, and write down each result.

## 0. Before anything

- Start the system with `launch.bat`. It sets the camera clock and starts the
  camera program.
- Command Center: `http://192.168.1.200:8080` (or `/command` on the portal).
  The health bar must show every service with its real state.

## 1. Network: is 192.168.1.210 free? (for the Command Center's own address)

    arp -a | findstr 192.168.1.210
    ping -n 2 192.168.1.210

If **no answer and no ARP entry**, the address is free. Then add it to the
laptop's lab cable (PowerShell **as administrator**):

    New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.1.210 -PrefixLength 24

The Command Center then opens at `http://192.168.1.210:8080`, or
`https://192.168.1.210:8443` once the certificate authority is trusted
(docs/SECURITY.md). If something answers on .210, pick another address,
check it the same way, and rerun `tools/tls/make_local_ca.py --ip <new>`.

## 2. UR5e: read-only telemetry

1. On the pendant: Settings → System → Network. Write down the IP, subnet
   mask and gateway. Do NOT change them. (The pendant photo showed
   192.168.1.102, with the student PC at 192.168.1.101.)
2. Before plugging the switch in: `ping 192.168.1.102` and
   `ping 192.168.1.101` from the laptop on the lab LAN. Neither address may
   be in use by anything else (`arp -a` must not show a different MAC).
3. Wiring: robot → switch (blue cable), switch → student PC, switch →
   Smart_Lab router (the UGREEN Cat6 cables).
4. `pip install ur_rtde`, then:

       cd tools\robot_monitor
       py robot_collector.py --source ur --robot 192.168.1.102 --device UR5E_01 --name UR5e --model UR5e --asset UR5E-01

5. Check the robot page: it should report about 50 samples a second, every
   joint value should match the pendant, and the state should be STATIONARY.
6. Movement tests (the robot's operator moves it; we only watch):
   - J1 alone, then J2 … J6 alone, then several joints together. Each move
     should give a `JOINT_MOVED` event with the right joint and angle.
   - Write down the timestamps on the pendant, in the event, and in the
     camera's view.
7. HOME: the operator puts the robot in its home pose and it stands still.
   An admin then presses "Calibrate HOME". Move away, and the page should
   show `HOME_LEFT`; move back, and it should show `HOME_RETURNED`.
8. Pull the robot's cable for 10 s: the page shows TELEMETRY_STALE, never
   "stationary". Plug it back in: `TELEMETRY_RESTORED`.

## 3. FANUC: identify first (no code assumes a protocol)

1. On the teach pendant: Menu → Setup → Host Comm → TCP/IP. Write down both
   ports' IP addresses, masks and MACs. Also note the controller type on its
   label (R-30iB / R-30iB Plus / …) and the arm model.
2. If both ports show the same subnet, do NOT plug both into the same switch.
3. For each address: `py tools\robot_monitor\fanuc_probe.py --robot <IP>`.
   This is read-only: connect checks plus the controller's own web pages,
   which are saved to `fanuc_probe_out/`. Send me the output; the read-only
   interface is chosen from what is really there.

## 4. Camera: identity and latency

1. Press **Record** on the Security page, then run the people test
   scenarios, one recording each:
   - 1 person alone, walking across the room;
   - 2 people crossing paths;
   - 2 people overlapping, then separating;
   - sitting down at a PC and standing up;
   - leaving the view and coming back;
   - turning their back to the camera;
   - an unknown person.

   After each: Stop. These files are replayed at home to measure identity
   accuracy, again and again on the same footage.
2. Camera delay from the scene to the laptop (it cannot be measured in
   software): show a millisecond stopwatch on a phone in front of the camera,
   and photograph the phone next to the portal's live view in the same shot.
   The difference is the camera's delay. Do it 5 times.
3. `http://127.0.0.1:5100/metrics` (device key header): save the JSON
   (frame ages, fps, detector ms) with the stopwatch photos.

## 5. Robot boxes on the camera

The UR5e and Fanuc boxes must be drawn around the arm's whole working area.
Then move the robot: the robot page's "Telemetry + camera" panel should show
`MOVEMENT_VERIFIED`. When someone stands in front of the robot it should
show `VISUALLY_OCCLUDED`, never "still".
