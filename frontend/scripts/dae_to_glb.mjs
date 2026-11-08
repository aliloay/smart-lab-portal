// One-off build step: every Collada robot mesh in public/models -> a binary .glb next to it.
// Collada is XML; parsing ~12 MB of it in the browser froze the page ~1.4 s the first time a robot
// was shown (profiled 2026-10-18). The .glb holds the same geometry in the same raw frame (the
// loader's Z-up -> Y-up rotation is removed here, exactly as MeshArm did at run time).
//   node scripts/dae_to_glb.mjs            (in frontend/; needs the dev dependency @xmldom/xmldom)
import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { DOMParser } from '@xmldom/xmldom'
import * as THREE from 'three'
import { ColladaLoader } from 'three/examples/jsm/loaders/ColladaLoader.js'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'

globalThis.DOMParser = DOMParser
globalThis.FileReader = class {            // GLTFExporter (binary) reads its Blob with a FileReader
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(b => { this.result = b; this.onloadend?.() }) }
  readAsDataURL(blob) { blob.arrayBuffer().then(b => { this.result = 'data:application/octet-stream;base64,' + Buffer.from(b).toString('base64'); this.onloadend?.() }) }
}
// No images in these meshes; a texture reference must not crash the conversion.
THREE.TextureLoader.prototype.load = () => new THREE.Texture()

const ROOT = path.resolve('public/models')
const files = []
const walk = d => { for (const f of readdirSync(d)) { const p = path.join(d, f); statSync(p).isDirectory() ? walk(p) : p.endsWith('.dae') && files.push(p) } }
walk(ROOT)
const exporter = new GLTFExporter()
let n = 0, before = 0, after = 0
for (const f of files) {
  const text = readFileSync(f, 'utf8')
  const collada = new ColladaLoader().parse(text, path.dirname(f) + '/')
  const scene = collada.scene
  scene.rotation.set(0, 0, 0)            // raw URDF frame, as MeshArm used it
  scene.updateMatrixWorld(true)
  const glb = await exporter.parseAsync(scene, { binary: true })
  const out = f.replace(/\.dae$/, '.glb')
  writeFileSync(out, Buffer.from(glb))
  before += text.length; after += glb.byteLength; n++
}
console.log(`${n} meshes: ${(before / 1e6).toFixed(1)} MB Collada -> ${(after / 1e6).toFixed(1)} MB glb`)
