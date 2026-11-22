// ultracode 2026-11-22 FE-1b: pure helpers for the project-knowledge NDJSON stream (no React, no DOM).
// ProjectKnowledge.tsx feeds every line through parseKbLine and every event through applyKbEvent;
// finishKbTurn decides the final status when the stream ends.

export type KbStatus = 'running' | 'completed' | 'failed' | 'cancelled'

export interface KbTurnFields {
  route?: string; why?: string; steps: string[]; text: string; cites: unknown[]
  status: KbStatus; error?: string; ms?: number; firstMs?: number; note?: string
}

/** One NDJSON line -> event object, or null for a blank or malformed line (skipped, never thrown). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function parseKbLine(line: string): Record<string, any> | null {
  const s = line.trim()
  if (!s) return null
  try {
    const v = JSON.parse(s)
    return v && typeof v === 'object' && !Array.isArray(v) ? v : null
  } catch {
    return null
  }
}

/** Fold one event into the turn. `startedAt` and `now` are epoch ms. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function applyKbEvent<T extends KbTurnFields>(t: T, e: Record<string, any>, startedAt: number, now: number): T {
  if (e.type === 'meta') return { ...t, route: e.route, why: e.why, cites: e.citations ?? [] }
  if (e.type === 'step') return { ...t, steps: [...t.steps, String(e.text).replace(/^step: /, '')] }
  if (e.type === 'sources') return { ...t, cites: e.sources }
  if (e.type === 'token') return { ...t, text: t.text + e.text, firstMs: t.firstMs ?? now - startedAt }
  if (e.type === 'done') return {
    ...t,
    status: e.status === 'completed' ? 'completed' : e.status === 'cancelled' ? 'cancelled' : 'failed',
    error: e.error, note: e.note, ms: now - startedAt,
    text: t.text || (e.answer && e.route !== 'lookup' ? e.answer : t.text),
  }
  return t
}

/**
 * The stream ended. Only a {"type":"done"} event makes a turn 'completed'; a stream that ends without it
 * (connection dropped, service restarted, reply cut short) is 'failed' - or 'cancelled' if the user stopped it.
 */
export function finishKbTurn<T extends KbTurnFields>(t: T, sawDone: boolean, aborted: boolean, startedAt: number, now: number): T {
  if (t.status !== 'running') return t
  if (sawDone) return { ...t, status: 'completed', ms: now - startedAt }
  if (aborted) return { ...t, status: 'cancelled', ms: now - startedAt }
  return { ...t, status: 'failed', error: t.error ?? 'answer stopped early', ms: now - startedAt }
}
