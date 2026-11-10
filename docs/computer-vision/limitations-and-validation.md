# Limitations and validation

## Validation (recorded)

| Test | Result | Source |
|---|---|---|
| Unit and scenario tests of the vision service | 297 passed (9 Nov 2026) | `py -m pytest -q tools/security_vision` |
| Detection on 363 reviewed people, tracking on 3 reviewed clips, two cameras on the GTX 1650 | See the benchmark | [CV_BENCHMARK_2026-10-26.md](../CV_BENCHMARK_2026-10-26.md) |
| Live portal camera with door cross-check | Recorded 7 Oct 2026 (person with no door entry flagged; "PC-10 in" after sitting) | screen recording kept locally |
| Two-camera name sharing | Simulation only | `test_crosscam*.py` |

## Known failure conditions

- Occlusion (people behind furniture or each other) and leaving the view lose tracks; a track is dropped after 2 s without a match.
- Seated people with only the head visible are harder to detect (the confidence threshold was tuned for them).
- Strong backlight from windows and low light reduce detection confidence.
- The camera must stay still: auto-tracking or a bump moves the equipment boxes (the service detects this and re-aligns or raises "Camera view changed").
- Similar clothing makes appearance matching weaker when two people cross.
- Cross-camera sharing is inactive until both cameras are floor-calibrated.
