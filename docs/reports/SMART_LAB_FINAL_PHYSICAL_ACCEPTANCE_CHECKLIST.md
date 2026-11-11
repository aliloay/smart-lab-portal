# Smart Lab - physical acceptance checklist (after the 2026-11-11 closure work)

Everything here needs the real lab, real people and the real cameras. Software tests cannot sign these off.
Tick a line only with a measured result written next to it. Never test by unlocking the door from software, never
move a robot from the portal.

## Before you start

- [ ] `launch.bat` from **C:\Projects\smart-lab-portal** (the project left OneDrive on 11 Nov).
- [ ] `py tools\ops\watchdog.py --once` -> every required service UP.
- [ ] Both camera windows / logs show `re-id on directml-gpu...` and `OpenCV threads 2` behaviour (no errors).

## Cameras and identity (two people: A enrolled, B enrolled)

- [ ] A enters through the door (fingerprint or face). Camera 1 names A within a few seconds of entering ("by door").
- [ ] A walks into camera 2's view with feet hidden behind a desk -> A's name appears on camera 2 (handoff), no
      wrong name on anyone for the whole walk. Note the delay: ___ s.
- [ ] A bends, crouches, sits, leans -> keeps the name (or shows "?"), never takes B's name.
- [ ] A and B cross twice, close together -> names stay on the right person both times.
- [ ] A walks behind the FANUC enclosure / entrance wall for ~4 s and comes back -> same name on return.
- [ ] Restart **one** camera service while A stands in view -> A first shows "A ? (look)" (guess), then the
      confirmed name when the face is matched. Note: ___ s to the guess, ___ s to the confirmed name.
- [ ] A visitor C (not enrolled, similar clothes to A) walks in -> C stays "Person N" / Unknown, never "A".
- [ ] Live bar under the cameras on the Security page lists every person with colour, posture and nearby
      equipment, and updates within ~2 s.
- [ ] Each camera keeps ~9 analyses/s with both running (Security page metrics). Measured: cam1 ___ / cam2 ___.

## Portal

- [ ] Phone and laptop: switch between Dashboard, Labs, Devices, Bookings twice - the second visit shows content
      at once (no skeleton). Note any page that still blanks: ___
- [ ] Assistant: a free question shows the answer appearing word by word; "what is everyone doing right now"
      answers instantly with the camera lines.
- [ ] Sign out and sign in as a student: none of the staff data is shown, even for a moment.

## Phone AR ("Scan the lab")

- [ ] Two lab PCs in one frame -> two boxes. Router, switch, master node in one frame -> each boxed once.
- [ ] Hold the phone still 10 s -> boxes do not jump. Note the time from pointing to first box: ___ s.

## Devices and security

- [ ] Door, environment, consumables, reusables nodes still report (Devices page: all online).
- [ ] Installing a new lab PC: set `PC_ENROLL_OPEN=true` in `.env`, restart the backend, install, then set it back
      to false (enrolment is now closed by default).

## What to bring back for me (so the remaining tuning is based on real data)

Everything stays on the laptop; nothing is uploaded. Ask the people filmed first.

1. **Two synchronized camera recordings, ~10 min, two enrolled people.** Portal -> Security -> enlarge a camera ->
   Record, on **both** cameras, then walk this script (one step at a time, say the step out loud for the audio):
   enter through the door one after the other (badge + fingerprint/face); walk the length of the lab; stand and sit
   at two PCs; bend down to a bin; crouch; walk behind the FANUC cell and the entrance wall (~4 s hidden); cross
   paths twice close together; stand side by side 30 s; one person leaves the room for 1 min and comes back; finally
   restart one camera service (`stop_all.bat` is NOT needed - close only that camera's window and run launch.bat)
   while both stand in view. Files land in tools\security_vision\recordings\ (local). This is what I use to measure
   real re-ID distances, the half-body matching and the handoff delay, and to set thresholds on evidence.
2. **Seats:** sit alone at each PC both cameras see and run `py tools\security_vision\seat_capture.py PC-07`
   (then PC-08, ...). About 5 s each; fixes "PC-08 in use" when someone sits at PC-07.
3. **Floor pairs:** with one person standing still at 4-5 different spots seen by both cameras, run
   `py tools\security_vision\pair_capture.py "Ali at the UR5e"` at each spot. Improves the two-camera floor match.
4. **AR photos for the weak classes:** 30-50 phone photos each of the network switch, the FANUC robot, both teach
   pendants, lab PCs and the door, from different distances and angles, plus 20 photos with several of them in one
   frame. A 30 s screen recording of "Scan the lab" moving across the room. Put them in a folder; I add them to the
   Colab round.
5. **The numbers in the checklist above** (delays, analysis rates, anything that went wrong with the time it happened).
6. **Logs:** nothing to do - the services write them to `logs\` and `tools\security_vision\recordings\identity_log*.jsonl`.

## Not to be done as part of this checklist

Door relay tests, firmware flashing, robot motion, changing the admin password.
