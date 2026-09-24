/**
 * Time helpers.
 *
 * The API speaks UTC ISO8601 throughout. Everything shown to a person is
 * rendered in their own locale and timezone by the browser, and everything
 * sent back is converted to UTC. Nothing compares naive local strings.
 */

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

export const fmtTimeSec = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit',
                                         second: '2-digit', hour12: false })

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' })

export const fmtDateLong = (iso: string) =>
  new Date(iso).toLocaleDateString([], { weekday: 'long', day: 'numeric',
                                         month: 'long', year: 'numeric' })

export const fmtDateTime = (iso: string) =>
  `${fmtDate(iso)}, ${fmtTime(iso)}`

export const fmtClock = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour12: false })

/** Turn local date + time inputs into a UTC ISO string for the API. */
export function localToUtcIso(date: string, time: string): string {
  return new Date(`${date}T${time}`).toISOString()
}

/** Local midnight-to-midnight bounds of a YYYY-MM-DD date, as UTC ISO. */
export function localDayBounds(date: string): [string, string] {
  const start = new Date(`${date}T00:00`)
  const end = new Date(start)
  end.setDate(end.getDate() + 1)
  return [start.toISOString(), end.toISOString()]
}

/** Countdown text, e.g. "starts in 2h 14m" or "43m remaining". */
export function countdown(fromIso: string, untilIso: string): string {
  const now = Date.now()
  const start = new Date(fromIso).getTime()
  const end = new Date(untilIso).getTime()

  if (now < start) return `starts in ${humanGap(start - now)}`
  if (now > end) return 'ended'
  return `${humanGap(end - now)} remaining`
}

export function humanGap(ms: number): string {
  const mins = Math.max(0, Math.floor(ms / 60000))
  if (mins < 1) return 'under a minute'
  if (mins < 60) return `${mins}m`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (h < 24) return m ? `${h}h ${m}m` : `${h}h`
  return `${Math.floor(h / 24)}d ${h % 24}h`
}

/** "01h 28m" style, for measured durations. */
export function fmtDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m`
}

export const relative = (iso: string): string => {
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 0) return `in ${humanGap(-diff)}`
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return `${Math.floor(diff / 86_400_000)}d ago`
}

export const pad2 = (n: number) => String(n).padStart(2, '0')

export function dateStr(d: Date) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

export const todayStr = () => dateStr(new Date())

export function greeting() {
  const h = new Date().getHours()
  if (h < 5) return 'Working late'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}
