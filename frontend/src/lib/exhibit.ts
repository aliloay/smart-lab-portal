/** What the exhibition screen shows, and where it came from. Counts and readings only: no people, no camera pictures,
 *  no addresses. The screen says LIVE, HISTORICAL or SIMULATED on every view. */
import type { MetricLatest, ServiceHealth } from './api'

export type Source = 'LIVE' | 'HISTORICAL' | 'SIMULATED'
export interface Reading { label: string; value: string; note: string; live: boolean }
export interface Snapshot { at: string; counts: Record<string, number>; parts: { name: string; state: string }[]; readings: Reading[] }

const PUBLIC = ['temperature', 'humidity', 'smoke', 'flame']
const GROUP: Record<string, string> = { door: 'Door control', entry_camera: 'Door camera', environment: 'Environment and bins',
  security_camera: 'Security cameras', robot: 'Robots', pc: 'Lab computers' }

/** Parts are grouped ("3 of 6 online"): single host names never reach a public screen. */
export function snapshot(services: ServiceHealth[], latest: MetricLatest[], at: string): Snapshot {
  const real = services.filter(s => s.state !== 'SIMULATION')
  const counts: Record<string, number> = {}
  real.forEach(s => { counts[s.state] = (counts[s.state] ?? 0) + 1 })
  const by = new Map<string, ServiceHealth[]>()
  real.forEach(s => { const k = GROUP[s.group ?? ''] ?? 'Portal services'; by.set(k, [...(by.get(k) ?? []), s]) })
  const readings = latest.filter(r => PUBLIC.includes(r.metric_name) && !r.metadata.simulated && r.quality !== 'OUT_OF_RANGE').map(r => ({
    label: r.label, value: r.kind === 'state' ? (r.value ? 'detected' : 'not detected') : `${Math.round(r.value * 10) / 10} ${r.unit}`,
    live: r.quality === 'VALID', note: r.quality === 'VALID' ? 'now' : `last stored ${r.timestamp.slice(0, 16).replace('T', ' ')} UTC` }))
  return { at, counts, readings, parts: [...by].map(([name, l]) => ({ name, state: `${l.filter(s => s.state === 'ONLINE').length} of ${l.length} online` })) }
}

/** SIMULATED example, used only when there is neither a live answer nor a stored snapshot. */
export const SIMULATED: Snapshot = {
  at: '2026-11-23T00:00:00Z', counts: { ONLINE: 18, STALE: 1, OFFLINE: 1 },
  parts: [{ name: 'Portal services', state: '8 of 8 online' }, { name: 'Door control', state: '1 of 1 online' },
    { name: 'Environment and bins', state: '3 of 3 online' }, { name: 'Security cameras', state: '2 of 2 online' },
    { name: 'Lab computers', state: '4 of 6 online' }],
  readings: [{ label: 'Temperature', value: '24.0 °C', note: 'example', live: false }, { label: 'Humidity', value: '45 %', note: 'example', live: false }],
}

const KEY = 'smartlab.exhibit.last'
export function remember(s: Snapshot) { try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* not kept */ } }
export function recall(): Snapshot | null {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || 'null')
    return s && typeof s.at === 'string' && !Number.isNaN(Date.parse(s.at)) && s.counts && typeof s.counts === 'object'
      && Array.isArray(s.parts) && Array.isArray(s.readings) ? s : null
  } catch { return null }
}
/** A live answer wins; then this browser's last real one; then the labelled example. */
export function choose(live: Snapshot | null, stored: Snapshot | null): { source: Source; data: Snapshot } {
  return live ? { source: 'LIVE', data: live } : stored ? { source: 'HISTORICAL', data: stored } : { source: 'SIMULATED', data: SIMULATED }
}
