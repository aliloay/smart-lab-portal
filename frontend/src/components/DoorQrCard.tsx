/**
 * Personal door QR, for the phone's Wallet (a pass app's "Add Code" -> QR).
 * A card that lives in a QR code: step 1 at the door, then the person's own
 * finger or face. Shown once - the portal keeps only its hash; replacing it
 * or revoking it makes the old one useless.
 */
import { useEffect, useState } from 'react'
import { Copy, QrCode, RefreshCw, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import SaveForWallet from './SaveForWallet'
import { fmtDate } from '../lib/time'

export default function DoorQrCard() {
  const [state, setState] = useState<{ active: boolean; issued_at?: string | null } | null>(null)
  const [fresh, setFresh] = useState<{ payload: string; png_base64: string | null } | null>(null)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => api.myDoorQr().then(setState).catch(() => setState(null))
  useEffect(() => { load() }, [])

  async function create() {
    if (state?.active && !confirm('Replace your door QR? The old one stops working.')) return
    setBusy(true); setMsg('')
    try { const r = await api.createMyDoorQr(); setFresh(r); setMsg(r.message); load() }
    catch (e) { setMsg(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy(false) }
  }
  async function revoke() {
    if (!confirm('Revoke your door QR? It stops working at the door.')) return
    setBusy(true)
    try { await api.revokeMyDoorQr(); setFresh(null); setMsg('Door QR revoked.'); load() }
    finally { setBusy(false) }
  }

  return (
    <div className="rounded-lg border border-ink-500/60 p-4 space-y-3">
      <div className="flex items-center gap-2 text-[13.5px] text-white font-medium">
        <QrCode size={15} className="text-accent-300" />Door QR for your phone's Wallet
        {state?.active && <span className="text-[11.5px] text-ok-soft font-normal">· active since {fmtDate(state.issued_at!)}</span>}
      </div>
      <p className="text-[12.5px] text-slate-400">
        Works like your RFID card: show it to the door camera, then your fingerprint or face.
        Add it to Wallet with a pass app ("Add Code" → QR, paste the text below). Keep it private;
        if your phone is lost, revoke it here.
      </p>
      {fresh && (
        <div className="flex flex-wrap items-start gap-4">
          {fresh.png_base64 && <img src={`data:image/png;base64,${fresh.png_base64}`} alt="Your door QR"
                                    className="w-44 h-44 rounded bg-white p-1" />}
          <div className="min-w-0 flex-1 space-y-2">
            <div className="text-[12px] text-warn-soft">Shown once - save it to Wallet now.</div>
            <code className="block break-all rounded bg-ink-900/70 p-2 text-[12px] text-slate-200">{fresh.payload}</code>
            <div className="flex flex-wrap gap-2">
              <button className="btn-ghost btn-sm" onClick={() => navigator.clipboard?.writeText(fresh.payload)}>
                <Copy size={13} />Copy text</button>
              {fresh.png_base64 && <SaveForWallet pngBase64={fresh.png_base64} text={fresh.payload}
                                                  filename="SmartLab-door-QR" />}
            </div>
          </div>
        </div>)}
      <div className="flex gap-2">
        <button className="btn-primary btn-sm" disabled={busy} onClick={create}>
          <RefreshCw size={13} />{state?.active ? 'Replace door QR' : 'Create door QR'}</button>
        {state?.active && <button className="btn-ghost btn-sm" disabled={busy} onClick={revoke}>
          <Trash2 size={13} />Revoke</button>}
      </div>
      {msg && <p className="text-[12.5px] text-accent-200">{msg}</p>}
    </div>)
}
