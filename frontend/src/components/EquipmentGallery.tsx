import { useEffect, useState } from 'react'

// Model / category photos (Wikimedia Commons, free licences) - NOT photos of
// our labs. Fetched by tools/fetch_lab_images.py; attribution shown per card.
interface Photo { file: string; label: string; title: string; source: string; author: string; licence: string }

const BY_LAB: Record<string, string[]> = {
  LAB_01: ['conveyor', 'workstation'],
  LAB_02: ['s7-1200', 'workstation'],
  LAB_03: ['drill-press', 'sheet-metal'],
  LAB_04: ['tensile', 'bending'],
  LAB_05: ['bmw-i3', 'gearbox', 'steering'],
  LAB_06: ['pcb-mill', 'soldering'],
  LAB_07: ['atmega', 'esp32', 'soldering'],
  LAB_09: ['laser-cutter', 'woodcut', 'jewelry'],
  LAB_11: ['sewing', 'mannequin', 'thread'],
}

let cache: Promise<Record<string, Photo>> | null = null
const load = () => (cache ??= fetch('/equipment/ATTRIBUTION.json').then(r => r.ok ? r.json() : {}).catch(() => ({})) as Promise<Record<string, Photo>>)

export default function EquipmentGallery({ labCode }: { labCode: string }) {
  const [photos, setPhotos] = useState<Photo[]>([])
  useEffect(() => {
    load().then(m => setPhotos((BY_LAB[labCode] ?? []).map(k => m[k]).filter(Boolean)))
  }, [labCode])
  if (!photos.length) return null
  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {photos.map(p => (
          <figure key={p.file} className="rounded-xl overflow-hidden border border-white/10 bg-white/5 backdrop-blur-md shadow-lg">
            <div className="aspect-[4/3] bg-slate-900/40">
              <img src={`/equipment/${p.file}`} alt={p.label} loading="lazy" decoding="async"
                className="w-full h-full object-cover" />
            </div>
            <figcaption className="px-3 py-2">
              <div className="text-[13px] font-medium text-slate-100">{p.label}</div>
              <div className="text-[10.5px] text-slate-400 truncate" title={`${p.title} - ${p.author}`}>
                Product photo, not our lab · {p.author} ·{' '}
                <a href={p.source} target="_blank" rel="noopener noreferrer" className="underline">{p.licence}</a>
              </div>
            </figcaption>
          </figure>))}
      </div>
    </div>
  )
}
