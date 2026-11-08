// Unit check of the live-camera person tracker (frontend/src/components/live/tracker.ts) - compiled to JS first:
//   npx tsc src/components/live/tracker.ts --outDir <tmp> --module es2020 --target es2020 && node e2e/tracker_check.mjs <tmp>/components/live/tracker.js
// Names must never move to another person: crossing, occlusion, contradicting evidence, lost tracks.
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'
const { PersonTracker, LOST_MS, NAME_TTL_MS } = await import(pathToFileURL(process.argv[2]).href)
const P = (name, ticket = 't-' + name) => ({ known: true, ticket, score: 0.7, person: { auth_subject: name, name, role: 'STUDENT', department: null, student_id: null, inside_by_door: false } })
const box = (x, y = 0.2) => ({ x, y, w: 0.15, h: 0.5, score: 0.9 })
let ok = 0
const t = new PersonTracker()
let now = 1000
// two people, A on the left named USER1, B on the right unknown
t.update([box(0.1), box(0.7)], now); now += 100; t.update([box(0.1), box(0.7)], now)
const [a, b] = t.tracks
t.applyFace(a.id, P('USER1'), now)
assert.equal(a.identity.auth_subject, 'USER1'); assert.equal(b.identity, null); ok++
// they walk towards each other in small steps and cross: the name follows A's track, never jumps to B
for (let i = 1; i <= 12; i++) { now += 100; t.update([box(0.1 + i * 0.05), box(0.7 - i * 0.05)], now) }
const A = t.tracks.find(x => x.id === a.id), B = t.tracks.find(x => x.id === b.id)
assert.ok(A && B, 'both tracks kept through the crossing')
assert.ok(B.x === undefined && B.raw.x < 0.2 && A.raw.x > 0.6, 'motion prediction kept each track on its own person')
assert.notEqual(B.identity?.auth_subject, 'USER1', 'the name never moved to the other person')
assert.equal(A.identity, null, 'after overlapping, the name is cleared until a new face match'); ok++
t.applyFace(A.id, P('USER1'), now); assert.equal(A.identity.auth_subject, 'USER1')
// occlusion: A disappears longer than LOST_MS -> track and name gone; a new person in the same place is unnamed
now += LOST_MS + 200; t.update([box(0.7 - 12 * 0.05)], now)
assert.equal(t.tracks.some(x => x.identity), false, 'no name survives a lost track'); ok++
now += 100; t.update([box(0.7 - 12 * 0.05), box(0.65)], now)
assert.equal(t.tracks.filter(x => x.identity).length, 0, 'a newcomer in the old place is not named'); ok++
// contradicting evidence: track named USER2 then a clear USER3 -> unknown (conflict), then needs two agreeing results
const c = t.tracks[0]
t.applyFace(c.id, P('USER2'), now); assert.equal(c.identity.auth_subject, 'USER2')
t.applyFace(c.id, P('USER3'), now); assert.equal(c.identity, null); assert.equal(c.conflict, true)
t.applyFace(c.id, P('USER3'), now); assert.equal(c.identity, null, 'first result after a conflict is not enough')
t.applyFace(c.id, P('USER3'), now); assert.equal(c.identity.auth_subject, 'USER3'); ok++
// a weak / no match never removes nor sets a name by itself
t.applyFace(c.id, { known: false, score: 0.4 }, now); assert.equal(c.identity.auth_subject, 'USER3'); ok++
// a name not re-confirmed for NAME_TTL_MS is dropped even if the track stays
for (let k = 0; k < Math.ceil((NAME_TTL_MS + 500) / 500); k++) { now += 500; t.update(t.tracks.map(x => x.raw), now) }
assert.equal(t.tracks.find(x => x.id === c.id).identity, null); ok++
// a face result for a track that was lost meanwhile is dropped
t.applyFace(99999, P('USER9'), now); assert.equal(t.tracks.some(x => x.identity?.auth_subject === 'USER9'), false); ok++
console.log(`tracker: ${ok}/8 checks passed`)
