import { useEffect, useState } from 'react'

// Model / category photos (Wikimedia Commons, free licences) - NOT photos of
// our labs. Fetched by tools/fetch_lab_images.py; attribution shown per card.
interface Photo { kind?: string; file: string; label: string; title: string; source: string; author: string; licence: string }

// What is in each lab (owner's list). `photo` = key in ATTRIBUTION.json; no
// photo = text card until our own photo is taken.
interface Item { label: string; photo?: string; note?: string; image?: string; imageAlt?: string; spec?: string[]; pos?: string }
export const BY_LAB: Record<string, Item[]> = {
  // Generated concept renders (owner's assets); the original photos stay as the fallback.
  LAB_01: [{ label: 'Universal Robots UR5e (mounted inverted)', photo: 'our-ur5e', spec: ['6 axes', '5 kg', '850 mm reach', 'Robotiq 2F-85'], image: '/assets/labs/ur5e-exploded-concept.jpg',
             imageAlt: 'Illustrative exploded concept of the inverted UR5e with its gripper' },
           { label: 'FANUC ER-4iA (R-30iB Mate Plus)', photo: 'our-fanuc', spec: ['6 axes', '4 kg', '550 mm reach', 'R-30iB Mate Plus'], image: '/assets/labs/fanuc-exploded-concept.jpg',
             imageAlt: 'Illustrative exploded concept of the FANUC ER-4iA' },
           { label: 'LAB PCs', photo: 'our-pcs', image: '/assets/labs/lab-pcs.jpg',
             imageAlt: 'Illustration of the robotics lab workstations (not a photograph of the exact setup)' },
           { label: 'Conveyor belt', photo: 'conveyor', image: '/assets/labs/conveyor-with-support-legs.jpg',
             imageAlt: 'Illustration of the conveyor belt on its support legs' }],
  LAB_02: [{ label: 'Siemens SIMATIC S7-1200 PLC', photo: 's7-1200', note: '8 stations', image: '/assets/labs/plc/01_plc_training_rack.webp', imageAlt: 'Illustration of a Siemens PLC training rack (not a photograph of the lab)' },
           { label: 'PC per PLC station', photo: 'workstation', note: '8 stations', image: '/assets/labs/plc/06_engineering_workstation.webp', imageAlt: 'Illustration of a PLC engineering workstation (not a photograph of the lab)' }],
  LAB_03: [{ label: 'CNC milling machine', image: '/assets/labs/production/production_eq_01_cnc_milling.webp', imageAlt: 'CNC milling spindle cutting a metal block (illustration, not a photograph of the lab)' },
           { label: 'CNC machining center', image: '/assets/labs/production/production_eq_02_cnc_machining_center.webp', imageAlt: 'Enclosed CNC machining center with its control panel (illustration, not a photograph of the lab)' },
           { label: 'Bending machine', image: '/assets/labs/production/production_eq_06_sheet_metal.webp', imageAlt: 'Press brake bending machine (illustration, not a photograph of the lab)' },
           { label: 'Drilling machine', photo: 'drill-press', image: '/assets/labs/production/production_eq_04_drilling_milling.webp', imageAlt: 'Pillar drilling machine with a machine vise (illustration, not a photograph of the lab)' },
           { label: 'Measurement and inspection tools', image: '/assets/labs/production/production_eq_05_measurement_inspection.webp', imageAlt: 'Machined parts and measuring tools on a bench (illustration, not a photograph of the lab)' },
           { label: 'Cutting and sheet-metal tools', photo: 'sheet-metal' },
           { label: 'Welding and fabrication', image: '/assets/labs/production/production_eq_07_welding_fabrication.webp', imageAlt: 'Welding machines under a fume extraction arm (illustration, not a photograph of the lab)' },
           { label: 'Tools and workshop materials', image: '/assets/labs/production/production_eq_08_tools_materials.webp', imageAlt: 'Tool wall and workbench with tool chests (illustration, not a photograph of the lab)' }],
  LAB_04: [{ label: 'Tensile testing machine', photo: 'tensile', image: '/assets/labs/materials/materials_eq_03_universal_testing_machine.webp', imageAlt: 'Universal testing machine with a tensile specimen in its grips (illustration, not a photograph of the lab)' },
           { label: 'Bending test machine', photo: 'bending', image: '/assets/labs/materials/materials_bending_test_machine.webp', imageAlt: 'Testing frame with its control panel, as used for bending tests (illustration, not a photograph of the lab)' },
           { label: 'Hardness tester', image: '/assets/labs/materials/materials_eq_04_hardness_tester.webp', imageAlt: 'Hardness tester with an indentation on screen (illustration, not a photograph of the lab)' }],
  LAB_05: [{ label: 'BMW i3 (electric hatchback)', photo: 'bmw-i3' }, { label: 'Gears and transmission', photo: 'gearbox' },
           { label: 'Steering system', photo: 'steering' }],
  LAB_06: [{ label: 'PCB prototyping machine', photo: 'pcb-mill', image: '/assets/labs/pcb/03-pcb-machine-gallery.webp', imageAlt: 'PCB prototyping machine working on a green board, with the layout on a monitor (illustration, not a photograph of the lab)' },
           { label: 'Soldering station', photo: 'soldering', image: '/assets/labs/pcb/04-soldering-station-gallery.webp', imageAlt: 'Soldering station with iron, solder wire and helping hands (illustration, not a photograph of the lab)' }],
  LAB_07: [{ label: 'PCs with Proteus simulation', photo: 'proteus', image: '/assets/labs/microcontrollers/03-proteus-simulation-workstation.webp', imageAlt: 'Workstation with a Proteus circuit simulation and microcontroller code (illustration, not a photograph of the lab)', note: 'installed on all PCs' },
           { label: 'ATmega microcontroller boards', photo: 'atmega', image: '/assets/labs/microcontrollers/04-microcontroller-boards.webp', imageAlt: 'ATmega development board, Arduino Uno and ESP32 on a bench (illustration, not a photograph of the lab)' }, { label: 'ESP32 boards', photo: 'esp32', image: '/assets/labs/microcontrollers/05-sensors-and-embedded-prototyping.webp', imageAlt: 'ESP32, Arduino and ATmega32 boards with sensors and a breadboard (illustration, not a photograph of the lab)' }],
  LAB_08: [{ label: 'Process water tanks', image: '/assets/labs/power/03-water-tank-process-rig.webp', imageAlt: 'Water-tank process rig with pump, valves, piping and level sensors (illustration, not a photograph of the lab)' },
           { label: 'Motor / rotary test rig', image: '/assets/labs/power/04-motor-rotary-test-rig.webp', imageAlt: 'Small electric motor coupled to a gearbox on a test bench (illustration, not a photograph of the lab)' },
           { label: 'HMI panels', image: '/assets/labs/power/05-hmi-panels.webp', imageAlt: 'Control panel with a touch HMI, start/stop buttons and an emergency stop (illustration, not a photograph of the lab)' },
           { label: 'MATLAB (licence USB keys)', photo: 'matlab', image: '/assets/labs/power/06-matlab-usb-simulation.webp', imageAlt: 'Laptop running MATLAB/Simulink beside USB licence keys (illustration, not a photograph of the lab)' }],
  LAB_09: [{ label: 'Laser cutter', photo: 'laser-cutter', image: '/assets/labs/design/design_laser_cutter.webp', imageAlt: 'Laser cutter engraving a wooden panel (illustration, not a photograph of the lab)' },
           { label: 'Wood-cutting equipment', photo: 'woodcut', image: '/assets/labs/design/design_wood_cnc_router.webp', imageAlt: 'CNC router cutting a wooden board (illustration, not a photograph of the lab)' },
           { label: 'Jewelry-making tools', photo: 'jewelry', image: '/assets/labs/design/design_jewelry_tools.webp', imageAlt: 'Jeweller bench with pliers, mandrels and wire (illustration, not a photograph of the lab)' }],
  LAB_11: [{ label: 'Sewing machines', photo: 'sewing', image: '/assets/labs/fashion/fashion_sewing_machine.webp', imageAlt: 'Industrial sewing machine stitching dark fabric (illustration, not a photograph of the lab)' },
           { label: 'Mannequins', photo: 'mannequin', note: 'many', image: '/assets/labs/fashion/fashion_mannequins_dress_forms.webp', imageAlt: 'Dress forms with garments in progress (illustration, not a photograph of the lab)' },
           { label: 'Threads and fabrics', photo: 'thread', image: '/assets/labs/fashion/fashion_threads_fabrics.webp', imageAlt: 'Fabric rolls, swatches and thread cones on a table (illustration, not a photograph of the lab)' }],
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
          <figure key={it.label} className={tech ? 'group rounded-md overflow-hidden border border-cyan-400/25 bg-ink-950/60 transition-[transform,box-shadow,border-color] duration-300 hover:-translate-y-1 hover:border-cyan-300/60 hover:shadow-[0_10px_30px_-10px_rgba(34,211,238,.45)]'
                                                : 'rounded-xl overflow-hidden border border-white/10 bg-white/5 backdrop-blur-md shadow-lg'}>
            <div style={{ aspectRatio: "4 / 3", ...(tech ? { backgroundImage: 'linear-gradient(rgba(34,211,238,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,.07) 1px,transparent 1px)', backgroundSize: '16px 16px' } : {}) }}
                 className={`relative overflow-hidden grid place-items-center ${tech ? '' : 'bg-gradient-to-br from-slate-800/60 to-slate-900/60'}`}>
              {tech && <Corners />}
              {tech && it.spec && <div className="absolute left-2 bottom-2 flex flex-wrap gap-1">{it.spec.map(t =>
                <span key={t} className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm bg-ink-950/80 border border-cyan-400/30 text-cyan-200">{t}</span>)}</div>}
              {it.image ? <img src={it.image} alt={it.imageAlt ?? it.label} loading="lazy" decoding="async" className={`w-full h-full object-cover ${tech ? 'transition-transform duration-500 group-hover:scale-[1.04]' : ''}`}
                               onError={e => { const el = e.currentTarget; if (p && !el.dataset.fb) { el.dataset.fb = '1'; el.src = `/equipment/${p.file}`; el.alt = it.label } else el.style.display = 'none' }} />
                 : p ? <img src={`/equipment/${p.file}`} alt={it.label} loading="lazy" decoding="async" className={`w-full h-full object-cover ${tech ? 'transition-transform duration-500 group-hover:scale-[1.04]' : ''}`} style={it.pos ? { objectPosition: it.pos } : undefined} onError={e => { e.currentTarget.style.display = 'none' }} />
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
