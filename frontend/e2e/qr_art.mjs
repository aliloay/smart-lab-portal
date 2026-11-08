// Illustrated asset markers (2026-10-27, owner: "a partially opened door with the QR on the door, a clear 3D 6-DOF robot
// with the QR in the middle, a camera whose LENS is the QR - good-looking art for the thesis"). Each marker is a vector
// drawing of the object with a REAL, flat, unmodified QR (ECC H, matrix from the portal's own encoder) on a white panel
// with its quiet zone - the art never touches the modules, so it scans like a plain code.
//   node e2e/qr_art.mjs <dir with matrices.json>  ->  <dir>/png/<slug>.png (2400 x 3000) and <dir>/svg/<slug>.svg
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import sharp from 'sharp'

const dir = process.argv[2]
const M = JSON.parse(readFileSync(`${dir}/matrices.json`, 'utf8'))
mkdirSync(`${dir}/png`, { recursive: true }); mkdirSync(`${dir}/svg`, { recursive: true })
const INK = '#0b1324'

/** The QR: modules only (square, ink colour), `size` = the module area; the caller provides the white quiet zone. */
function qr(code, cx, cy, size, ink = INK) {
  const m = M[code], n = m.length, k = size / n, x0 = cx - size / 2, y0 = cy - size / 2
  let d = ''
  m.forEach((row, y) => { for (let x = 0; x < n; x++) if (row[x] === '1') d += `M${(x0 + x * k).toFixed(2)} ${(y0 + y * k).toFixed(2)}h${k.toFixed(2)}v${k.toFixed(2)}h-${k.toFixed(2)}z` })
  return `<path d="${d}" fill="${ink}" shape-rendering="crispEdges"/>`
}
/** White panel with a quiet zone of 4+ modules around a QR of `size`. */
function qrPanel(code, cx, cy, size, { r = 18, stroke = '#cbd5e1', ink } = {}) {
  const n = M[code].length, q = (size / n) * 4.5, w = size + 2 * q
  return `<rect x="${cx - w / 2}" y="${cy - w / 2}" width="${w}" height="${w}" rx="${r}" fill="#fff" stroke="${stroke}" stroke-width="3"/>` + qr(code, cx, cy, size, ink)
}
const shadow = (cx, cy, rx, ry) => `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="url(#shadow)"/>`
const DEFS = `
  <radialGradient id="shadow"><stop offset="0" stop-color="#0f172a" stop-opacity=".28"/><stop offset="1" stop-color="#0f172a" stop-opacity="0"/></radialGradient>
  <linearGradient id="metal" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f8fafc"/><stop offset=".5" stop-color="#cbd5e1"/><stop offset="1" stop-color="#64748b"/></linearGradient>
  <linearGradient id="metalV" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#94a3b8"/><stop offset=".35" stop-color="#f1f5f9"/><stop offset="1" stop-color="#64748b"/></linearGradient>
  <linearGradient id="darkV" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1e293b"/><stop offset=".4" stop-color="#475569"/><stop offset="1" stop-color="#0f172a"/></linearGradient>
  <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e0f2fe"/><stop offset="1" stop-color="#7dd3fc"/></linearGradient>`
const grad = (id, a, b, c, vertical = false) =>
  `<linearGradient id="${id}" x1="0" y1="0" x2="${vertical ? 0 : 1}" y2="${vertical ? 1 : 0.35}"><stop offset="0" stop-color="${a}"/><stop offset=".45" stop-color="${b}"/><stop offset="1" stop-color="${c}"/></linearGradient>`

// ------------------------------------------------------------------ scenes (art area 1200 x 1200)
function door(code, acc) {
  return `<defs>${grad('leaf', '#5eead4', acc, '#134e4a')}${grad('frame', '#475569', '#334155', '#1e293b')}
    <linearGradient id="inside" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#0f172a"/><stop offset="1" stop-color="#1e3a5f"/></linearGradient>
    <linearGradient id="light" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fde68a" stop-opacity=".9"/><stop offset="1" stop-color="#fde68a" stop-opacity="0"/></linearGradient></defs>
  ${shadow(600, 1135, 420, 40)}
  <rect x="150" y="1110" width="900" height="16" rx="8" fill="#e2e8f0"/>
  <rect x="290" y="110" width="620" height="1010" rx="10" fill="url(#frame)"/>
  <rect x="330" y="150" width="540" height="965" fill="url(#inside)"/>
  <polygon points="770,1115 870,1115 1010,1180 820,1180" fill="url(#light)"/>
  <rect x="770" y="150" width="100" height="965" fill="#fde68a" opacity=".55"/>
  <polygon points="330,150 770,190 770,1080 330,1115" fill="url(#leaf)" stroke="#0f3d3a" stroke-width="4"/>
  <polygon points="770,190 800,182 800,1088 770,1080" fill="#0f3d3a"/>
  <rect x="372" y="760" width="350" height="290" rx="10" fill="none" stroke="#0f3d3a" stroke-opacity=".35" stroke-width="6"/>
  ${qrPanel(code, 545, 450, 300)}
  <rect x="712" y="600" width="26" height="90" rx="12" fill="url(#metal)" stroke="#475569" stroke-width="3"/>
  <rect x="940" y="520" width="110" height="200" rx="16" fill="#1e293b"/>
  <rect x="958" y="545" width="74" height="54" rx="6" fill="#38bdf8"/>
  <circle cx="972" cy="640" r="11" fill="#22c55e"/><circle cx="1018" cy="640" r="11" fill="#ef4444"/>
  <path d="M968 685 q27 -22 54 0" stroke="#94a3b8" stroke-width="6" fill="none"/>`
}

function robot(code, acc, body, joint) {
  // a 6-DOF arm on a cabinet; the QR is the cabinet's front panel
  return `<defs>${grad('cabF', '#f8fafc', '#e2e8f0', '#cbd5e1', true)}${grad('link', body[0], body[1], body[2])}${grad('jnt', joint[0], joint[1], joint[2])}</defs>
  ${shadow(620, 1150, 420, 42)}
  <polygon points="330,690 870,690 950,620 410,620" fill="#f1f5f9" stroke="#94a3b8" stroke-width="4"/>
  <polygon points="870,690 950,620 950,1070 870,1140" fill="#94a3b8" stroke="#64748b" stroke-width="4"/>
  <rect x="330" y="690" width="540" height="450" fill="url(#cabF)" stroke="#94a3b8" stroke-width="4"/>
  <rect x="330" y="690" width="540" height="18" fill="${acc}"/>
  ${qrPanel(code, 600, 920, 300, { stroke: 'none', r: 6 })}
  <ellipse cx="640" cy="652" rx="120" ry="34" fill="#334155"/>
  <rect x="545" y="540" width="190" height="112" fill="url(#link)"/>
  <ellipse cx="640" cy="652" rx="95" ry="26" fill="url(#link)"/>
  <ellipse cx="640" cy="540" rx="95" ry="26" fill="${body[0]}"/>
  <circle cx="640" cy="470" r="86" fill="url(#jnt)"/><circle cx="640" cy="470" r="44" fill="${joint[2]}" opacity=".55"/>
  <polygon points="590,430 690,505 520,250 420,180" fill="url(#link)" stroke="${body[2]}" stroke-width="3"/>
  <circle cx="470" cy="215" r="74" fill="url(#jnt)"/><circle cx="470" cy="215" r="36" fill="${joint[2]}" opacity=".55"/>
  <polygon points="470,170 470,260 830,230 830,160" fill="url(#link)" stroke="${body[2]}" stroke-width="3"/>
  <circle cx="840" cy="195" r="56" fill="url(#jnt)"/><circle cx="840" cy="195" r="24" fill="${joint[2]}" opacity=".55"/>
  <rect x="870" y="160" width="70" height="80" rx="16" fill="url(#link)" stroke="${body[2]}" stroke-width="3"/>
  <circle cx="930" cy="290" r="48" fill="url(#jnt)"/>
  <rect x="900" y="330" width="60" height="40" rx="6" fill="#334155"/>
  <rect x="884" y="370" width="92" height="26" rx="6" fill="#1e293b"/>
  <rect x="888" y="396" width="20" height="62" rx="5" fill="#475569"/><rect x="952" y="396" width="20" height="62" rx="5" fill="#475569"/>`
}

function lens(code, cx, cy, r) {
  // the QR sits inside the lens: the white disc is the quiet zone, rings + glints around it
  const n = M[code].length, size = Math.floor((r - 6) * Math.SQRT2 * 0.86)
  return `<circle cx="${cx}" cy="${cy}" r="${r + 46}" fill="#0f172a"/>
  <circle cx="${cx}" cy="${cy}" r="${r + 32}" fill="url(#metal)"/>
  <circle cx="${cx}" cy="${cy}" r="${r + 12}" fill="#1e293b"/>
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#fff"/>
  ${qr(code, cx, cy, size)}
  <path d="M${cx - r * 0.82} ${cy - r * 0.62} A${r + 22} ${r + 22} 0 0 1 ${cx - r * 0.2} ${cy - r - 18}" stroke="#fff" stroke-opacity=".75" stroke-width="10" fill="none" stroke-linecap="round"/>`
  + (n ? '' : '')
}

function camera(code, acc) {
  return `<defs>${grad('body', '#a78bfa', acc, '#3b0764', true)}</defs>
  ${shadow(600, 1090, 440, 40)}
  <rect x="300" y="250" width="240" height="110" rx="20" fill="#3b0764"/>
  <rect x="800" y="285" width="130" height="50" rx="14" fill="#1e1b4b"/>
  <rect x="150" y="320" width="900" height="720" rx="70" fill="url(#body)"/>
  <rect x="150" y="430" width="900" height="70" fill="#000" opacity=".12"/>
  <rect x="860" y="380" width="130" height="80" rx="12" fill="url(#glass)" stroke="#e0e7ff" stroke-width="4"/>
  <circle cx="230" cy="400" r="18" fill="#f43f5e"/>
  ${lens(code, 600, 700, 262)}`
}

function cctv(code, acc) {
  return `<defs>${grad('house', '#f8fafc', '#e2e8f0', '#94a3b8', true)}</defs>
  ${shadow(600, 1150, 430, 38)}
  <rect x="510" y="70" width="180" height="70" rx="14" fill="#334155"/>
  <rect x="570" y="135" width="60" height="150" fill="url(#darkV)"/>
  <path d="M170 330 Q600 220 1030 330 L1030 370 L170 370 Z" fill="${acc}"/>
  <rect x="190" y="360" width="820" height="740" rx="90" fill="url(#house)" stroke="#94a3b8" stroke-width="4"/>
  ${Array.from({ length: 12 }, (_, i) => { const a = (i / 12) * Math.PI * 2; return `<circle cx="${600 + Math.cos(a) * 345}" cy="${745 + Math.sin(a) * 345}" r="13" fill="#7f1d1d" opacity=".75"/>` }).join('')}
  ${lens(code, 600, 745, 252)}
  <circle cx="930" cy="440" r="16" fill="${acc}"/><circle cx="930" cy="440" r="28" fill="${acc}" opacity=".25"/>`
}

function laptop(code, acc) {
  return `<defs>${grad('deck', '#e2e8f0', '#cbd5e1', '#94a3b8', true)}</defs>
  ${shadow(600, 1010, 520, 40)}
  <rect x="220" y="150" width="760" height="680" rx="28" fill="#0f172a"/>
  <rect x="252" y="182" width="696" height="616" rx="8" fill="#fff"/>
  <rect x="252" y="182" width="696" height="34" fill="${acc}"/>
  <circle cx="600" cy="166" r="6" fill="#334155"/>
  ${qr(code, 600, 512, 470)}
  <polygon points="150,850 1050,850 1130,975 70,975" fill="url(#deck)" stroke="#64748b" stroke-width="4"/>
  <rect x="200" y="830" width="800" height="24" rx="8" fill="#475569"/>
  ${Array.from({ length: 4 }, (_, r) => Array.from({ length: 14 }, (_, c) => { const y = 868 + r * 22, sh = (y - 850) / 125 * 80, x0 = 150 - sh + 40, w = (900 + 2 * sh - 80) / 14; return `<rect x="${(x0 + c * w + 3).toFixed(1)}" y="${y}" width="${(w - 6).toFixed(1)}" height="15" rx="3" fill="#94a3b8"/>` }).join('')).join('')}
  <rect x="510" y="955" width="180" height="12" rx="5" fill="#64748b"/>`
}

function monitor(code, acc) {
  return `<defs>${grad('stand', '#cbd5e1', '#94a3b8', '#475569')}</defs>
  ${shadow(600, 1120, 470, 40)}
  <rect x="190" y="110" width="820" height="640" rx="26" fill="#0f172a"/>
  <rect x="222" y="142" width="756" height="576" rx="8" fill="#fff"/>
  <rect x="222" y="142" width="756" height="30" fill="${acc}"/>
  ${qr(code, 600, 455, 450)}
  <rect x="560" y="750" width="80" height="170" fill="url(#stand)"/>
  <ellipse cx="600" cy="925" rx="200" ry="34" fill="url(#stand)"/>
  <rect x="210" y="980" width="780" height="110" rx="18" fill="#e2e8f0" stroke="#94a3b8" stroke-width="4"/>
  ${Array.from({ length: 3 }, (_, r) => Array.from({ length: 15 }, (_, c) => `<rect x="${236 + c * 49.5}" y="${996 + r * 30}" width="42" height="22" rx="4" fill="#94a3b8"/>`).join('')).join('')}`
}

function server(code, acc) {
  return `<defs>${grad('front', '#6366f1', acc, '#1e1b4b', true)}</defs>
  ${shadow(620, 1150, 380, 38)}
  <polygon points="330,130 850,130 930,80 410,80" fill="#818cf8"/>
  <polygon points="850,130 930,80 930,1080 850,1130" fill="#1e1b4b"/>
  <rect x="330" y="130" width="520" height="1000" rx="10" fill="url(#front)"/>
  ${qrPanel(code, 590, 420, 330, { stroke: 'none' })}
  <g fill="none" stroke="#c7d2fe" stroke-width="8" stroke-linecap="round">
    <path d="M520 760 v-30 h30"/><path d="M660 730 h30 v30"/><path d="M690 860 v30 h-30"/><path d="M550 890 h-30 v-30"/></g>
  <circle cx="605" cy="800" r="34" fill="none" stroke="#e0e7ff" stroke-width="7"/>
  <path d="M560 875 q45 -40 90 0" stroke="#e0e7ff" stroke-width="7" fill="none"/>
  ${Array.from({ length: 3 }, (_, i) => `<rect x="370" y="${940 + i * 52}" width="440" height="36" rx="6" fill="#1e1b4b" opacity=".55"/><circle cx="785" cy="${958 + i * 52}" r="8" fill="#22d3ee"/>`).join('')}`
}

function partsBin(code, acc) {
  return `<defs>${grad('bin', '#fdba74', acc, '#7c2d12', true)}</defs>
  ${shadow(600, 1135, 460, 38)}
  <rect x="190" y="1010" width="820" height="100" rx="18" fill="url(#metalV)" stroke="#64748b" stroke-width="4"/>
  <rect x="770" y="1030" width="190" height="60" rx="8" fill="#052e16"/>
  <text x="865" y="1072" font-family="Consolas, monospace" font-size="34" font-weight="700" fill="#4ade80" text-anchor="middle">128 pcs</text>
  ${Array.from({ length: 9 }, (_, i) => { const x = 330 + i * 64; return `<g transform="rotate(${-20 + i * 5} ${x} 330)"><line x1="${x}" y1="250" x2="${x}" y2="420" stroke="#94a3b8" stroke-width="5"/><rect x="${x - 16}" y="305" width="32" height="60" rx="14" fill="#d6b48c"/><rect x="${x - 16}" y="318" width="32" height="7" fill="#a16207"/><rect x="${x - 16}" y="333" width="32" height="7" fill="#111"/><rect x="${x - 16}" y="347" width="32" height="7" fill="#dc2626"/></g>` }).join('')}
  <polygon points="230,380 970,380 930,1010 270,1010" fill="url(#bin)" stroke="#7c2d12" stroke-width="5"/>
  <polygon points="230,380 970,380 950,420 250,420" fill="#000" opacity=".15"/>
  ${qrPanel(code, 600, 700, 330, { stroke: '#7c2d12' })}`
}

function pedalBin(code, acc) {
  return `<defs>${grad('can', '#67e8f9', acc, '#083344')}</defs>
  ${shadow(600, 1140, 400, 40)}
  <path d="M300 330 L900 330 L870 1070 Q600 1120 330 1070 Z" fill="url(#can)" stroke="#083344" stroke-width="5"/>
  <g transform="rotate(-12 300 330)"><rect x="280" y="270" width="660" height="66" rx="30" fill="#164e63"/><rect x="560" y="246" width="100" height="30" rx="10" fill="#0e7490"/></g>
  ${qrPanel(code, 600, 680, 330, { stroke: '#083344' })}
  <g fill="none" stroke="#a5f3fc" stroke-width="7" stroke-linecap="round"><path d="M780 960 a30 30 0 0 1 0 50"/><path d="M800 945 a52 52 0 0 1 0 80"/><path d="M820 930 a74 74 0 0 1 0 110"/></g>
  <rect x="480" y="1070" width="240" height="44" rx="14" fill="#334155"/>`
}

const ASSETS = [
  ['entry-camera', 'SLAB:D:CAM_LAB01', 'Entry Camera', 'ESP32-CAM · face capture at the door', 'CAMERA', '#7c3aed', c => camera(c, '#7c3aed')],
  ['face-server', 'SLAB:D:FACESRV_01', 'Face Recognition Server', 'SFace identity matching', 'SERVER', '#4338ca', c => server(c, '#4338ca')],
  ['door-master', 'SLAB:D:MASTER_LAB01', 'Master Door Controller', 'ESP32 · NFC · fingerprint · lock', 'DOOR', '#0f766e', c => door(c, '#0f766e')],
  ['admin-laptop', 'SLAB:D:PC_ADMIN_LAPTOP', 'Admin Laptop', 'Smart Lab portal host', 'LAB PC', '#1d4ed8', c => laptop(c, '#1d4ed8')],
  ['ur5e-robot', 'SLAB:D:UR5E_01', 'UR5e Robot Arm', 'Universal Robots · 6 axes', 'ROBOT', '#2563eb', c => robot(c, '#2563eb', ['#f8fafc', '#cbd5e1', '#64748b'], ['#7dd3fc', '#38bdf8', '#0c4a6e'])],
  ['fanuc-robot', 'SLAB:D:FANUC_01', 'FANUC Robot Arm', 'FANUC ER-4iA · 6 axes', 'ROBOT', '#ca8a04', c => robot(c, '#ca8a04', ['#fde047', '#facc15', '#a16207'], ['#475569', '#334155', '#0f172a'])],
  ['consumables-bin', 'SLAB:D:BIN_NODE_1', 'Consumables Bin', 'Weighing scale · parts count', 'CONSUMABLES', '#c2410c', c => partsBin(c, '#c2410c')],
  ['security-camera', 'SLAB:D:SECCAM_LAB01', 'Security Camera', 'Lab CCTV · people & PC analysis', 'SECURITY', '#dc2626', c => cctv(c, '#dc2626')],
  ['reusable-bin', 'SLAB:D:REUSE_BIN_1', 'Reusable Items Bin', 'NFC check-out / return', 'REUSABLE', '#0e7490', c => pedalBin(c, '#0e7490')],
  ['student-pc', 'SLAB:D:PC_01', 'Lab PC-01', 'Student workstation', 'LAB PC', '#1d4ed8', c => monitor(c, '#1d4ed8')],
]

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
const man = []
for (const [slug, code, title, sub, cat, acc, scene] of ASSETS) {
  const pill = cat.length * 21 + 60
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500" viewBox="0 0 1200 1500">
  <defs>${DEFS}</defs>
  <rect width="1200" height="1500" fill="#ffffff"/>
  <rect x="24" y="24" width="1152" height="1452" rx="44" fill="none" stroke="${acc}" stroke-opacity=".25" stroke-width="6"/>
  ${scene(code)}
  <rect x="${600 - pill / 2}" y="1215" width="${pill}" height="54" rx="27" fill="${acc}"/>
  <text x="600" y="1252" font-family="Segoe UI, Arial, sans-serif" font-size="28" font-weight="700" letter-spacing="3" fill="#fff" text-anchor="middle">${esc(cat)}</text>
  <text x="600" y="1340" font-family="Segoe UI, Arial, sans-serif" font-size="66" font-weight="800" fill="${INK}" text-anchor="middle">${esc(title)}</text>
  <text x="600" y="1392" font-family="Segoe UI, Arial, sans-serif" font-size="32" fill="#475569" text-anchor="middle">${esc(sub)}</text>
  <text x="600" y="1440" font-family="Consolas, monospace" font-size="28" fill="#94a3b8" text-anchor="middle">${esc(code)}</text>
</svg>`
  writeFileSync(`${dir}/svg/${slug}.svg`, svg)
  await sharp(Buffer.from(svg), { density: 144 }).flatten({ background: '#fff' }).png().withMetadata({ density: 300 }).toFile(`${dir}/png/${slug}.png`)
  man.push({ file: `${slug}.png`, payload: code, title, category: cat })
  console.log('drew', slug)
}
writeFileSync(`${dir}/manifest.json`, JSON.stringify(man, null, 1))
