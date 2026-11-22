// ultracode 2026-11-22 FE-1b: project-knowledge stream folding (pure functions, no DOM, no network).
import test from 'node:test'
import assert from 'node:assert/strict'
import { applyKbEvent, finishKbTurn, parseKbLine } from '../src/lib/kbstream'
import type { KbTurnFields } from '../src/lib/kbstream'

const fresh = (): KbTurnFields => ({ steps: [], text: '', cites: [], status: 'running' })

/** Run NDJSON lines through the same steps ProjectKnowledge uses, then end the stream. */
function run(lines: string[], aborted = false): KbTurnFields {
  let t = fresh()
  let sawDone = false
  for (const line of lines) {
    const e = parseKbLine(line)
    if (!e) continue
    if (e.type === 'done') sawDone = true
    t = applyKbEvent(t, e, 0, 1000)
  }
  return finishKbTurn(t, sawDone, aborted, 0, 2000)
}

test('a done:completed event completes the turn', () => {
  const t = run([
    '{"type":"meta","route":"answer","why":"x","citations":[]}',
    '{"type":"token","text":"Hello"}',
    '{"type":"done","status":"completed","answer":"Hello"}',
  ])
  assert.equal(t.status, 'completed')
  assert.equal(t.text, 'Hello')
  assert.equal(t.route, 'answer')
  assert.equal(t.ms, 1000)                              // set by the done event (now = 1000 in run())
})

test('a stream that ends without a done event fails, it does not complete', () => {
  const t = run(['{"type":"token","text":"partial"}'])
  assert.equal(t.status, 'failed')
  assert.equal(t.error, 'answer stopped early')
  assert.equal(t.text, 'partial')
})

test('a stream the user stopped without done is cancelled', () => {
  const t = run(['{"type":"token","text":"partial"}'], true)
  assert.equal(t.status, 'cancelled')
})

test('a malformed line is skipped and the rest of the answer still completes', () => {
  const t = run([
    '{"type":"token","text":"A"}',
    '{"type":"token","text":"B"',                       // truncated JSON
    'not json at all',
    '',
    '[1,2,3]',
    '{"type":"token","text":"C"}',
    '{"type":"done","status":"completed"}',
  ])
  assert.equal(t.text, 'AC')
  assert.equal(t.status, 'completed')
})

test('parseKbLine returns null for blank, malformed and non-object lines', () => {
  assert.equal(parseKbLine('   '), null)
  assert.equal(parseKbLine('{oops'), null)
  assert.equal(parseKbLine('42'), null)
  assert.deepEqual(parseKbLine('{"type":"step","text":"step: x"}'), { type: 'step', text: 'step: x' })
})

test('a done with status failed or an error keeps the failure', () => {
  const t = run(['{"type":"done","status":"failed","error":"model busy"}'])
  assert.equal(t.status, 'failed')
  assert.equal(t.error, 'model busy')
})
