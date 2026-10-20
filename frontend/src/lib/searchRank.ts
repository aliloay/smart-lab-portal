/**
 * Relevance ranking for the global search (owner 2026-10-20: "lab1 or robot should show the Robotics
 * Lab - not the literal word"). Runs in the browser on every keystroke over the small index from
 * /api/search/index, so results are instant.
 *
 * Matching, per query word, against each field of an item:
 *   exact word 1.0 · word starts with it 0.85 · inside the squashed text 0.6 · one typo 0.5 (4+ letters)
 * "Squashed" = lower case, no spaces or punctuation, leading zeros dropped: "LAB_01", "lab 1", "Lab01"
 * and "lab1" are all "lab1"; "UR-5e" is "ur5e". Every query word must match somewhere. Fields weigh
 * differently: the name counts most, then its code / tag, then what it is (type and subject words,
 * e.g. the Robotics Lab carries "robot arm ur5e fanuc"), then the lab it belongs to.
 */
export interface SearchItem {
  type: string; title: string; subtitle: string; to: string
  keys?: string; words?: string; lab?: string; resolved?: boolean
}

const FIELDS: [keyof SearchItem, number][] = [['title', 1], ['keys', 0.9], ['words', 0.6], ['lab', 0.35], ['subtitle', 0.3]]
const TYPE_BOOST: Record<string, number> = { page: 0.3, lab: 0.35, device: 0.3, equipment: 0.25, person: 0.2, incident: 0.05 }

const squash = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '').replace(/(^|[a-z])0+(?=\d)/g, '$1')
const noLeadZeros = (t: string) => t.replace(/^0+(?=\d)/, '')
// words, plus the letter / digit parts of mixed ones: "LAB01" -> lab1, lab, 1; "ur5e" -> ur5e, ur, 5, e
const words = (s: string) => s.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean)
  .flatMap(w => /\d/.test(w) && /[a-z]/.test(w)
    ? [squash(w), ...w.split(/(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)/).map(noLeadZeros)]
    : [noLeadZeros(w)])

function editWithin1(a: string, b: string): boolean {
  if (a === b) return true
  if (Math.abs(a.length - b.length) > 1) return false
  let i = 0, j = 0, diff = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { i++; j++; continue }
    if (++diff > 1) return false
    if (a.length > b.length) i++; else if (b.length > a.length) j++; else { i++; j++ }
  }
  return diff + (a.length - i) + (b.length - j) <= 1
}

interface Prepared { item: SearchItem; f: { w: number; words: string[]; sq: string }[]; titleSq: string; keySq: string[] }

export function prepare(items: SearchItem[]): Prepared[] {
  return items.map(item => ({
    item,
    f: FIELDS.map(([k, w]) => ({ w, words: words(String(item[k] ?? '')), sq: squash(String(item[k] ?? '')) })),
    titleSq: squash(item.title),
    keySq: words(item.keys ?? '').length ? (item.keys ?? '').split(/\s+/).map(squash).filter(Boolean) : [],
  }))
}

function tokenScore(tok: string, f: Prepared['f'][number]): number {
  let best = 0
  for (const w of f.words) {
    if (w === tok) return 1
    // a typed number is a whole number: "1" is not the start of "10"
    if (w.startsWith(tok) && !(/\d$/.test(tok) && /^\d/.test(w.slice(tok.length)))) best = Math.max(best, tok.length === 1 ? 0.5 : 0.85)
    else if (tok.length >= 4 && (editWithin1(w, tok) || (w.length > tok.length && editWithin1(w.slice(0, tok.length), tok)))) best = Math.max(best, 0.5)
  }
  if (best < 0.6 && tok.length >= 2 && f.sq.includes(tok)) best = 0.6
  return best
}

// Words that carry no meaning in a phrase ("person keeps disappearing on camera" -> person, disappearing, camera)
const STOP = new Set(('a an and are at be by can do does for from has have i in is it its keep keeps kept me my of on or ' +
  'show shows the this to too very was what when where which who why will with how not no doesnt dont isnt cant ' +
  'please find search open get see any some').split(' '))
const SOFT = new Set('high low hot cold warm broken problem problems issue wrong working work fails failing slow fast bad stuck'.split(' '))
// Related words people type for the same thing (query side; matched at 0.8 of a direct hit)
const RELATED: Record<string, string[]> = {
  disappearing: ['tracking', 'lost', 'unknown', 'identity'], disappears: ['tracking', 'lost', 'unknown'], vanish: ['tracking', 'lost'],
  lost: ['tracking', 'unknown'], tracking: ['camera', 'identity'], identity: ['face', 'tracking'], who: ['identity', 'face'],
  hot: ['temperature', 'environment'], heat: ['temperature'], warm: ['temperature'], high: ['warning', 'alert'], cold: ['temperature'],
  humid: ['humidity'], smoke: ['gas', 'hazard', 'fire'], fire: ['emergency', 'hazard', 'evacuation'], evacuate: ['emergency', 'evacuation'],
  denied: ['refused', 'access', 'denial'], refused: ['denied', 'access'], rejected: ['denied', 'refused'], blocked: ['denied', 'locked'],
  login: ['access', 'users'], entry: ['access', 'door'], enter: ['access', 'door'], unlock: ['door', 'access'],
  broken: ['issue', 'maintenance', 'fault'], fault: ['issue', 'maintenance', 'incident'], error: ['incident', 'issue', 'alert'],
  down: ['offline', 'incident'], offline: ['incident', 'devices'], repair: ['maintenance', 'issue'], fix: ['maintenance', 'issue'],
  reserve: ['booking', 'bookings'], reservation: ['booking'], schedule: ['booking', 'bookings'], booked: ['booking'],
  pc: ['computer'], computer: ['pc'], laptop: ['pc'], cctv: ['camera', 'security'], video: ['camera'], webcam: ['camera'],
  arm: ['robot', 'robotics'], cobot: ['robot'], machine: ['equipment'], tool: ['equipment', 'reusable'], stock: ['consumables', 'inventory'],
  stats: ['analytics', 'reports'], graph: ['analytics'], report: ['reports'], people: ['users', 'person'], student: ['users', 'person'],
}

export function rank(prepared: Prepared[], query: string, limit = 20): SearchItem[] {
  const all = words(query).filter((t, i, a) => a.indexOf(t) === i)
  const toks = all.filter(t => !STOP.has(t)).length ? all.filter(t => !STOP.has(t)) : all
  const qsq = squash(query)
  if (!toks.length) return []
  // describing words ("too HIGH", "BROKEN door") add to the score but are not required to match
  const hard = toks.filter(t => !SOFT.has(t)).length || toks.length
  // short queries: every word must match; phrases (3+ words): at least half, ranked by how many
  const need = hard >= 3 ? Math.ceil(hard / 2) : hard
  const scored: [number, SearchItem][] = []
  for (const p of prepared) {
    let total = 0, hardHit = 0
    for (const t of toks) {
      let best = 0
      for (const f of p.f) best = Math.max(best, tokenScore(t, f) * f.w)
      for (const r of RELATED[t] ?? []) for (const f of p.f) best = Math.max(best, tokenScore(r, f) * f.w * 0.8)
      if (best > 0 && (!SOFT.has(t) || hard === toks.length && toks.every(x => SOFT.has(x)))) hardHit++
      total += best
    }
    const ok = hardHit >= need
    // the whole query, squashed, against the name and the codes ("lab1" -> LAB_01, "inc12" -> INC-000012)
    let whole = 0
    if (qsq.length >= 2) {
      const pre = (k: string) => k.startsWith(qsq) && !(/\d$/.test(qsq) && /^\d/.test(k.slice(qsq.length)))
      if (p.titleSq === qsq || p.keySq.includes(qsq)) whole = 2
      else if (pre(p.titleSq) || p.keySq.some(pre)) whole = 1
      else if (p.titleSq.includes(qsq)) whole = 0.5
    }
    if (!ok && whole === 0) continue
    const s = (ok ? total / toks.length : 0) + whole + (TYPE_BOOST[p.item.type] ?? 0) - (p.item.resolved ? 0.3 : 0)
    scored.push([s, p.item])
  }
  scored.sort((a, b) => b[0] - a[0])
  return scored.slice(0, limit).map(x => x[1])
}

/** What each page is about, so "camera", "temperature" or "door" find the right page too. */
export const PAGE_WORDS: Record<string, string> = {
  '/': 'home dashboard overview summary',
  '/labs': 'labs laboratories rooms',
  '/command': 'command center operations live control room',
  '/monitor': 'live monitor wall screen',
  '/admin/security': 'security camera cameras cctv video people person tracking identity unknown lost names',
  '/admin/operations': 'operations analytics usage trends',
  '/admin/access': 'access audit door entry sessions log nfc fingerprint face denied refused granted denial',
  '/admin/bookings': 'bookings booking reservations schedule calendar denied approved',
  '/book': 'book booking reserve',
  '/admin/emergency': 'emergency evacuation fire alarm hazard',
  '/admin/equipment': 'equipment robots pcs environment consumables reusables inventory temperature humidity gas bins',
  '/admin/devices': 'devices esp32 nodes sensors firmware online offline',
  '/issues': 'maintenance issues repairs faults tickets',
  '/admin/incidents': 'incidents problems outages',
  '/admin/alerts': 'alerts alarms warnings warning high temperature gas',
  '/notifications': 'notifications messages inbox',
  '/admin/system': 'system analytics performance health',
  '/admin/reliability': 'reliability briefing uptime backups drift',
  '/admin/reports': 'reports export csv pdf',
  '/admin/users': 'users roles people students staff accounts face enrollment',
  '/admin/experiments': 'experiments research',
  '/admin/settings': 'settings configuration',
  '/profile': 'profile account me face photos',
  '/robots': 'robots arms ur5e fanuc twin',
}
