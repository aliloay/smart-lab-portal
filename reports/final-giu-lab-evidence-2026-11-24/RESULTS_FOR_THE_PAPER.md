# GIU Robotics Lab: measured results, 24 Nov 2026

Live at GIU unless a row says otherwise. Local time (Cairo). Raw data: `D:\SmartLabData\FINAL_GIU_LAB_EVIDENCE_2026-11-24` (private: it contains people). Portal build during the 16:14-17:18 measurements: cd5bf8b. Laptop with a GTX 1650, both cameras, both robots.

## 1. Cameras (16:14-17:12, sampled every second, n = 3,144 per camera)
| | Camera 1 | Camera 2 |
|---|---|---|
| Analysis rate, median / mean / lowest (limit 6/s) | 6.0 / 5.73 / 2.6 | 6.0 / 5.69 / 2.9 |
| Capture rate, median | 14.7 fps | 14.9 fps |
| Analysis pass, median of window medians (95th percentile of them) | 123 ms (171) | 132 ms (182) |
| Analysis pass, p95 inside each 300-frame window, median of them | 270 ms | 277 ms |
| Detection, median of window medians | 76 ms | 79 ms |
| Rate with 0-3 / 4-5 / 6+ people, median (16:14-16:59) | 6.0 / 6.0 / 4.6 (n = 31) | 6.0 / 5.8 / 4.1 (n = 13) |
| Streaming, 16:14-16:59 | 100 % | 100 % |

Laptop: CPU median 77 %, RAM 79 %, GPU 40 % at about 66 °C. At 13:38-13:47, with up to 9 (camera 1) and 10 (camera 2) people, the medians were 4.3 and 3.4 per second; laptop load was not controlled.
While the assistant answered: 5.3 to 4.2 and 3.9 to 3.0 (13:37); 6.0 to 4.8 and 5.8 to 5.0 (16:17). Two runs.

## 2. Naming people
Names came from staff confirmation and face matches; there was no door entry because the ESP32 boards were at home.

| Recording | Result |
|---|---|
| 15:20, 4 min | 58 % (camera 1) and 90 % (camera 2) of detections carried a name |
| 15:52, 5 min, walk | 27 % and 74 %. USER1 kept the name at the FANUC and back on camera 2, then it moved to another person |
| 16:04, 5 min, walk | 82 % and 74 %. USER1 and USER12 kept their names in 99.8 % of samples (529 of 530) on both cameras |
| 16:28, 12 min | 42 % and 78 % |
| 16:41, 20 min | 58 % and 83 % |

A carried name is not proof of a correct name: the operator verified only single moments.
- Same name on two people in one camera: 0 samples in the five recordings.
- Identity swaps confirmed by the operator: 2 (USER1 to USER5 on camera 1; USER1 to USER12 on camera 2).
- Look-only guesses on the wrong person were seen on the code of that morning. The rule was changed at the lab for the returning-look path (a person seen together with the named one does not inherit the name) and was running from 15:35. The handoff and the stored-look path did not read it until 25 Nov (section 11).
- Face matches stored 13:38-14:14: 12, score 0.504-0.663, all for USER5 and USER6. An earlier face confirmation named USER1 at 13:37:47.
- Seated people: the two cameras placed one seated person 3.3 m apart (pairing limit 0.7 m), because the feet were hidden.

## 3. Robots (16:14-17:12)
| | UR5e | FANUC |
|---|---|---|
| Live samples, all with joints | 1,891 | 1,763 |
| Age of stored data, median / p95 / max | 0.12 / 0.29 / 1.41 s | 0.14 / 0.36 / 2.73 s |
| Collector rate, median | 35.6 /s | 3.8 /s |
| Collector to portal, median / p95 | 29 / 143 ms | 128 / 279 ms |
| Check against the pendant | 6 joints within 0.006° (one still pose) | no numbers; lab engineer checked by eye |

Camera and telemetry agreement 16:14-16:59: UR5e "still, verified" 1,201 of 1,457, "movement verified" 87, "visual anomaly" 83. FANUC 1,298 of 1,359, 5 and 42.
FANUC web-page reads: n = 1,321, median 102 ms, p95 179 ms.
Tool position on the UR5e pendant used another reference frame and is not compared.

## 4. Failures and recovery
| Test | Result |
|---|---|
| Camera 2 cable | People cleared 2.0 s after each last frame, but old buffered frames showed 3 people twice more: fully clear after about 12 s. Fixed afterwards, tested offline only |
| Camera 1 | Recovered without a service restart; unplugged and boot time not separated |
| FANUC cable, about 21 s | Stale after about 3 s; portal record within about 7 s; back about 1 s after it was readable |
| UR5e cable, about 50 s | Stale event at 16:30:56, restored 16:31:46 |
| Router restart, 17:12:37 | Network back after 68 s. Streams stale after 2 s. Robots live 3 s (FANUC) and 8 s (UR5e) after the network. No portal health check failed (asked on the laptop itself, so this does not test the network) |
| Router restart, UR5e stale in the portal record | **47 s**. Cause: the reconnect blocked about 21 s, then the old pose was sent as fresh. Fixed afterwards, tested offline only |
| Robot record | Every 5 s a second report erased the joints (4 of 45 samples). Fixed at the lab: 0 of 3,654 live samples without joints afterwards |

## 5. Network and portal
Ping, n = 30 each, 0 % loss: router 2 ms, UR5e 2 ms, cameras 9 ms, engineer PC 1 ms (mean).
Portal health is asked on the laptop itself. TCP connect, n = 50, median / p95: router 4.8 / 22.8 ms, camera 1 13.7 / 43.4, camera 2 11.7 / 29.4, FANUC 5.1 / 19.0, UR5e RTDE port 16.7 / 1,039 (two groups, about 17 ms and about 1 s; a connection limit of the controller while the collector is connected is a possible cause, not tested).
Portal `/api/health`, n = 3,144: median 30 ms, p95 187 ms, max 2,533 ms, 0 failures. OPC UA server: 417 variables; 60 variables read in 213 ms median (60 cycles).
PC agents: Hemaly's PC, PC-08, PC-09 on 1.0; PC-02 updated to 1.1 at 15:59. Reports arrive every 30 s; those PCs' clocks differ from the laptop by 70.8 s, and the laptop matches internet time within 0.5 s.
Screen share: worked, with 304 "unchanged" answers. Delay not measured.

## 6. Assistants
| | Result |
|---|---|
| Project assistant, cameras live | FAQ and refusals 0.01-0.03 s; lookups 0.25-2.7 s; written answers 8.8-22.9 s (4 answers in two runs) |
| Portal assistant, instant answers, live | 18 of 20 answered from records, 427 ms slowest |
| Portal model, live, 5 questions | 1 plausible, **4 wrong**. Three are now answered from records |
| Project assistant, 50 questions, **at home, cameras off** | 32 correct, 8 partly, 7 wrong, 3 without a direct answer (graded by Claude, not a second person). 21 written answers: median 16 s, first word 11.9 s |
| Refusals | 5 of 5 control and secret requests refused (the other guard answers in that run were live-value questions). On 25 Nov 11 of 15 reworded requests passed the portal guard; fixed, 0 of 15 pass (offline) |

The benchmark ran before the six fact entries of 24 Nov were added, so it must not be quoted as the final state. A re-run on the same questions would not be an independent test.

## 7. Not measured at GIU on 24 Nov
ESP32 boards, door, RFID and sensors (use the earlier measurements of 21 Nov with their own date and place); camera, twin and screen-share delay; FANUC pendant numbers; face recognition after re-enrolment; no-internet test; pose accuracy; ground truth for tracking.

## 8. Overlapping people: what was done, and wording for the paper
1. Before 24 Nov: separate tracks for touching people, a re-check of names after a crossing, no name handed over while two people could fit.
2. At the lab, running from 15:35: a person seen together with the named one does not inherit that name when a look returns. Two other paths did not check this (fixed 25 Nov).
3. Enhanced version, after the lab (offline): a staff-confirmed name that clearly no longer fits after people touched becomes "Name ? (look)" and is flagged. It never moves to somebody else.

Evidence for step 3, replayed on the two-camera recording of 16:36-16:41: 6 of 6 tracks kept their name with no swap; 4 of 8 simulated swaps were detected (median 21 s). The 4 others had no clean view before the first touch. The limit (0.46, 10 checks) was chosen on this same recording, so this is calibration, not an independent test. Identity scenarios (simulated): 17, with 0 false names and 0 name switches.
Appearance distance in that recording (re-ID plus colour): same track more than 5 s apart p95 0.42 and 0.49 (n = 164, 214); two people at once p5 0.48 and 0.45 (n = 34, 165). The same-track values assume no identity change within a track: checked by eye on camera 2 sample frames only.

Suggested sentence: "Overlap between people is handled in three stages: separate tracking, withheld name transfer while identities are ambiguous, and a post-contact appearance check that downgrades an inconsistent name to an explicit guess. In simulated scenarios no false name occurred. In the laboratory, two identity swaps were observed with people meeting closely; the final check was added after that session and evaluated on recorded data."

### Seated people and the older version
- Recorded seats (21 Oct and 18 Nov) now also join seated people between the cameras, shown as "Name? (seat)": a guess that is never shared or counted. Two missing seats were added from the staff-confirmed labels of 15:52 and 16:04.
- Replay against confirmed labels (seat rule alone, matched samples): 15:20 recording 51 right, 2 wrong (before 1 and 0); 16:28 recording 245 right, 6 wrong (before 0 and 0). The two recordings used to add the seats: 104 / 0 and 67 / 59; the 59 come from a track whose label had probably swapped, not proven. This is why it stays a guess. Same people and same day, so no general accuracy is claimed. Not yet run on live cameras.
- Version of 22 Nov (d023e98) against the final one in the 17 simulated scenarios: identical, 0 false names in both. No reason to go back.

## 9. Robot and twin videos
- UR5e with the twin on a laptop in one shot: `D:/SmartLabData/colab/robot_pack_tmp/Ur5e robot.mov` (10.9 s). FANUC with the twin: `owner_robot_and_twin_older_video.mov` (19.0 s, date not in the file). Both are in or beside the evidence folder; no faces were seen in the sampled frames.
- A delay was tried on the UR5e video by matching motion in the two regions. The moving hand-held camera gives a best correlation of only 0.37, so **no delay is claimed**; the videos show that the twin follows.

## 10. Place of these numbers in the thesis
The contribution is the integration: door, ESP32 nodes, cameras, robots, lab PCs, automation, assistant and portal as one local system. The numbers justify it and show its limits. ESP32 and door figures are the existing ones of 21 Nov (`docs/reports/MEASUREMENTS_2026-11-21.md`, home bench), used with that date and place.

## 11. Corrections of 25 Nov (independent audit)
Reproduced and fixed in the code **after** all measurements above (offline tests only, not run on live cameras or robots):
- The step-3 check ("Name ? (look)") could be undone by the other camera's copy of the same name, was switched off by a touch before three clean views, and let the other person's look be learnt meanwhile.
- A shared desk could give a confirmed name; a look alone could cross between cameras as a confirmed name. Both are guesses now.
- Robot collector: a failed outage report was not repeated; the rate after an outage included the gap (the minimum of 3.5 /s in robot_telemetry.csv is this error).
- People walking in front of a still robot counted as robot motion (part of the 83 and 42 "visual anomaly" samples).
- The unplug script wrote "back after 5.5 s" from one buffered frame. That number is not used; section 4 is right.

Simulated scenarios with the corrected code: 17, 0 false names and 0 name switches, the same as before. So these scenarios do not contain the corrected cases; the new tests do.

No raw file was saved for: the 304 screen-share answers, the 18-of-20 and 5-question portal answers, and the replay counts of section 8. Describe them as observations, not as reproducible measurements.

Figures in circulation that this data does **not** support, so do not use them: "single-frame p95 307 / 294 ms, max 423 / 384 ms" (single frames were not logged; the logged window maxima reach 950 and 874 ms), an MX130 GPU (it is a GTX 1650), "26 sensor rows" (the database holds 102,911 from ENV_LAB01, 5 Oct to 22 Nov), BMP280 pressure (no such sensor in this project), and "80 % / 96 % after the fix" for the assistant (no such run exists).
