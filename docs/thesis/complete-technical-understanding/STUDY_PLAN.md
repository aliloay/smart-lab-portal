# Fast study plan: 12 lessons, 7 days, about 17 hours

Every day: two lessons of 70 minutes. One lesson = 10 min recall without notes, 25 min reading, 20 min in the code or hardware, 15 min questions and explaining aloud.
After each lesson you write half a page for the thesis section named here (included from day 2 as 20 extra minutes a day). So the paper is drafted while you learn.

| Day | Min | Lesson | You open | You can explain | Thesis section |
|---|---|---|---|---|---|
| **1** Wed 25 Nov | 70 | 1 Whole system: parts, who decides, one value end to end | LESSON_01, map | the project in 3 minutes | Introduction, architecture |
| | 70 | 2 ESP32 nodes: every sensor, pin, power rail, Wi-Fi, what happens offline | firmware/SmartLab_Environment_Node, hardware docs | any pin and why it is there | Hardware |
| **2** Thu 26 | 70 | 3 Bins: load cell, HX711, tare, calibration, item counting; NFC, lid, servo | SmartLab_Consumable_Bin, SmartLab_Reusable_Bin | grams to item count with numbers | Hardware, firmware |
| | 70 + 20 | 4 Door: card/QR, fingerprint/face, identity match, fail closed, relay | SmartLab_Master_Portal, access.py | why nothing on the network opens the door | Access control |
| **3** Fri 27 | 70 | 5 Backend and database: request, roles, 43 tables, events, WebSocket, backups | access.py, models, API_CATALOG | one request line by line | Backend |
| | 70 + 20 | 6 Portal: React, router, roles, live data, caching; every page | App.tsx, nav.ts, live.tsx | how a page gets and refreshes its data | Frontend |
| **4** Sat 28 | 70 | 7 Cameras 1: frame, detection, tracking, look, floor map, pose, speed | vision.py, security_vision.py | capture rate, analysis rate and pass time | Computer vision |
| | 70 + 20 | 8 Cameras 2: names, guesses, doubt, vetoes, two cameras, seats; the audit bugs | vision.py, crosscam.py, labmap.py | every rule that prevents a wrong name | Identity |
| **5** Sun 29 | 70 | 9 Robots: RTDE, FANUC page, staleness, twin, camera check; OPC UA server | robot_collector.py, robot_fusion.py | why UNKNOWN is never STATIONARY | Robotics |
| | 70 + 20 | 10 PCs: agent, signing, relay, screens, ETag/304; network and Docker | pc_agent.py, relay.py, compose | why a relay exists and how it is limited | Infrastructure |
| **6** Mon 30 | 70 | 11 AI: embeddings, search, FAQ, guards, model, voice; Obsidian, n8n, AR | agent.py, kb.py, scan.py | what answers without a model and why | AI and knowledge |
| | 70 + 20 | 12 Results: every test, median/p95, what each number proves and does not | RESULTS_FOR_THE_PAPER | every number in the paper | Results, limits |
| **7** Tue 1 Dec | 120 | Mock defence: 40 strict questions over all parts, 10 min presentation | no notes | the whole system | - |
| | 60 | Repair the weakest three topics | - | - | Discussion |

**Total:** 14 h lessons, 3 h mock and repair, about 2 h paper notes.

**When will you understand everything?** On 1 Dec you can explain and defend every part and trace every data flow. Knowing every line of about 355 routes and the camera code by heart is not realistic in a week and not what an examiner asks; you will know where each rule lives and why. Keep it alive with one 30-minute mixed quiz every third day until 31 Jan.

**Paper:** raw section notes exist by 1 Dec; full writing starts 2 Dec with them.

**If a day is missed:** do only the first lesson of the next day double; never skip 1, 5, 8 and 12.
**Rule:** lesson n+1 starts after the five questions of lesson n are answered. Wrong fundamentals are repeated at once.
