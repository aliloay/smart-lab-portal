/**
 * Open tabs pick up a new portal version (2026-10-21). A tab left open keeps running the code it loaded -
 * a fix deployed since (e.g. the screen-share preview) never reached it. Every minute the tab compares the
 * main script in the live index.html with its own; once they differ it reloads on the next page change
 * (nothing is lost mid-task), and `outdated` lets the layout offer a Reload button meanwhile.
 */
import { useEffect, useState } from 'react'

const mine = () => [...document.scripts].map(s => s.getAttribute('src') || '').find(s => /\/assets\/index-.*\.js$/.test(s)) ?? null

async function liveScript(): Promise<string | null> {
  try {
    const r = await fetch('/', { cache: 'no-store' })
    const m = (await r.text()).match(/\/assets\/index-[^"']+\.js/)
    return m ? m[0] : null
  } catch { return null }
}

export function useNewVersion(path: string): boolean {
  const [outdated, setOutdated] = useState(false)
  useEffect(() => {
    const own = mine()
    if (!own) return                               // dev server: no hashed bundle
    const check = () => { void liveScript().then(s => { if (s && !own.endsWith(s)) setOutdated(true) }) }
    const t = window.setInterval(check, 60000)
    const vis = () => { if (document.visibilityState === 'visible') check() }
    document.addEventListener('visibilitychange', vis)
    check()
    return () => { window.clearInterval(t); document.removeEventListener('visibilitychange', vis) }
  }, [])
  // a page change while outdated: load the new version for that page
  const [first] = useState(path)
  useEffect(() => { if (outdated && path !== first) window.location.reload() }, [path, outdated, first])
  return outdated
}
