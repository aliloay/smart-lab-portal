import type { RootState } from '@react-three/fiber'

/** three.js checks every shader program for errors right after linking (getProgramInfoLog). That
 *  makes the browser finish each compile at once, on the main thread: 2.85 s of frozen page when the
 *  dashboard or a robot page opened (profiled 2026-10-18). Production builds skip the check; in
 *  development it stays on, so a broken shader still shows its error. */
export function noShaderChecks(state: RootState) {
  if (import.meta.env.PROD) state.gl.debug.checkShaderErrors = false
}
