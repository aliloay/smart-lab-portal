/**
 * "Save QR for Wallet": shares (iPhone share sheet) or downloads the QR as an
 * image, and copies its text, so a pass app's "Add Code -> QR" can take it.
 * A real "Add to Apple Wallet" (.pkpass) needs a pass certificate from an
 * Apple Developer account; until then this is the way into Wallet.
 */
import { useState } from 'react'
import { Wallet } from 'lucide-react'

export default function SaveForWallet({ pngBase64, text, filename }: {
  pngBase64: string; text: string; filename: string
}) {
  const [note, setNote] = useState('')

  async function save() {
    setNote('')
    try { await navigator.clipboard?.writeText(text) } catch { /* not allowed: fine */ }
    const bytes = Uint8Array.from(atob(pngBase64), c => c.charCodeAt(0))
    const file = new File([bytes], `${filename}.png`, { type: 'image/png' })
    const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean }
    try {
      if (nav.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: filename })
      } else {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(file); a.download = file.name; a.click()
        setTimeout(() => URL.revokeObjectURL(a.href), 5000)
      }
      setNote('Saved. The code text is also copied - in the pass app use Add Code → QR.')
    } catch { /* share sheet closed */ }
  }

  return (
    <div className="space-y-1">
      <button type="button" className="btn-ghost btn-sm" onClick={save}>
        <Wallet size={14} />Save QR for Wallet</button>
      {note && <p className="text-[11.5px] text-slate-400">{note}</p>}
    </div>)
}
