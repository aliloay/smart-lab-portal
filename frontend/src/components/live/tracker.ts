/**
 * Person tracks for the live camera (2026-10-27). The detector gives boxes per frame; this keeps a stable track id
 * per person (greedy IoU matching) with a smoothed box for the overlay. A NAME belongs to one track only:
 *   - it is set only from a face check of THAT track's own crop (never from a neighbour or the last position);
 *   - it is dropped when the track is lost (no transfer to whoever appears in the same place later);
 *   - a later clear match with a DIFFERENT person clears it (contradicting evidence = unknown, not a guess).
 * Pure functions + one small class: unit-tested in e2e/tracker_check.mjs.
 */
export interface Box { x: number; y: number; w: number; h: number; score?: number }
export interface Identity { auth_subject: string; name: string; ticket: string; score: number | null; at: number
  person: import('../../lib/api').ScanPerson }
export interface Track { id: number; box: Box; raw: Box; firstSeen: number; lastSeen: number; hits: number
  identity: Identity | null; lastFaceCheck: number; conflict: boolean; vx: number; vy: number }

export const LOST_MS = 1500          // a track not matched for this long is gone (and its name with it)
export const NAME_TTL_MS = 20000     // a name not re-confirmed by a face check for this long is dropped
const IOU_MIN = 0.25
const OVERLAP_CLEAR = 0.4            // two tracks this much on top of each other = a crossing: both names re-checked
const SMOOTH = 0.45                  // new = old + SMOOTH * (measured - old)

export function iou(a: Box, b: Box): number {
  const x1 = Math.max(a.x, b.x), y1 = Math.max(a.y, b.y)
  const x2 = Math.min(a.x + a.w, b.x + b.w), y2 = Math.min(a.y + a.h, b.y + b.h)
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1)
  const u = a.w * a.h + b.w * b.h - inter
  return u > 0 ? inter / u : 0
}

export class PersonTracker {
  tracks: Track[] = []
  private next = 1

  update(boxes: Box[], now: number): Track[] {
    const pairs: [number, number, number][] = []
    // matched against where each person is HEADING (last box + its velocity), so two people crossing keep their
    // own tracks instead of swapping at the moment they overlap
    this.tracks.forEach((t, ti) => {
      const dt = Math.min(1, (now - t.lastSeen) / 100)
      const pred = { ...t.raw, x: t.raw.x + t.vx * dt, y: t.raw.y + t.vy * dt }
      boxes.forEach((b, bi) => { const v = iou(pred, b); if (v >= IOU_MIN) pairs.push([v, ti, bi]) })
    })
    pairs.sort((a, b) => b[0] - a[0])
    const usedT = new Set<number>(), usedB = new Set<number>()
    for (const [, ti, bi] of pairs) {
      if (usedT.has(ti) || usedB.has(bi)) continue
      usedT.add(ti); usedB.add(bi)
      const t = this.tracks[ti], b = boxes[bi]
      const dt = Math.max(1, (now - t.lastSeen) / 100)          // velocity per 100 ms, smoothed
      t.vx = 0.5 * t.vx + 0.5 * ((b.x - t.raw.x) / dt); t.vy = 0.5 * t.vy + 0.5 * ((b.y - t.raw.y) / dt)
      t.raw = b
      t.box = { x: t.box.x + SMOOTH * (b.x - t.box.x), y: t.box.y + SMOOTH * (b.y - t.box.y),
                w: t.box.w + SMOOTH * (b.w - t.box.w), h: t.box.h + SMOOTH * (b.h - t.box.h), score: b.score }
      t.lastSeen = now; t.hits++
    }
    boxes.forEach((b, bi) => {
      if (usedB.has(bi)) return
      this.tracks.push({ id: this.next++, box: { ...b }, raw: b, firstSeen: now, lastSeen: now, hits: 1,
                         identity: null, lastFaceCheck: 0, conflict: false, vx: 0, vy: 0 })
    })
    this.tracks = this.tracks.filter(t => now - t.lastSeen <= LOST_MS)
    for (const t of this.tracks) if (t.identity && now - t.identity.at > NAME_TTL_MS) t.identity = null
    // a crossing / occlusion between two tracks: a name may no longer be on the right person - both are re-checked
    // by a face match before a name shows again (a correct "person" beats a confident wrong name)
    for (let i = 0; i < this.tracks.length; i++) for (let j = i + 1; j < this.tracks.length; j++) {
      const a = this.tracks[i], b = this.tracks[j]
      if ((a.identity || b.identity) && iou(a.raw, b.raw) >= OVERLAP_CLEAR) {
        a.identity = null; b.identity = null; a.lastFaceCheck = 0; b.lastFaceCheck = 0
      }
    }
    return this.tracks
  }

  /** The result of a face check made on track `id`'s own crop. */
  applyFace(id: number, r: { known: boolean; ticket?: string; score: number | null; person?: Identity['person'] }, now: number) {
    const t = this.tracks.find(x => x.id === id)
    if (!t) return                                         // the track was lost meanwhile: the result is dropped
    t.lastFaceCheck = now
    if (!r.known || !r.person || !r.ticket) return          // no clear match: an existing name stays until its ticket ages
    if (t.identity && t.identity.auth_subject !== r.person.auth_subject) {
      t.identity = null; t.conflict = true                  // two different people on one track: show unknown
      return
    }
    if (t.conflict) { t.conflict = false; return }          // first clear result after a conflict: wait for a second one
    t.identity = { auth_subject: r.person.auth_subject, name: r.person.name, ticket: r.ticket, score: r.score, at: now,
                   person: r.person }
  }

  /** Which track to check next: the selected one first, then ones without a name, then the oldest re-check. */
  nextForFace(now: number, selected: number | null, everyMs = 5000): Track | null {
    // a person is checked from their FIRST box (2026-10-27, owner: "takes too much time to detect me" - over a slow
    // phone link waiting for a second box cost a whole extra round trip); the name still needs a clear face match
    const live = this.tracks.filter(t => now - t.lastSeen < 400)
    const sel = live.find(t => t.id === selected && now - t.lastFaceCheck > 1200)
    if (sel) return sel
    const unnamed = live.filter(t => !t.identity && now - t.lastFaceCheck > 1500).sort((a, b) => a.lastFaceCheck - b.lastFaceCheck)
    if (unnamed.length) return unnamed[0]
    const recheck = live.filter(t => t.identity && now - t.lastFaceCheck > everyMs).sort((a, b) => a.lastFaceCheck - b.lastFaceCheck)
    return recheck[0] ?? null
  }

  clear() { this.tracks = [] }
}

/** The face crop for one person box (normalised 0..1): head and shoulders, a little wider than the box. */
export function faceCrop(b: Box): Box {
  const x = Math.max(0, b.x - b.w * 0.1), y = Math.max(0, b.y - b.h * 0.05)
  const w = Math.min(1 - x, b.w * 1.2), h = Math.min(1 - y, Math.max(b.h * 0.55, b.w * 0.9))
  return { x, y, w, h }
}
