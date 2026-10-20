// Compacts the robot .glb meshes in place (after scripts/dae_to_glb.mjs) - same shapes, a fraction of the bytes.
// 2026-10-20: the UR5e twin downloaded ~8.3 MB because the converted meshes were unindexed "triangle soup" with a
// separate normal per corner (each position stored ~5.6 times). Here, per primitive:
//   * flat-shaded (every triangle's 3 normals equal - the UR5e meshes): drop NORMAL, weld the positions; three.js
//     shades a primitive without normals flat (GLTFLoader sets flatShading), i.e. exactly as before;
//   * smooth-shaded (the Robotiq gripper): keep NORMAL, weld bitwise-identical vertices only;
// then quantize (KHR_mesh_quantization, read natively by three's GLTFLoader) and write one binary .glb.
// No simplification: every triangle is kept.
//   node scripts/compact_glb.mjs public/models/ur5e public/models/robotiq_2f85
import { readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { NodeIO } from '@gltf-transform/core'
import { ALL_EXTENSIONS } from '@gltf-transform/extensions'
import { dedup, prune, quantize, weld } from '@gltf-transform/functions'

const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)

function flatShaded(prim) {
  const n = prim.getAttribute('NORMAL'), idx = prim.getIndices()
  if (!n) return false
  const tri = idx ? idx.getCount() / 3 : n.getCount() / 3
  const a = [], b = [], c = []
  let flat = 0
  for (let t = 0; t < tri; t++) {
    const i = idx ? [idx.getScalar(3 * t), idx.getScalar(3 * t + 1), idx.getScalar(3 * t + 2)] : [3 * t, 3 * t + 1, 3 * t + 2]
    n.getElement(i[0], a); n.getElement(i[1], b); n.getElement(i[2], c)
    const same = (u, v) => Math.abs(u[0] - v[0]) < 1e-3 && Math.abs(u[1] - v[1]) < 1e-3 && Math.abs(u[2] - v[2]) < 1e-3
    if (same(a, b) && same(a, c)) flat++
  }
  return flat / Math.max(tri, 1) > 0.97
}

let before = 0, after = 0
for (const dir of process.argv.slice(2)) {
  for (const f of readdirSync(dir).filter(f => f.endsWith('.glb'))) {
    const file = path.join(dir, f)
    const bin = file + '.bin'
    before += statSync(file).size + (statSync(bin, { throwIfNoEntry: false })?.size ?? 0)
    const doc = await io.read(file)
    let flat = 0, smooth = 0
    for (const mesh of doc.getRoot().listMeshes()) for (const prim of mesh.listPrimitives()) {
      if (flatShaded(prim)) { prim.setAttribute('NORMAL', null); flat++ } else smooth++
    }
    await doc.transform(weld(), dedup(), prune(), quantize())
    for (const buf of doc.getRoot().listBuffers()) buf.setURI('')          // one self-contained .glb
    const glb = await io.writeBinary(doc)
    const { writeFileSync } = await import('node:fs')
    writeFileSync(file, glb)
    after += glb.byteLength
    console.log(`${file}: ${flat} flat / ${smooth} smooth primitives -> ${(glb.byteLength / 1024).toFixed(1)} KB`)
  }
}
console.log(`total ${(before / 1e6).toFixed(2)} MB -> ${(after / 1e6).toFixed(2)} MB`)
