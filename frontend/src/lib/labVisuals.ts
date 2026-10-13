/**
 * Smart Lab visual manifest - the ONE place that maps equipment and labs to images.
 *
 * Replacing a placeholder with a real photograph = put the file under
 * frontend/public/lab/ (see public/lab/README.md) and fill in `src` below.
 * No component changes are needed.
 *
 * Every image says what it is (`kind`) so an illustration is never shown as a photograph:
 *   photo         untouched documentary photograph (the reference / ground truth)
 *   curated       the same photo cropped / straightened / exposure-corrected only
 *   isolated      the real equipment with the background removed
 *   illustration  exploded view, annotated diagram - NOT a photograph
 *   dimensional   depth / layered visual made from a real photo - NOT a plain photograph
 * A derivative names its source in `from` (the original's file name), so it stays traceable.
 */

export type ImageKind = 'photo' | 'curated' | 'isolated' | 'illustration' | 'dimensional'
export type ImageRole = 'hero' | 'angle' | 'detail' | 'isolated' | 'illustration' | 'dimensional' | 'reference'

export interface LabImage {
  src: string                 // path under public/, e.g. /lab/equipment/ur5e/hero.webp
  thumb?: string              // small version for grids (falls back to src)
  alt: string
  role: ImageRole
  kind: ImageKind
  width?: number              // intrinsic size if known: reserves space, avoids layout shift
  height?: number
  from?: string               // derivative: the original photo it was made from
  credit?: string
}

export interface EquipmentVisual {
  id: string
  title: string
  model?: string              // only when verified
  labCode?: string            // only when the project data places it there
  description: string
  images: LabImage[]          // any subset of roles; empty = "photo pending"
  route?: { to: string; label: string; staffOnly?: boolean }   // existing portal routes only
  docs?: { href: string; label: string }
}

export interface LabVisual { code: string; hero?: LabImage; intro?: string }

const OWN = 'Ali Loay (own photo)'

export const EQUIPMENT: EquipmentVisual[] = [
  {
    id: 'ur5e', title: 'Universal Robots UR5e', model: 'UR5e', labCode: 'LAB_01',
    description: 'Collaborative 6-axis arm, mounted on its frame. The portal shows its joints live, read-only, through RTDE.',
    images: [{ src: '/equipment/our-ur5e.jpg', alt: 'The lab\'s UR5e robot arm on its frame', role: 'hero', kind: 'photo', credit: OWN }],
    route: { to: '/robots', label: 'Digital twin' },
  },
  {
    id: 'fanuc', title: 'FANUC ER-4iA', model: 'ER-4iA (R-30iB Mate Plus)', labCode: 'LAB_01',
    description: 'Compact industrial arm. Read-only telemetry is planned once its controller interface is confirmed.',
    images: [{ src: '/equipment/our-fanuc.jpg', alt: 'The lab\'s FANUC ER-4iA robot', role: 'hero', kind: 'photo', credit: OWN }],
    route: { to: '/robots', label: 'Robots' },
  },
  {
    id: 'robotics-pcs', title: 'Robotics lab PCs', labCode: 'LAB_01',
    description: 'Workstations for robot programming; their use is seen by the security camera\'s equipment boxes.',
    images: [{ src: '/equipment/our-pcs.jpg', alt: 'PC workstations in the robotics lab', role: 'hero', kind: 'photo', credit: OWN }],
    route: { to: '/labs', label: 'Laboratories' },
  },
  {
    id: 's7-1200', title: 'Siemens PLC stations', model: 'SIMATIC S7-1200', labCode: 'LAB_02',
    description: 'Eight PLC training stations, each with its own PC.',
    images: [],
    route: { to: '/labs', label: 'Laboratories' },
  },
  {
    id: 'iot', title: 'Smart Lab sensors and controllers',
    description: 'ESP32 door controller, environment node, smart bins and the security camera that feed this portal.',
    images: [],
    route: { to: '/command', label: 'IoT dashboard', staffOnly: true },
  },
  {
    id: 'conveyor', title: 'Conveyor belt', labCode: 'LAB_01',
    description: 'Part of the robotics cell.',
    images: [],
  },
]

/** Lab hero photographs, by lab code (existing codes only). Empty until photographed. */
export const LABS: Record<string, LabVisual> = {
  LAB_01: { code: 'LAB_01', hero: { src: '/equipment/our-ur5e.jpg', alt: 'Robotics lab: the UR5e on its frame', role: 'hero', kind: 'photo', credit: OWN } },
}

/** The landing page's hero picture. Replace with a wide photo of the lab when available. */
export const SITE_HERO: LabImage | null =
  { src: '/equipment/our-pcs.jpg', alt: 'Inside the Smart Lab robotics laboratory', role: 'hero', kind: 'photo', credit: OWN }

export const ROLE_ORDER: ImageRole[] = ['hero', 'angle', 'detail', 'isolated', 'illustration', 'dimensional', 'reference']
export const ROLE_LABEL: Record<ImageRole, string> = {
  hero: 'Main view', angle: 'Another angle', detail: 'Detail', isolated: 'Cut-out',
  illustration: 'Illustration', dimensional: 'Depth view', reference: 'Original',
}
export const KIND_LABEL: Record<ImageKind, string> = {
  photo: 'Photograph', curated: 'Photograph (cropped / corrected)', isolated: 'Photograph, background removed',
  illustration: 'Illustration - not a photograph', dimensional: 'Depth visual made from a photograph',
}

export const heroOf = (e: EquipmentVisual) => e.images.find(i => i.role === 'hero') ?? e.images[0]
export const sortedImages = (e: EquipmentVisual) =>
  [...e.images].sort((a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role))
