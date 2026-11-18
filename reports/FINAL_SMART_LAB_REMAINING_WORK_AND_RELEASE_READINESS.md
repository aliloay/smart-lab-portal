# Smart Lab: remaining work and release readiness (19 Nov 2026)

This page is the short entry point. The full closure set is in
[`final-smart-lab-closure-2026-11-18/`](final-smart-lab-closure-2026-11-18/). Start with
`FINAL_SMART_LAB_EXECUTIVE_READINESS_REPORT.md` there.

**Software: release-ready for the local demo.**
- Deployed build `ecbb167-20261118231702`.
- Tests: 841 backend, 396 cameras, 64 AI, 44 robots, 40 PC agent.
- 25 concurrent logins pass.

**What is left needs a person or hardware:**

| # | Item | Who |
|---|---|---|
| 1 | Change the admin password before the exhibition | owner |
| 2 | Router: stop Hemaly's PC taking .100/.102 (robot IPs) via DHCP: move the pool above .110, reserve the robots, or give Hemaly's Smart_Lab NIC a static .210 | owner / GIU IT |
| 3 | Connect the 4 ESP32 nodes (+ ESP32-CAM, core 3.2.1); Claude flashes and tests one step at a time | owner + Claude |
| 4 | Power on UR5e and FANUC once; confirm the twins go ONLINE (read-only) | owner |
| 5 | Re-measure AI answer time with both cameras live | next lab session |
| 6 | Confirm the PC-11 sticker (renamed from hostname GIULAB20-PC14) | owner |
| 7 | Thesis numbers still unmeasured: door end-to-end latency, cold start, power-cut recovery, load-cell accuracy, cost, node power | owner + hardware |

**Detail files:**
- `FINAL_OPEN_ISSUES.csv`
- `FINAL_UNRUN_TESTS.csv`
- `FINAL_OPERATOR_ACTIONS.md`
- `FINAL_RELEASE_READINESS_SCORECARD.md`
- `FINAL_TEST_EVIDENCE_INDEX.md`
- `FINAL_TEST_RESULTS.md`
