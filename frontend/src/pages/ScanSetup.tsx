/**
 * "Scan the lab" helpers (2026-10-26):
 *   /scan/markers  printable QR markers for every asset in the registry (devices, consumables bins, equipment) -
 *                  each marker's text is the asset's own record key, so a scan can only ever mean that record.
 *   /phone-setup   open the portal on a phone over https:// (the camera and microphone need a secure page):
 *                  a self-check, the Smart Lab CA download and the trust steps, and a QR to hand over from a PC.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Download, Printer, ShieldAlert, XCircle } from 'lucide-react'
import { getToken, scanMarkersPdf } from '../lib/api'
import { Chip, Skeleton } from '../components/ui'

interface MarkerCard { code: string; key: string; kind: string; name: string; type: string; lab_code: string | null
  category: string; color: string; label: string; source: string; img: string }

// Illustrated markers (2026-10-27, owner: "a partially opened door with the QR on the door, a 3D 6-DOF robot, a camera whose
// lens is the QR"): the owner's own object pictures with the REAL flat QR (portal encoder, ECC H) drawn into each white
// panel by e2e/qr_place_on_images.py (door: a sticker below the handle), decode-checked (jsQR 80/80, OpenCV 48/50 - the
// 2 misses only at 337 px thumbnail size). Only these registered assets have a picture; others keep the pack artwork.
const ART: Record<string, string> = {
  'SLAB:D:CAM_LAB01': 'entry-camera', 'SLAB:D:FACESRV_01': 'face-server', 'SLAB:D:MASTER_LAB01': 'door-master',
  'SLAB:D:PC_ADMIN_LAPTOP': 'admin-laptop', 'SLAB:D:UR5E_01': 'ur5e-robot', 'SLAB:D:FANUC_01': 'fanuc-robot',
  'SLAB:D:BIN_NODE_1': 'consumables-bin', 'SLAB:D:SECCAM_LAB01': 'security-camera', 'SLAB:D:REUSE_BIN_1': 'reusable-bin',
  'SLAB:D:PC_01': 'student-pc', 'SLAB:D:SECCAM_LAB02': 'security-camera-2',
}
type Style = 'art' | 'pack' | 'shape'

export function ScanMarkers() {
  // ONE request for the whole page (2026-10-27, owner: "the markers are freezing and loading a lot"): the backend
  // returns every marker with its artwork inline (cached, pre-rendered at start-up). Print prints these same cards.
  const [style, setStyle] = useState<Style>(() => { try { const v = localStorage.getItem('smartlab.markerStyle'); return v === 'shape' || v === 'pack' ? v : 'art' } catch { return 'art' } })
  const [kind, setKind] = useState<'all' | 'device' | 'bin' | 'asset'>('all')
  const [cards, setCards] = useState<MarkerCard[] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let live = true
    setCards(null); setError('')
    const token = getToken()
    fetch(`/api/scan/markers.json?kind=${kind}&style=${style === 'art' ? 'pack' : style}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`Markers could not load (${r.status})`)))
      .then(d => { if (live) setCards(d.markers) }).catch(e => { if (live) setError(e.message) })
    try { localStorage.setItem('smartlab.markerStyle', style) } catch { /* private mode */ }
    return () => { live = false }
  }, [kind, style])
  const printNow = () => {
    setError('')
    document.body.classList.add('printing-markers')
    const done = () => { document.body.classList.remove('printing-markers'); window.removeEventListener('afterprint', done) }
    window.addEventListener('afterprint', done)
    window.print()
    setTimeout(done, 60_000)
  }
  const downloadPdf = async () => {
    setBusy(true); setError('')
    try {
      const url = URL.createObjectURL(await scanMarkersPdf(kind, style === 'art' ? 'art' : 'pack'))
      const a = document.createElement('a'); a.href = url; a.download = `smartlab_markers_${kind}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (e) { setError(e instanceof Error ? e.message : 'PDF failed') }
    finally { setBusy(false) }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap print:hidden">
        <h1 className="text-[18px] font-semibold text-white">Asset markers</h1>
        <span className="text-[12px] text-slate-400">Print, cut out, stick on a flat visible face (≥ 6 cm wide). One marker = one record.</span>
        <div className="ml-auto flex rounded-lg border border-ink-600 p-0.5" role="group" aria-label="Marker style">
          {([['art', 'Illustrated'], ['pack', 'Marker pack'], ['shape', 'Object shape']] as const).map(([k, t]) => (
            <button key={k} type="button" aria-pressed={style === k} onClick={() => setStyle(k)}
                    className={`rounded-md px-2.5 py-1 text-[12px] ${style === k ? 'bg-accent-500/25 text-white' : 'text-slate-400 hover:text-white'}`}>{t}</button>))}
        </div>
        <select className="input !w-auto" value={kind} onChange={e => setKind(e.target.value as typeof kind)}>
          <option value="all">All</option><option value="device">Devices</option><option value="bin">Consumables bins</option>
          <option value="asset">Equipment / reusable items</option></select>
        <button className="btn-primary btn-sm" disabled={!cards?.length} onClick={printNow}><Printer size={14} /> Print</button>
        <button className="btn-ghost btn-sm" disabled={busy} onClick={downloadPdf}>
          <Download size={14} /> {busy ? 'Preparing…' : 'Download PDF'}</button>
        <Link to="/scan" className="btn-ghost btn-sm">Back to scanning</Link>
      </div>
      {error && <p className="text-bad-soft text-[13px]">{error}</p>}
      {!cards ? <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="aspect-[4/5] rounded-2xl" />)}</div> : (
        <div id="marker-sheet" className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {cards.map(c0 => {
            const art = style === 'art' ? ART[c0.code] : undefined
            const look: Style = art ? 'art' : style === 'art' ? 'pack' : style
            const c = art ? { ...c0, img: `/markers/art/${art}.webp` } : c0
            return (
            <div key={c.code} className="marker-card overflow-hidden rounded-2xl border border-slate-200 bg-white text-center shadow-sm">
              {look === 'pack' && <div className="h-2" style={{ background: c.color }} />}
              <img src={c.img} alt={`QR marker ${c.code} - ${c.name}`} className={look === 'pack' ? 'mx-auto block w-[92%] aspect-square object-contain' : look === 'art' ? 'block w-full aspect-[4/5] object-contain' : 'block w-full'}
                   loading="lazy" decoding="async" />
              {look === 'art' && <div className="px-2 pb-2 text-[12.5px] font-semibold text-slate-900 leading-tight">
                {c.name}{c.name.includes(c.key) ? '' : <span className="font-normal text-slate-500"> · {c.key}</span>}</div>}
              {look === 'pack' && <div className="px-2 pb-2.5">
                <div className="text-[13px] font-semibold text-slate-900 leading-tight">{c.name}</div>
                <div className="mt-0.5 text-[10.5px] font-medium" style={{ color: c.color }}>{c.key} · {c.label}{c.lab_code ? ` · ${c.lab_code}` : ''}</div>
              </div>}
            </div>)})}
        </div>)}
    </div>
  )
}

export function PhoneSetup() {
  const secure = window.isSecureContext
  const cam = !!navigator.mediaDevices?.getUserMedia
  const httpsUrl = `https://${window.location.hostname}/scan`
  const [qr, setQr] = useState('')
  useEffect(() => {
    let u = ''
    const token = getToken()
    fetch(`/api/scan/link.png?url=${encodeURIComponent(httpsUrl)}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => r.ok ? r.blob() : null).then(b => { if (b) { u = URL.createObjectURL(b); setQr(u) } }).catch(() => {})
    return () => { if (u) URL.revokeObjectURL(u) }
  }, [httpsUrl])
  const Row = ({ ok, children }: { ok: boolean; children: React.ReactNode }) =>
    <li className="flex gap-2 items-start">{ok ? <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
      : <XCircle size={16} className="text-bad-soft shrink-0 mt-0.5" />}<span>{children}</span></li>
  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-[18px] font-semibold text-white">Set up a phone for Scan the lab</h1>
      <div className="card p-4 space-y-2 text-[13.5px]">
        <div className="font-medium text-slate-200">This device, right now</div>
        <ul className="space-y-1.5 text-slate-300">
          <Row ok={secure}>Secure page (https://){secure ? '' : ` - you opened ${window.location.protocol}//. Open ${httpsUrl} instead.`}</Row>
          <Row ok={cam}>Camera available to the browser{cam ? '' : ' - needs the secure page (above) and a browser with camera access'}</Row>
        </ul>
        {secure && cam && <Link to="/scan" className="btn-primary btn-sm inline-flex mt-1">Open Scan the lab</Link>}
      </div>
      <div className="card p-4 space-y-3 text-[13.5px] text-slate-300">
        <div className="font-medium text-slate-200">Once per phone: trust the Smart Lab certificate</div>
        <p>The lab network has no internet, so the portal's https certificate comes from the lab's own authority. Install
          its public certificate once; the browser then opens https:// without a warning. Security is never switched off.</p>
        <a href="/smartlab-ca.crt" className="btn-ghost btn-sm inline-flex"><Download size={14} /> Download the Smart Lab CA certificate</a>
        <div className="grid sm:grid-cols-2 gap-3">
          <div><div className="font-medium text-slate-200 mb-1">Android</div><ol className="list-decimal pl-5 space-y-1">
            <li>Download the certificate (above).</li><li>Settings → Security → More security settings → Install from device
              storage → <b>CA certificate</b> → pick smartlab-ca.crt.</li><li>Open {httpsUrl} in Chrome.</li></ol></div>
          <div><div className="font-medium text-slate-200 mb-1">iPhone</div><ol className="list-decimal pl-5 space-y-1">
            <li>Download in Safari → Allow → Settings → Profile Downloaded → Install.</li>
            <li>Settings → General → About → <b>Certificate Trust Settings</b> → turn on Smart Lab CA.</li>
            <li>Open {httpsUrl} in Safari.</li></ol></div>
        </div>
        <p className="text-[12px] text-slate-500 flex gap-1.5"><ShieldAlert size={14} className="shrink-0 mt-0.5" />Only the public
          certificate is offered here; the authority's private key never leaves the lab laptop.</p>
      </div>
      <div className="card p-4 flex gap-4 items-center flex-wrap">
        {qr ? <img src={qr} alt="QR code to open Scan the lab on a phone" className="w-40 h-40 bg-white rounded" /> : <Skeleton className="w-40 h-40" />}
        <div className="text-[13.5px] text-slate-300 space-y-1">
          <div className="font-medium text-slate-200">From a PC: hand over to the phone</div>
          <p>Scan this with the phone's camera to open <span className="mono">{httpsUrl}</span>, then sign in on the phone.</p>
          <p className="text-[12px] text-slate-500">A PC browser cannot use a separate phone's camera - the phone runs the scanner itself.</p>
          <Chip tone="idle">phone on the Smart_Lab Wi-Fi</Chip>
        </div>
      </div>
    </div>
  )
}
