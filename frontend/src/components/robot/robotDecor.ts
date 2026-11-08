/**
 * Printed surfaces of the lab's FANUC Educational Cell and ER-4iA arm, drawn on canvases at run time (no image
 * files to download): the yellow FANUC side panels, the FANUC sticker on the front glass, the "FANUC Robot ER-4iA"
 * lettering on the arm, the controller front, the teach pendant, the slotted table and the parts plate.
 * Layout and colours follow the owner's photos of 2026-10-19 - APPROXIMATE, for recognition only.
 * Each texture is made once and shared by every view (Lab Equipment twin and Welcome page).
 */
import * as THREE from 'three'

const YELLOW = '#ffd100'
const RED = '#c0232b'
const WORDMARK = '900 1px "Arial Black", "Helvetica Neue", Arial, sans-serif'

export type DecorKey = 'side-panel' | 'sticker' | 'arm-label' | 'arm-warning' | 'controller' | 'pendant'
  | 'slotted-table' | 'parts-plate'

function font(px: number, base = WORDMARK) { return base.replace('1px', `${Math.round(px)}px`) }

function canvas(w: number, h: number, draw: (g: CanvasRenderingContext2D, w: number, h: number) => void) {
  const c = document.createElement('canvas')
  c.width = w; c.height = h
  draw(c.getContext('2d')!, w, h)
  return c
}

/** The yellow side panel of the lower cabinet: lettering top, white wave lines across the lower half. */
function sidePanel(g: CanvasRenderingContext2D, w: number, h: number) {
  g.fillStyle = YELLOW; g.fillRect(0, 0, w, h)
  g.fillStyle = RED; g.fillRect(64, 66, 7, 92)
  g.fillStyle = '#3a3a3a'; g.font = font(30, '400 1px "Segoe UI", Arial, sans-serif'); g.fillText('Learn online:', 88, 100)
  g.fillStyle = '#262626'; g.font = font(33, '700 1px "Segoe UI", Arial, sans-serif'); g.fillText('fanuc.eu/educational-package', 88, 146)
  g.fillStyle = RED; g.font = font(150); g.textAlign = 'right'; g.fillText('FANUC', w - 60, 345)
  g.textAlign = 'left'
  g.strokeStyle = 'rgba(255,255,255,0.9)'; g.lineWidth = 2.2
  for (let i = 0; i < 26; i++) {
    g.beginPath()
    for (let x = 0; x <= w; x += 8) {
      const u = x / w
      const y = h * 0.72 + Math.sin(u * Math.PI * 2.1 + 0.9 + i * 0.045) * h * (0.10 + 0.004 * i)
        - u * h * 0.06 + (i - 13) * 1.6 * Math.cos(u * Math.PI * 1.3)
      if (x === 0) g.moveTo(x, y); else g.lineTo(x, y)
    }
    g.stroke()
  }
}

function sticker(g: CanvasRenderingContext2D, w: number, h: number) {
  g.fillStyle = YELLOW; g.fillRect(0, 0, w, h)
  g.fillStyle = RED; g.font = font(h * 0.46); g.textAlign = 'center'; g.textBaseline = 'middle'
  g.fillText('FANUC', w / 2, h * 0.53)
}

/** "FANUC Robot ER-4iA" as printed along the side of the arm (transparent around the letters). */
function armLabel(g: CanvasRenderingContext2D, w: number, h: number) {
  const base = h * 0.72
  const parts: [string, string, string][] = [
    ['FANUC', RED, font(h * 0.62)], [' Robot ', '#202020', font(h * 0.34, 'italic 600 1px "Segoe UI", Arial, sans-serif')],
    ['ER-4iA', '#151515', font(h * 0.58, '800 1px "Segoe UI", Arial, sans-serif')]]
  let total = 0
  for (const [t, , f] of parts) { g.font = f; total += g.measureText(t).width }
  let x = (w - total) / 2
  for (const [t, c, f] of parts) { g.font = f; g.fillStyle = c; g.fillText(t, x, base); x += g.measureText(t).width }
}

function armWarning(g: CanvasRenderingContext2D, w: number, h: number) {
  g.fillStyle = '#f4f4f2'; g.fillRect(0, 0, w, h)
  g.fillStyle = '#ffd100'
  g.beginPath(); g.moveTo(w * 0.5, h * 0.05); g.lineTo(w * 0.78, h * 0.2); g.lineTo(w * 0.22, h * 0.2); g.closePath(); g.fill()
  g.fillStyle = '#9aa0a6'
  for (let i = 0; i < 16; i++) g.fillRect(w * 0.12, h * (0.27 + i * 0.042), w * (0.45 + ((i * 37) % 30) / 100), h * 0.012)
  g.strokeStyle = '#555'; g.lineWidth = 3; g.strokeRect(w * 0.3, h * 0.62, w * 0.4, h * 0.2)
}

/** R-30iB Mate Plus front: fan grille, vents, the operator panel with the emergency stop, the type label. */
function controller(g: CanvasRenderingContext2D, w: number, h: number) {
  g.fillStyle = '#ece6d3'; g.fillRect(0, 0, w, h)
  g.fillStyle = YELLOW; g.fillRect(16, 14, 300, 30)
  g.fillStyle = '#1b1b1b'; g.font = font(19, '700 1px "Segoe UI", Arial, sans-serif'); g.fillText('FANUC  SYSTEM R-30iB Mate Plus', 24, 36)
  g.fillStyle = '#2c2c2c'
  for (let i = 0; i < 6; i++) { g.fillRect(40, 70 + i * 16, 220, 7); g.fillRect(40, 470 + i * 16, 220, 7) }
  const cx = 150, cy = 330, r = 115
  g.fillStyle = '#c9c4b3'; g.beginPath(); g.arc(cx, cy, r + 12, 0, Math.PI * 2); g.fill()
  g.fillStyle = '#3a3a3a'; g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.fill()
  g.strokeStyle = '#9b9b9b'; g.lineWidth = 3
  for (let k = 1; k <= 5; k++) { g.beginPath(); g.arc(cx, cy, (r * k) / 5.4, 0, Math.PI * 2); g.stroke() }
  for (let a = 0; a < 12; a++) { g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(a * Math.PI / 6) * r, cy + Math.sin(a * Math.PI / 6) * r); g.stroke() }
  g.fillStyle = '#151515'; g.fillRect(330, 70, 440, 170)
  g.fillStyle = '#d6d6d6'; g.beginPath(); g.arc(400, 155, 28, 0, Math.PI * 2); g.fill()
  g.fillStyle = '#22c55e'; g.fillRect(470, 130, 34, 46)
  g.fillStyle = '#4b4b4b'; g.beginPath(); g.arc(700, 155, 40, 0, Math.PI * 2); g.fill()
  g.fillStyle = YELLOW; g.fillRect(560, 380, 210, 120)
  g.fillStyle = '#1b1b1b'; g.font = font(40, '800 1px "Segoe UI", Arial, sans-serif'); g.fillText('ER-4iA', 590, 432)
  g.fillStyle = '#3d3d3d'; for (let i = 0; i < 3; i++) g.fillRect(578, 450 + i * 14, 170, 5)
  g.fillStyle = '#f5f5f5'; g.fillRect(560, 515, 210, 60)
  g.fillStyle = '#8a8a8a'; for (let i = 0; i < 4; i++) g.fillRect(572, 525 + i * 12, 180, 4)
}

/** Teach pendant front: screen, key field, emergency stop. */
function pendant(g: CanvasRenderingContext2D, w: number, h: number) {
  g.fillStyle = '#16181c'; g.fillRect(0, 0, w, h)
  g.fillStyle = '#2b3542'; g.fillRect(w * 0.12, h * 0.07, w * 0.62, h * 0.3)
  g.fillStyle = '#3f5468'; g.fillRect(w * 0.15, h * 0.1, w * 0.56, h * 0.24)
  for (let r = 0; r < 9; r++) for (let c = 0; c < 6; c++) {
    g.fillStyle = (r + c) % 7 === 0 ? '#4f86c6' : '#d9dde3'
    g.fillRect(w * (0.1 + c * 0.135), h * (0.43 + r * 0.058), w * 0.105, h * 0.04)
  }
  g.fillStyle = '#d61f26'; g.beginPath(); g.arc(w * 0.86, h * 0.1, w * 0.07, 0, Math.PI * 2); g.fill()
}

/** Aluminium T-slot table: slots run front to back. */
function slottedTable(g: CanvasRenderingContext2D, w: number, h: number) {
  g.fillStyle = '#bcc2ca'; g.fillRect(0, 0, w, h)
  for (let x = 10; x < w; x += 43) {
    g.fillStyle = '#7d848d'; g.fillRect(x, 0, 9, h)
    g.fillStyle = '#d7dce2'; g.fillRect(x + 9, 0, 3, h)
  }
}

/** Black perforated plate of the pick-and-place exercise (4 x 3 holes). */
function partsPlate(g: CanvasRenderingContext2D, w: number, h: number) {
  g.fillStyle = '#1a1c20'; g.fillRect(0, 0, w, h)
  for (let i = 0; i < 4; i++) for (let j = 0; j < 3; j++) {
    const x = w * (0.125 + i * 0.25), y = h * (0.18 + j * 0.32)
    g.fillStyle = '#050607'; g.beginPath(); g.arc(x, y, w * 0.05, 0, Math.PI * 2); g.fill()
    g.strokeStyle = '#33363c'; g.lineWidth = 3; g.stroke()
  }
}

const RECIPES: Record<DecorKey, [number, number, (g: CanvasRenderingContext2D, w: number, h: number) => void]> = {
  'side-panel': [1024, 930, sidePanel],
  sticker: [512, 256, sticker],
  'arm-label': [1024, 200, armLabel],
  'arm-warning': [256, 512, armWarning],
  controller: [800, 600, controller],
  pendant: [400, 560, pendant],
  'slotted-table': [1024, 512, slottedTable],
  'parts-plate': [512, 358, partsPlate],
}

const cache = new Map<DecorKey, THREE.Texture>()

export function decorTexture(key: DecorKey): THREE.Texture {
  const hit = cache.get(key)
  if (hit) return hit
  const [w, h, draw] = RECIPES[key]
  const tex = new THREE.CanvasTexture(canvas(w, h, draw))
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 4
  cache.set(key, tex)
  return tex
}

/** Rotation that turns a plane (drawn in x-y, facing +z) to face `facing` with its top up (+z), or lying face-up. */
export type Facing = '+x' | '-x' | '+y' | '-y' | '+z'
const BASES: Record<Facing, [number, number, number][]> = {
  '+x': [[0, 1, 0], [0, 0, 1], [1, 0, 0]], '-x': [[0, -1, 0], [0, 0, 1], [-1, 0, 0]],
  '+y': [[-1, 0, 0], [0, 0, 1], [0, 1, 0]], '-y': [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
  '+z': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
}
export function facingQuaternion(f: Facing): THREE.Quaternion {
  const [x, y, z] = BASES[f].map(v => new THREE.Vector3(...v))
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z))
}
