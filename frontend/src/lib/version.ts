/**
 * Reload an open tab once per NEW deployment (2026-10-19). The deployed build id is the one
 * tools/deploy/deploy.py stamps into backend/app/build_info.json and /api/health serves as version.id
 * (backend and frontend are built and deployed together). The old guard allowed one automatic reload
 * per page per browser session, so a second deploy in the same session left the tab on stale code.
 *
 *  - first answer seen in this tab = the version the tab runs: remembered, no reload
 *  - a different id later = a real new deploy: reload once for THAT id (sessionStorage), never again for it
 *  - endpoint down / no version = do nothing (no reload loops on errors)
 */
const KEY = 'slp.reloadedForVersion'

export type Decision = 'remember' | 'reload' | 'none'

/** Pure: what to do with one /api/health answer. */
export function decide(seen: string | null, latest: string | null, reloadedFor: string | null): Decision {
  if (!latest) return 'none'                       // unavailable metadata: never reload on it
  if (seen === null) return 'remember'
  if (latest === seen) return 'none'
  if (latest === reloadedFor) return 'none'        // already reloaded once for this deploy
  return 'reload'
}

export async function deployedVersion(): Promise<string | null> {
  try {
    const r = await fetch('/api/health', { cache: 'no-store' })
    if (!r.ok) return null
    const id = (await r.json())?.version?.id
    return typeof id === 'string' && id ? id : null
  } catch {
    return null
  }
}

function reloadedFor(): string | null {
  try { return sessionStorage.getItem(KEY) } catch { return null }
}

/** Reload once for version `v`; false when that already happened (or storage is blocked: no loop risk). */
export function reloadOnceFor(v: string): boolean {
  try {
    if (sessionStorage.getItem(KEY) === v) return false
    sessionStorage.setItem(KEY, v)
  } catch {
    return false
  }
  location.reload()
  return true
}

let seen: string | null = null
let started = false

/** Poll the deployed version (every minute and when the tab becomes visible again). */
export function watchDeployments(everyMs = 60_000): void {
  if (started) return
  started = true
  const tick = async () => {
    const latest = await deployedVersion()
    const d = decide(seen, latest, reloadedFor())
    if (d === 'remember') seen = latest
    else if (d === 'reload' && latest) reloadOnceFor(latest)
  }
  tick()
  window.setInterval(tick, everyMs)
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') tick() })
}
