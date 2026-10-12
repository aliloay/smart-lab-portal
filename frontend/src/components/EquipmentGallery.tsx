import { useEffect, useState } from 'react'

// Model / category photos (Wikimedia Commons, free licences) - NOT photos of
// our labs. Fetched by tools/fetch_lab_images.py; attribution shown per card.
interface Photo { file: string; label: string; title: string; source: string; author: string; licence: string }

// What is in each lab (owner's list). `photo` = key in ATTRIBUTION.json; no
// photo = text card until our own photo is taken.
interface Item { label: string; photo?: string; note?: string }
const BY_LAB: Record<string, Item[]> = {
  LAB_01: [{ label: 'Universal Robots UR5e', photo: 'ur5e' }, { label: 'FANUC ER-4iA (R-30iB Mate Plus)' },
           { label: 'Conveyor belt', photo: 'conveyor' }, { label: 'Lab PCs', photo: 'workstation' }],
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

export default function EquipmentGallery({ labCode }: { labCode: string }) {
  const items = BY_LAB[labCode] ?? []
  const [meta, setMeta] = useState<Record<string, Photo>>({})
  useEffect(() => { load().then(setMeta) }, [])
  if (!items.length) return null
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {items.map(it => {
        const p = it.photo ? meta[it.photo] : undefined
        return (
          <figure key={it.label} className="rounded-xl overflow-hidden border border-white/10 bg-white/5 backdrop-blur-md shadow-lg">
            <div className="aspect-[4/3] bg-gradient-to-br from-slate-800/60 to-slate-900/60 grid place-items-center">
              {p ? <img src={`/equipment/${p.file}`} alt={it.label} loading="lazy" decoding="async" className="w-full h-full object-cover" />
                 : <span className="text-[11px] text-slate-400 px-4 text-center">Photo of our unit not added yet</span>}
            </div>
            <figcaption className="px-3 py-2">
              <div className="text-[13px] font-medium text-slate-100">{it.label}{it.note && <span className="text-slate-400 font-normal"> · {it.note}</span>}</div>
              {p && <div className="text-[10.5px] text-slate-400 truncate" title={`${p.title} - ${p.author}`}>
                Model photo, not our lab · {p.author} ·{' '}
                <a href={p.source} target="_blank" rel="noopener noreferrer" className="underline">{p.licence}</a>
              </div>}
            </figcaption>
          </figure>)
      })}
    </div>
  )
}
