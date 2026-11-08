---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/INCIDENT_REVIEW_2026-10-17.md"
source_hash: "77421777c78bbc580ac1845ee209e7b7255b7f4300cd225fb5c906e55c5a731e"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/INCIDENT_REVIEW_2026-10-17.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_LAB_READINESS_2026-10-18.md]] - mentioned by docs
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs

# Incident review (read-only evidence, 2026-10-17 evening)

Nothing below was changed in the portal: no incident was acknowledged, resolved or labelled false.
Each item lists the evidence from the records around it; a person decides and closes it in
/admin/incidents with a real reason. Times are Cairo time.

## Forced entry (6, all CRITICAL, all LAB_01)

| Incident | Time | Evidence around it (door records) | Reading |
|---|---|---|---|
| #56 | 2 Oct 21:28 | Controller had just rebooted (component faults 21:26, all back online), a booking + QR issued 21:28:15, the alarm 6 s later | Bring-up session; door opened by hand right after setup |
| #58, #59 | 2 Oct 21:31:35 and 21:31:46 | Granted entries at 21:31:08 and 21:32:12 (face / finger, ALI); door opened twice in between with no grant, each closed 4 s later | Testing the reed switch / relock between granted entries |
| #84 | 3 Oct 03:22 | No other records around it; door closed 4 s later | Unexplained - needs the owner's memory or a camera snapshot |
| #171 | 6 Oct 21:05 | Granted 21:05:29, then an identity-mismatch denial 21:05:48 | Testing identity mismatch (USER2 card + USER1 face) |
| #329 | 10 Oct 00:06 | Door-camera reconnect loop, two granted entries 00:05, then the alarm | Bench test after midnight; camera instability at the same time |

All carry provenance UNKNOWN (recorded before provenance tagging). The pattern - alarm seconds
after a granted entry or a controller restart, door closed within 4 s - fits bench testing, but it is
not proof. Suggested: the owner confirms each from memory; #84 is the only one with no surrounding test activity.

## Person in the lab with no door entry (2, CRITICAL)

| Incident | Time | Evidence | Reading |
|---|---|---|---|
| #153 | 6 Oct 01:33 | Camera saw 1 person, door had nobody inside; a snapshot exists | View the snapshot (Security -> Events) before deciding |
| #568 | 15 Oct 15:53 | Same, snapshot exists, provenance SOFTWARE_TEST (test mode) | Recorded in software-test mode |

Snapshots may show people: view them in the portal only, never copy them out.

## Repeated camera warnings ("Movement at equipment with nobody there" x 15, "Equipment moved or missing" x 13)

Not duplicates: each is a different equipment box (PC-01 ... PC-11, UR5e, laptop), and the
existing dedupe already folds repeats into one open incident per box (e.g. PC-10: 29 events, 1 incident).
Evidence for a common cause: on 7 Oct 12:54:57 six boxes fired in the same second - a lighting
change or a bumped camera, not six movements. Change made (2026-10-17): from the 3rd box of one
camera reporting the same kind within 5 s, the events join one "camera-wide change" incident that lists
the boxes (all events still stored; test `test_many_boxes_at_once_become_one_camera_wide_incident`).
The boxes named laptop / pc1 / pc01 are from the first zone drawings (5-6 Oct) and have had no events since.

