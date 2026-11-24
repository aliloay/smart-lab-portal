/**
 * Exhibition screen (/exhibit): full screen, read only, for visitors. It shows groups and readings, never people, camera
 * pictures, host names or a control. When the portal stops answering the open page keeps showing this browser's last real
 * values, marked HISTORICAL; with none it shows an example, marked SIMULATED. (Opening the page still needs the portal.)
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { SmartLabMark } from '../components/Brand'
import { api } from '../lib/api'
import { Snapshot, choose, recall, remember, snapshot } from '../lib/exhibit'
import { fmtDateTime } from '../lib/time'
import { visibleInterval } from '../lib/visibleInterval'

const STYLE = {
  LIVE: ['bg-ok/15 text-ok-soft border-ok/50', 'Live data from the lab'],
  HISTORICAL: ['bg-warn/15 text-warn-soft border-warn/50', 'Historical: the portal is not answering, these are the last real values'],
  SIMULATED: ['bg-violet-500/20 text-violet-200 border-violet-400/60', 'Simulated example: these are not measurements'],
} as const
const STEPS: [string, string][] = [
  ['Enter', 'Two factors at the door: card or phone code, then face or fingerprint.'],
  ['Measure', 'Small ESP32 nodes send temperature, humidity, gas, flame and motion states to the laptop.'],
  ['Decide', 'The portal stores every reading, raises alerts and keeps working without internet.'],
  ['Explain', 'A local assistant answers from stored records and says when it does not know.']]

export default function Exhibition() {
  const [live, setLive] = useState<Snapshot | null>(null)
  const [stored, setStored] = useState(recall)
  useEffect(() => {
    let on = true
    let okAt = 0
    const load = () => Promise.all([api.systemHealth(), api.metricLatest()]).then(([h, m]) => {
      if (!on) return
      okAt = Date.now()
      const s = snapshot(h.services, m, h.checked_at)
      setLive(s); setStored(s); remember(s)
    }).catch(() => { if (on) setLive(null) })
    load()
    const t = visibleInterval(load, 15000)
    // A request can hang and retry for a long time: without a good answer for 25 s the screen stops saying LIVE.
    const age = window.setInterval(() => { if (Date.now() - okAt > 25000) setLive(null) }, 2000)
    return () => { on = false; window.clearInterval(t); window.clearInterval(age) }
  }, [])
  const { source, data } = choose(live, stored)
  const [cls, text] = STYLE[source]
  const n = (k: string) => data.counts[k] ?? 0
  return (
    <main className="min-h-screen bg-ink-950 text-slate-100 p-5 sm:p-8 lg:p-12 flex flex-col gap-6">
      <header className="flex flex-wrap items-center gap-4">
        <SmartLabMark size={52} />
        <div className="mr-auto"><h1 className="font-display text-3xl lg:text-5xl font-semibold">Smart Research Laboratory</h1>
          <p className="text-slate-400 text-base lg:text-xl">German International University, local and low-cost</p></div>
        <div role="status" className={`border rounded-2xl px-5 py-3 ${cls}`}><b className="text-xl tracking-wide">{source}</b><div className="text-sm">{text}</div></div>
      </header>
      <section className="grid gap-4 sm:grid-cols-3" aria-label="System state">
        {([['Parts online', n('ONLINE')], ['Not up to date', n('STALE') + n('DEGRADED') + n('UNKNOWN')], ['Offline', n('OFFLINE')]] as [string, number][]).map(([l, v]) => (
          <div key={l} className="card p-6"><div className="text-slate-400 text-lg">{l}</div><div className="font-display text-6xl font-semibold tnum">{v}</div></div>))}
      </section>
      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card p-6"><h2 className="text-xl font-semibold mb-3">The lab now</h2>
          <ul className="space-y-2 text-lg">{data.parts.map(p => <li key={p.name} className="flex justify-between gap-4"><span className="text-slate-300">{p.name}</span><span className="tnum">{p.state}</span></li>)}</ul></div>
        <div className="card p-6"><h2 className="text-xl font-semibold mb-3">Environment</h2>
          {data.readings.length === 0 ? <p className="text-slate-400 text-lg">No stored reading.</p> :
            <ul className="space-y-2 text-lg">{data.readings.map((r, i) => <li key={i} className="flex flex-wrap justify-between gap-x-4"><span className="text-slate-300">{r.label}</span>
              <span className={`tnum ${r.live && source === 'LIVE' ? '' : 'text-slate-400'}`}>{r.value} <small>({source === 'HISTORICAL' && r.live ? 'at the time below' : r.note})</small></span></li>)}</ul>}
          <p className="mt-4 text-sm text-slate-500">Indicators, not certified fire or gas detectors.</p></div>
      </section>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{STEPS.map(([t, d], i) => (
        <div key={t} className="card p-5"><div className="text-accent-300 text-lg font-semibold">{i + 1}. {t}</div><p className="text-slate-300 mt-1">{d}</p></div>))}</section>
      <footer className="mt-auto flex flex-wrap gap-4 text-sm text-slate-500">
        <span>{source === 'SIMULATED' ? 'Example values' : `Checked ${fmtDateTime(data.at)}`}</span>
        <span>Read only. No names, no camera pictures, no controls.</span>
        <Link to="/" className="ml-auto text-slate-500 hover:text-slate-300">Leave the exhibition screen</Link>
      </footer>
    </main>
  )
}
