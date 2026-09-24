/**
 * Time helpers.
 *
 * The API speaks UTC ISO8601 throughout. Everything shown to a person is
 * rendered in their own locale and timezone by the browser, and everything
 * sent back is converted to UTC. Nothing compares naive local strings.
 */

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' })

export const fmtDateTime = (iso: string) =>
  `${fmtDate(iso)}, ${fmtTime(iso)}`

export const fmtClock = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour12: false })

/** Turn local date + time inputs into a UTC ISO string for the API. */
export function localToUtcIso(date: string, time: string): string {
  return new Date(`${date}T${time}`).toISOString()
}

/** Countdown text, e.g. "in 2h 14m" or "43m left". Returns null when over. */
export function countdown(fromIso: string, untilIso: string): string {
  const now = Date.now()
  const start = new Date(fromIso).getTime()
  const end = new Date(untilIso).getTime()

  if (now < start) return `starts in ${humanGap(start - now)}`
  if (now > end) return 'expired'
  return `${humanGap(end - now)} remaining`
}

function humanGap(ms: number): string {
  const mins = Math.floor(ms / 60000)
  if (mins < 60) return `${mins}m`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (h < 24) return m ? `${h}h ${m}m` : `${h}h`
  return `${Math.floor(h / 24)}d ${h % 24}h`
}

export const relative = (iso: string): string => {
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return `${Math.floor(diff / 86_400_000)}d ago`
}
