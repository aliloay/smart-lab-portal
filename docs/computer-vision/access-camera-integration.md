# Access and camera integration

**Why it matters:** a door log knows who badged in, not who is inside an hour later. Someone may leave for a break while the door is open, or follow someone else in. Linking door events to what the cameras see gives a more accurate occupancy picture, and flags the cases where the two disagree.

## Flow (verified in code)

1. The Master Node reports a grant (`POST /api/access/grant`); the API opens an access session for that user.
2. The security-vision service sends its tracks and per-track evidence to `/api/security/*`.
3. A track first seen in the door area within 25 s of a grant takes that user's name ("door evidence"); a clear face match can confirm or contradict it.
4. The API compares camera counts with open sessions and raises the events listed in [tracking-and-presence.md](tracking-and-presence.md).
5. The portal shows the live view with boxes, the count ("3 seen · 0 entered"), the occupants and the events. PC zones turn "in use" when a person sits there, which is how desk and PC occupancy are inferred.
6. n8n workflow **16** uses the same records the other way round: a stock withdrawal while no session is open becomes a record to check.

Real example (7 Oct 2026 recording, faces blurred, name removed): a person walks in from the door without badging; the portal labels them "USER1 – not entered" and raises **Person with no door entry**; later the same track sits at PC-10 and the PC zone shows "PC-10 in".

## What it does not do

- It does not verify presence perfectly: occlusion, people outside the camera's view, and a missed exit all reduce accuracy.
- It does not make access decisions: the door decides; the cameras only observe and report.
- It does not identify people with YOLO; identity comes from door, face or look evidence.
