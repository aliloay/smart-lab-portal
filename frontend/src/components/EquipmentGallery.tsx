import { useEffect, useState } from 'react'

// Model / category photos (Wikimedia Commons, free licences) - NOT photos of
// our labs. Fetched by tools/fetch_lab_images.py; attribution shown per card.
interface Photo { kind?: string; file: string; label: string; title: string; source: string; author: string; licence: string }

// What is in each lab (owner's list). `photo` = key in ATTRIBUTION.json; no
// photo = text card until our own photo is taken.
interface Item { label: string; photo?: string; note?: string; image?: string; imageAlt?: string; spec?: string[] }
export const BY_LAB: Record<string, Item[]> = {
  // Generated concept renders (owner's assets); the original photos stay as the fallback.
  LAB_01: [{ label: 'Universal Robots UR5e (mounted inverted)', photo: 'our-ur5e', spec: ['6 axes', '5 kg', '850 mm reach', 'Robotiq 2F-85'], image: '/assets/labs/ur5e-exploded-concept.png',
             imageAlt: 'Illustrative exploded concept of the inverted UR5e with its gripper' },
           { label: 'FANUC ER-4iA (R-30iB Mate Plus)', photo: 'our-fanuc', spec: ['6 axes', '4 kg', '550 mm reach', 'R-30iB Mate Plus'], image: '/assets/labs/fanuc-exploded-concept.png',
             imageAlt: 'Illustrative exploded concept of the FANUC ER-4iA' },
           { label: 'Lab PCs', photo: 'our-pcs' },
           { label: 'Conveyor belt', photo: 'conveyor', image: '/assets/labs/conveyor-with-support-legs.png',
             imageAlt: 'Illustration of the conveyor belt on its support legs' }],
  LAB_02: [{ label: 'Siemens SIMATIC S7-1200 PLC', photo: 's7-1200', note: '8 stations' },
           { label: 'PC per PLC station', photo: 'workstation', note: '8 stations' }],
  LAB_03: [{ label: 'Drilling machine', photo: 'drill-press' }, { label: 'Cutting and sheet-metal tools', photo: 'sheet-metal' }],
  LAB_04: [{ label: 'Tensile testing machine', photo: 'tensile' }, { label: 'Bending test machine', photo: 'bending' }],
  LAB_05: [{ label: 'BMW i3 (electric hatchback)', photo: 'bmw-i3' }, { label: 'Gears and transmission', photo: 'gearbox' },
           { label: 'Steering system', photo: 'steering' }],
  LAB_06: [{ label: 'PCB prototyping machine', photo: 'pcb-mill' }, { label: 'Soldering station', photo: 'soldering' }],
  LAB_07: [{ label: 'PCs with Proteus simulation', photo: 'proteus', note: 'installed on all PCs' },
           { label: 'ATmega microcontroller boards', photo: 'atmega' }, { label: 'ESP32 boards', photo: 'esp32' }],
  LAB_08: [{ label: 'Process water tanks' }, { label: 'SCADA system' }, { label: 'HMI panels' },
           { label: 'MATLAB (licence USB keys)', photo: 'matlab' }],
  LAB_09: [{ label: 'Laser cutter', photo: 'laser-cutter' }, { label: 'Wood-cutting equipment', photo: 'woodcut' },
           { label: 'Jewelry-making tools', photo: 'jewelry' }],
  LAB_11: [{ label: 'Sewing machines', photo: 'sewing' }, { label: 'Mannequins', photo: 'mannequin', note: 'many' },
           { label: 'Threads and fabrics', photo: 'thread' }],
}

let cache: Promise<Record<string, Photo>> | null = null
const load = () => (cache ??= fetch('/equipment/ATTRIBUTION.json').then(r => r.ok ? r.json() : {}).catch(() => ({})) as Promise<Record<string, Photo>>)

// The Robotics Lab's gallery is deliberately TECHNICAL (blueprint grid, corner marks, spec tags,
// monospace) - the cinematic motion stays on the lab's outside card. Static CSS only.
const TECH = new Set(['LAB_01'])
const Corners = () => <>{['top-1.5 left-1.5 border-t border-l', 'top-1.5 right-1.5 border-t border-r',
  'bottom-1.5 left-1.5 border-b border-l', 'bottom-1.5 right-1.5 border-b border-r'].map(c =>
  <span key={c} aria-hidden className={`absolute w-3 h-3 border-cyan-300/70 ${c}`} />)}</>

export default function EquipmentGallery({ labCode }: { labCode: string }) {
  const items = BY_LAB[labCode] ?? []
  const tech = TECH.has(labCode)
  const [meta, setMeta] = useState<Record<string, Photo>>({})
  useEffect(() => { load().then(setMeta) }, [])
  if (!items.length) return null
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-start">
      {items.map(it => {
        const p = it.photo ? meta[it.photo] : undefined
        return (
          <figure key={it.label} className={tech ? 'rounded-md overflow-hidden border border-cyan-400/25 bg-ink-950/60'
                                                : 'rounded-xl overflow-hidden border border-white/10 bg-white/5 backdrop-blur-md shadow-lg'}>
            <div style={{ aspectRatio: "4 / 3", ...(tech ? { backgroundImage: 'linear-gradient(rgba(34,211,238,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,.07) 1px,transparent 1px)', backgroundSize: '16px 16px' } : {}) }}
                 className={`relative overflow-hidden grid place-items-center ${tech ? '' : 'bg-gradient-to-br from-slate-800/60 to-slate-900/60'}`}>
              {tech && <Corners />}
              {tech && it.spec && <div className="absolute left-2 bottom-2 flex flex-wrap gap-1">{it.spec.map(t =>
                <span key={t} className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm bg-ink-950/80 border border-cyan-400/30 text-cyan-200">{t}</span>)}</div>}
              {it.image ? <img src={it.image} alt={it.imageAlt ?? it.label} loading="lazy" decoding="async" className="w-full h-full object-cover"
                               onError={e => { if (p) { e.currentTarget.onerror = null; e.currentTarget.src = `/equipment/${p.file}`; e.currentTarget.alt = it.label } }} />
                 : p ? <img src={`/equipment/${p.file}`} alt={it.label} loading="lazy" decoding="async" className="w-full h-full object-cover" />
                 : <span className="text-[11px] text-slate-400 px-4 text-center">Photo of our unit not added yet</span>}
            </div>
            <figcaption className={tech ? 'px-3 py-2 border-t border-cyan-400/20' : 'px-3 py-2'}>
              <div className={tech ? 'font-mono text-[12px] tracking-wide text-cyan-100 uppercase' : 'text-[13px] font-medium text-slate-100'}>{it.label}{it.note && <span className="text-slate-400 font-normal"> · {it.note}</span>}</div>
            </figcaption>
          </figure>)
      })}
    </div>
  )
}
