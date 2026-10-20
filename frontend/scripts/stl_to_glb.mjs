// FANUC arm meshes: binary STL -> welded, quantized .glb next to each STL (same triangles, ~1/5 of the bytes).
// An STL stores every triangle with its own three corners and a face normal (50 bytes per triangle); STLLoader
// draws it flat-shaded. The .glb keeps every triangle, shares the corners (weld) and stores no normals - three.js
// then shades it flat exactly as before (MeshArm sets flatShading for these).
//   node scripts/stl_to_glb.mjs public/models/fanuc_lrmate200id
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { Document, NodeIO } from '@gltf-transform/core'
import { ALL_EXTENSIONS } from '@gltf-transform/extensions'
import { quantize, weld } from '@gltf-transform/functions'

const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
let before = 0, after = 0
for (const dir of process.argv.slice(2)) {
  for (const f of readdirSync(dir).filter(f => f.toLowerCase().endsWith('.stl'))) {
    const file = path.join(dir, f)
    const buf = readFileSync(file)
    const n = buf.readUInt32LE(80)
    if (84 + n * 50 !== buf.length) throw new Error(`${f}: not a binary STL`)
    const pos = new Float32Array(n * 9)
    for (let t = 0; t < n; t++) for (let k = 0; k < 9; k++) pos[t * 9 + k] = buf.readFloatLE(84 + t * 50 + 12 + k * 4)
    const doc = new Document()
    const buffer = doc.createBuffer()
    const acc = doc.createAccessor().setType('VEC3').setArray(pos).setBuffer(buffer)
    const name = f.replace(/\.stl$/i, '')
    const mesh = doc.createMesh(name).addPrimitive(doc.createPrimitive().setAttribute('POSITION', acc))
    doc.createScene().addChild(doc.createNode(name).setMesh(mesh))
    await doc.transform(weld(), quantize())
    const glb = await io.writeBinary(doc)
    writeFileSync(file.replace(/\.stl$/i, '.glb'), glb)
    before += statSync(file).size; after += glb.byteLength
    console.log(`${f}: ${n} triangles, ${(statSync(file).size / 1024).toFixed(0)} KB -> ${(glb.byteLength / 1024).toFixed(0)} KB`)
  }
}
console.log(`total ${(before / 1e6).toFixed(2)} MB -> ${(after / 1e6).toFixed(2)} MB`)
