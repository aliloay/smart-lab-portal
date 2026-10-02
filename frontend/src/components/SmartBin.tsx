/**
 * The lab's reusable smart bin (System 3): its NFC-tagged items.
 *
 * Anyone inside the lab can take an available item: the bin opens, they
 * take it and scan its tag at the bin - only the chosen item's own tag
 * completes the checkout. Returning: scan the item at the bin. Staff also
 * see who holds what and the tag of each item.
 */
import { useCallback, useEffect, useState } from 'react'
import { Boxes, PackageOpen, Wifi, WifiOff } from 'lucide-react'
import { BinItem, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import { Chip, ErrorBanner, SectionTitle } from './ui'

const TONE: Record<BinItem['status'], 'ok' | 'warn' | 'idle' | 'bad'> = {
  AVAILABLE: 'ok', CHECKED_OUT: 'warn', MAINTENANCE: 'bad', RETIRED: 'idle',
}

export default function SmartBin({ labId }: { labId: number }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.binItems>> | null>(null)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)

  const load = useCallback(() => { api.binItems(labId).then(setData).catch(() => setData(null)) }, [labId])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 15000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => {
    if ((m.type === 'access_event' && m.event.lab_id === labId) ||
        (m.type === 'staff' && m.kind === 'device_command')) load()
  })

  if (!data || (!data.items.length && !data.bin_device)) return null

  async function take(item: BinItem) {
    setBusy(item.id); setError(''); setMsg('')
    try { setMsg((await api.takeFromBin(item.id)).message) }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy(null) }
  }

  return (
    <section>
      <SectionTitle icon={<Boxes size={15} />}
        sub="NFC-tagged equipment: take it here, scan it at the bin.">Smart bin</SectionTitle>
    <div className="card p-4 space-y-3">
      <div className="flex items-center gap-2 text-[12.5px]">
        {data.bin_online ? <span className="inline-flex items-center gap-1 text-ok-soft"><Wifi size={13} /> Bin online</span>
          : <span className="inline-flex items-center gap-1 text-warn-soft"><WifiOff size={13} /> Bin offline</span>}
        <span className="text-slate-500">· return an item by scanning it at the bin</span>
      </div>
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {msg && <p className="text-[13px] text-accent-200">{msg}</p>}
      {!data.items.length ? <p className="text-[12.5px] text-slate-500">No tagged items yet.</p> : (
        <ul className="divide-y divide-ink-600/50">
          {data.items.map(i => (
            <li key={i.id} className="py-2 flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-[13.5px] text-white truncate">{i.name}</div>
                <div className="text-[11.5px] text-slate-400">
                  <span className="mono">{i.asset_tag}</span>
                  {i.holder && <> · with <b className="text-slate-200">{i.holder}</b></>}
                  {i.checked_out_at && <> · {relative(i.checked_out_at)}</>}
                </div>
              </div>
              <Chip tone={TONE[i.status]}>{i.status.replace('_', ' ').toLowerCase()}</Chip>
              {i.status === 'AVAILABLE' && (
                <button className="btn-ghost btn-sm" disabled={!data.bin_online || !data.inside || busy !== null}
                        title={!data.inside ? 'Available while you are inside the lab' : undefined}
                        onClick={() => take(i)}>
                  <PackageOpen size={14} /> {busy === i.id ? 'Opening…' : 'Take'}</button>)}
            </li>))}
        </ul>)}
      {!data.inside && data.items.some(i => i.status === 'AVAILABLE') &&
        <p className="text-[11.5px] text-slate-500">You can take items while you are inside the lab.</p>}
    </div>
    </section>
  )
}
