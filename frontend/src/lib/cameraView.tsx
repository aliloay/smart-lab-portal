/**
 * "Detection boxes" on or off, for every camera view on this screen.
 *
 * Only what this viewer SEES changes: with boxes off the views show the plain
 * picture (/raw.jpg). Detection, tracking, names and events keep running on
 * the laptop exactly the same, at the same speed. Kept per browser, like a
 * remembered tab.
 */
import { useEffect, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

const KEY = 'smartlab.camera.boxes'
const EVENT = 'smartlab:camera-boxes'

export function boxesShown(): boolean {
  try { return localStorage.getItem(KEY) !== 'off' } catch { return true }
}

export function setBoxesShown(on: boolean) {
  try { localStorage.setItem(KEY, on ? 'on' : 'off') } catch { /* private mode: this page only */ }
  window.dispatchEvent(new Event(EVENT))
}

export function useBoxesShown(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(boxesShown)
  useEffect(() => {
    const h = () => setOn(boxesShown())
    window.addEventListener(EVENT, h)
    window.addEventListener('storage', h)
    return () => { window.removeEventListener(EVENT, h); window.removeEventListener('storage', h) }
  }, [])
  return [on, setBoxesShown]
}

/** "Detection boxes ON / OFF" - the same switch everywhere a camera is shown. */
export function BoxesToggle({ dark = false }: { dark?: boolean }) {
  const [on, set] = useBoxesShown()
  return (
    <button onClick={e => { e.stopPropagation(); set(!on) }} aria-pressed={on}
      title={on ? 'Show the clear picture (detection keeps running)' : 'Show the detection boxes'}
      className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[12.5px] font-semibold transition
        ${on ? 'border-accent-400/50 bg-accent-500/15 text-accent-100'
             : dark ? 'border-white/30 text-slate-200 hover:bg-white/10' : 'border-ink-500 text-slate-300 hover:bg-white/5'}`}>
      {on ? <Eye size={14} /> : <EyeOff size={14} />} Detection boxes {on ? 'ON' : 'OFF'}</button>
  )
}
