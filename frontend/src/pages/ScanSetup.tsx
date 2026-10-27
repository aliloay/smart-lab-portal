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
import { ScanRegistryItem, api, getToken, scanMarkerBlob, scanMarkerSvg, scanMarkersPdf } from '../lib/api'
import { Chip, Skeleton } from '../components/ui'

// the owner's marker pack colours per category (presentation only - the registry and payloads come from the backend)
const PACK: Record<string, [string, string]> = { camera: ['#6426a8', 'CAMERA'], server: ['#562099', 'SERVER'], door: ['#075f59', 'DOOR'],
  pc: ['#1557ad', 'PC'], robot: ['#b84300', 'ROBOT'], inventory: ['#976000', 'INVENTORY'], security: ['#a71f31', 'SECURITY'],
  reusable: ['#0e6e83', 'REUSABLES'], environment: ['#15803d', 'ENVIRONMENT'], equipment: ['#334155', 'EQUIPMENT'] }

export function ScanMarkers() {
  // previews: vector QR (SVG) in an HTML card; printing: the 300-dpi PNG cards (loaded after the previews)
  const [svgs, setSvgs] = useState<Record<string, { url: string; category: string; source: string }>>({})
  const [items, setItems] = useState<ScanRegistryItem[] | null>(null)
  const [urls, setUrls] = useState<Record<string, string>>({})
  const [kind, setKind] = useState<'all' | 'device' | 'bin' | 'asset'>('all')
  const [error, setError] = useState('')
  useEffect(() => { api.scanRegistry().then(r => setItems(r.assets)).catch(e => setError(e.message)) }, [])
  const shown = useMemo(() => (items ?? []).filter(i => kind === 'all' || i.kind === kind), [items, kind])
  useEffect(() => {
    let live = true
    const made: string[] = []
    ;(async () => {
      for (const i of shown) {                          // previews first, one at a time
        if (!live || svgs[i.code]) continue
        try {
          const r = await scanMarkerSvg(i.code)
          const u = URL.createObjectURL(r.blob)
          if (live) setSvgs(m => ({ ...m, [i.code]: { url: u, category: r.category, source: r.source } }))
        } catch { /* the card shows its name only */ }
      }
      for (const i of shown) {                          // then the print cards
        if (!live || urls[i.code]) continue
        try {
          const u = URL.createObjectURL(await scanMarkerBlob(i.code)); made.push(u)
          if (live) setUrls(m => ({ ...m, [i.code]: u }))
        } catch { /* the card just shows no image */ }
      }
    })()
    return () => { live = false }
  }, [shown])                                           // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { Object.values(urls).forEach(u => URL.revokeObjectURL(u)); Object.values(svgs).forEach(v => URL.revokeObjectURL(v.url)) }, [])   // eslint-disable-line
  // Print (2026-10-27, owner: Print did nothing, then a grey box): the portal's security policy does not allow a PDF
  // viewer inside the page, so Print prints the marker sheet itself - the same print-resolution images, A4, three
  // per row at 6.3 cm (index.css, body.printing-markers). Download PDF gives the file for any other printer/phone.
  const [busy, setBusy] = useState<'' | 'print' | 'pdf'>('')
  const allLoaded = shown.length > 0 && shown.every(i => urls[i.code])
  const printNow = () => {
    if (!allLoaded) { setError('Markers are still loading - try again in a moment.'); return }
    setError('')
    document.body.classList.add('printing-markers')
    const done = () => { document.body.classList.remove('printing-markers'); window.removeEventListener('afterprint', done) }
    window.addEventListener('afterprint', done)
    window.print()
    setTimeout(done, 60_000)                               // browsers without afterprint
  }
  const downloadPdf = async () => {
    setBusy('pdf'); setError('')
    try {
      const url = URL.createObjectURL(await scanMarkersPdf(kind))
      const a = document.createElement('a'); a.href = url; a.download = `smartlab_markers_${kind}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (e) { setError(e instanceof Error ? e.message : 'PDF failed') }
    finally { setBusy('') }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap print:hidden">
        <h1 className="text-[18px] font-semibold text-white">Asset markers</h1>
        <span className="text-[12px] text-slate-400">Print, cut out, stick on a flat visible face (≥ 6 cm wide). One marker = one record.</span>
        <select className="input !w-auto ml-auto" value={kind} onChange={e => setKind(e.target.value as typeof kind)}>
          <option value="all">All</option><option value="device">Devices</option><option value="bin">Consumables bins</option>
          <option value="asset">Equipment / reusable items</option></select>
        <button className="btn-primary btn-sm" disabled={!allLoaded} onClick={printNow}>
          <Printer size={14} /> {allLoaded ? 'Print' : 'Loading…'}</button>
        <button className="btn-ghost btn-sm" disabled={busy === 'pdf'} onClick={downloadPdf}>
          <Download size={14} /> {busy === 'pdf' ? 'Preparing…' : 'Download PDF'}</button>
        <Link to="/scan" className="btn-ghost btn-sm">Back to scanning</Link>
      </div>
      {error && <p className="text-bad-soft text-[13px]">{error}</p>}
      {/* the sheet that prints (hidden on screen) */}
      <div id="marker-sheet" className="hidden" aria-hidden>
        {shown.map(i => urls[i.code] && <img key={i.code} src={urls[i.code]} alt="" />)}
      </div>
      {!items ? <Skeleton className="h-60" /> : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {shown.map(i => {
            const v = svgs[i.code]
            const [color, label] = PACK[v?.category ?? 'equipment'] ?? PACK.equipment
            return (
              <div key={i.code} className="overflow-hidden rounded-2xl border border-slate-200 bg-white text-center shadow-sm">
                <div className="h-2" style={{ background: color }} />
                {v ? <img src={v.url} alt={`QR marker ${i.code} - ${i.name}`} className="mx-auto block w-[92%]" />
                  : <div className="aspect-square grid place-items-center text-[12px] text-slate-400">loading…</div>}
                <div className="px-2 pb-2.5">
                  <div className="text-[13px] font-semibold text-slate-900 leading-tight">{i.name}</div>
                  <div className="mt-0.5 text-[10.5px] font-medium" style={{ color }}>{i.key} · {label}{i.lab_code ? ` · ${i.lab_code}` : ''}</div>
                  {v?.source === 'pack' && <div className="text-[9.5px] text-slate-400">from the marker pack (verified payload)</div>}
                </div>
              </div>)
          })}
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
