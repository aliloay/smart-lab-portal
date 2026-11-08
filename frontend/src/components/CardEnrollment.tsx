/**
 * RFID card enrollment inside Users & roles -> Enroll / Edit user.
 *
 * Same path as a finger: the portal leaves a request; the door controller
 * fetches it while idle, asks the person to tap their card (LCD + tablet),
 * stores it in its own memory for USERn - so the card works even with the
 * laptop off - and reports the card's UID, shown here. A person may hold
 * several cards (up to 5 on the door); each can be removed on its own.
 */
import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, CreditCard, Trash2, XCircle } from 'lucide-react'
import { DeviceCommand, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { fmtDateTime } from '../lib/time'
import { ErrorBanner } from './ui'

const ACTIVE = new Set(['PENDING', 'SENT', 'RUNNING'])
type Card = Awaited<ReturnType<typeof api.userCards>>[number]

const colons = (hex: string) => hex.match(/.{1,2}/g)?.join(':') ?? hex

export default function CardEnrollment({ userId, savedSubject }: {
  userId: number
  savedSubject: string | null
}) {
  const [cards, setCards] = useState<Card[] | null>(null)
  const [cmd, setCmd] = useState<DeviceCommand | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const loadCards = useCallback(() => {
    api.userCards(userId).then(setCards).catch(() => setCards([]))
  }, [userId])
  useEffect(loadCards, [loadCards])

  const refresh = useCallback((id: number) => {
    api.deviceCommand(id).then(c => {
      setCmd(c)
      if (!ACTIVE.has(c.status)) loadCards()
    }).catch(() => {})
  }, [loadCards])
  useLiveMessages(m => {
    if (m.type === 'staff' && m.kind === 'device_command' && cmd && m.command_id === cmd.id) refresh(cmd.id)
  })
  useEffect(() => {
    if (!cmd || !ACTIVE.has(cmd.status)) return
    const t = window.setInterval(() => refresh(cmd.id), 1500)
    return () => window.clearInterval(t)
  }, [cmd, refresh])

  if (!/^USER\d{1,3}$/.test(savedSubject ?? '')) {
    return <p className="text-[12px] text-slate-500">
      RFID card: save a door identity USERn first, then reopen this to enroll a card.
    </p>
  }

  async function run(remove: boolean, c?: Card) {
    if (remove && !window.confirm(`Remove card ${c ? colons(c.uid_hex) : ''} from the door? It stops opening step 1 at once.`)) return
    setBusy(true); setError('')
    try { setCmd(await (remove ? api.cardRemove(userId, c?.id) : api.cardEnroll(userId))) }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed') }
    finally { setBusy(false) }
  }
  async function cancel() {
    if (!cmd) return
    try { setCmd(await api.cancelDeviceCommand(cmd.id)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Cancel failed') }
  }

  const running = !!cmd && ACTIVE.has(cmd.status)
  const removing = cmd?.command === 'REMOVE_RFID'
  const failed = !!cmd && ['FAILED', 'EXPIRED', 'CANCELLED'].includes(cmd.status)
  const has = !!cards?.length

  return (
    <div className="rounded-lg border border-ink-600/70 bg-ink-800/40 p-3 space-y-2.5">
      <div className="flex items-center gap-2 text-sm text-slate-200">
        <CreditCard size={15} className="text-accent-300" />
        <span className="font-medium">RFID card</span>
        <span className="mono text-[11px] text-slate-400">{savedSubject}</span>
        {has && <span className="ml-auto text-[11.5px] text-slate-400">{cards!.length} card{cards!.length > 1 ? 's' : ''}</span>}
      </div>
      {has && <ul className="space-y-1">
        {cards!.map(c => (
          <li key={c.id} className="flex items-center gap-2 text-[12px]">
            <span className="mono text-ok-soft">{colons(c.uid_hex)}</span>
            <span className="text-slate-500">· {fmtDateTime(c.issued_at)}</span>
            {!running && <button type="button" className="ml-auto btn-ghost btn-sm !py-0.5" disabled={busy}
              onClick={() => run(true, c)}><Trash2 size={13} /> Remove</button>}
          </li>))}
      </ul>}
      {!has && cards && !running && (
        <p className="text-[12px] text-slate-400">No card yet. Their booking QR works for step 1 meanwhile.</p>)}

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {running && (
        <div className="flex items-center gap-2">
          <p className="flex-1 text-[12.5px] text-white">
            {cmd?.status === 'PENDING'
              ? 'Waiting for the door controller (it takes requests only while the door is idle)…'
              : removing ? 'Removing the card…' : 'Tap the card on the door\'s RFID reader now (20 s).'}</p>
          {cmd?.status === 'PENDING' &&
            <button type="button" className="btn-ghost btn-sm" onClick={cancel}>Cancel</button>}
        </div>)}
      {failed && (
        <p className="flex items-start gap-1.5 text-[12px] text-warn-soft">
          <XCircle size={14} className="shrink-0 mt-px" />
          {cmd?.message || (cmd?.status === 'EXPIRED' ? 'The request expired.' : 'Not stored.')}
        </p>)}
      {cmd?.status === 'DONE' && (
        <p className="flex items-center gap-1.5 text-[12px] text-ok-soft"><CheckCircle2 size={13} />
          {removing ? 'Card removed from the door.' : `${cmd.message || 'Card stored'}. It now works for step 1.`}</p>)}

      {!running && (
        <div className="flex gap-2">
          <button type="button" className="btn-ghost btn-sm flex-1" disabled={busy || (cards?.length ?? 0) >= 5} onClick={() => run(false)}>
            <CreditCard size={14} /> {has ? 'Add another card at the door' : 'Enroll card at the door'}</button>
        </div>)}
    </div>
  )
}
