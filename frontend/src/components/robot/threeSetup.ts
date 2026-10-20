import type { RootState } from '@react-three/fiber'
import type * as THREE from 'three'

/** three.js checks every shader program for errors right after linking (getProgramInfoLog). That
 *  makes the browser finish each compile at once, on the main thread: 2.85 s of frozen page when the
 *  dashboard or a robot page opened (profiled 2026-10-18). Production builds skip the check; in
 *  development it stays on, so a broken shader still shows its error.
 *
 *  2026-10-20 (owner: "Robots & PCs takes too much to load"): even without the check, the first
 *  render still waited for the compile - three's uniform setup (WebGLUniforms) asks the driver for
 *  the program's uniforms, which blocks until compiling is done: 1.2 s of main-thread time and a
 *  609 ms freeze on the Robots & PCs tab (two 3D views). So a render that meets materials with no
 *  program yet is skipped; renderer.compileAsync compiles them in parallel (KHR_parallel_shader_compile,
 *  falls back to a plain compile where the browser lacks it) and the scene is drawn once they are
 *  ready. The page stays responsive; the 3D view appears when its shaders are done. */
export function noShaderChecks(state: RootState) {
  if (import.meta.env.PROD) state.gl.debug.checkShaderErrors = false
  asyncFirstCompile(state)
}

const MAX_WAIT_MS = 2000

function asyncFirstCompile(state: RootState) {
  const gl = state.gl as THREE.WebGLRenderer & { __asyncCompile?: boolean }
  if (gl.__asyncCompile || typeof gl.compile !== 'function') return
  // Without KHR_parallel_shader_compile there is nothing to wait for: render as before.
  if (gl.extensions.get('KHR_parallel_shader_compile') === null) return
  gl.__asyncCompile = true
  const render = gl.render.bind(gl)
  const tried = new WeakSet<THREE.Material>()      // each material gets one async round, never a loop
  let compiling = false
  gl.render = (scene: THREE.Object3D, camera: THREE.Camera) => {
    if (compiling) return
    if ((scene as THREE.Scene).isScene && needsCompile(gl, scene, tried)) {
      compiling = true
      compileThen(gl, scene, camera, () => { compiling = false; state.invalidate() })
      return
    }
    render(scene, camera)
  }
}

/** Not renderer.compileAsync: its readiness poll throws (program undefined) when a material is
 *  replaced or disposed while it waits - R3F does that as models load - and its promise then never
 *  settles, which would leave the view blank for good (seen 2026-10-20 before release). Here a
 *  material that lost its program counts as ready, any error ends the wait, and the scene is drawn
 *  after MAX_WAIT_MS whatever happens. */
function compileThen(gl: THREE.WebGLRenderer, scene: THREE.Object3D, camera: THREE.Camera, done: () => void) {
  let mats: Set<THREE.Material>
  try {
    const r = gl.compile(scene, camera) as unknown
    if (!(r instanceof Set)) { done(); return }
    mats = r as Set<THREE.Material>
  } catch { done(); return }
  const t0 = performance.now()
  const check = () => {
    try {
      for (const m of mats) {
        const prog = (gl.properties.get(m) as { currentProgram?: { isReady?: () => boolean } }).currentProgram
        if (!prog || typeof prog.isReady !== 'function' || prog.isReady()) mats.delete(m)
      }
    } catch { mats.clear() }
    if (mats.size === 0 || performance.now() - t0 > MAX_WAIT_MS) done()
    else window.setTimeout(check, 16)
  }
  window.setTimeout(check, 0)
}

function needsCompile(gl: THREE.WebGLRenderer, scene: THREE.Object3D, tried: WeakSet<THREE.Material>) {
  let need = false
  scene.traverseVisible(o => {
    const m = (o as THREE.Mesh).material
    if (!m) return
    for (const mat of Array.isArray(m) ? m : [m]) {
      if (tried.has(mat)) continue
      tried.add(mat)
      if (!(gl.properties.get(mat) as { currentProgram?: unknown }).currentProgram) need = true
    }
  })
  return need
}
