import { api } from './api'

/** "Whenever an admin signs in - whatever the device, place or connection - he IS the master"
 *  (owner 2026-10-21). Called after an admin's sign-in: the admin becomes the master. If this browser
 *  runs on a lab PC with the agent, the agent (127.0.0.1 only) proves which PC it is and that PC becomes
 *  the master PC. No agent (own laptop, phone, Wi-Fi): the admin is master from this browser alone. */
const AGENT = 'http://127.0.0.1:47123/whoami'

export function deviceLabel(ua = navigator.userAgent): string {
  const os = /Android/i.test(ua) ? 'Android' : /iPhone|iPad/i.test(ua) ? 'iOS' : /Windows NT 6\.1/.test(ua) ? 'Windows 7'
    : /Windows/i.test(ua) ? 'Windows' : /Mac OS X/i.test(ua) ? 'macOS' : /Linux/i.test(ua) ? 'Linux' : 'device'
  const br = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Firefox\//.test(ua) ? 'Firefox'
    : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'browser'
  return `${os} · ${br}`
}

/** Ask this PC's agent (127.0.0.1 only) which lab PC this browser runs on; {} when there is no agent. */
export async function agentProof(nonce: string): Promise<{ device_uid?: string; proof?: string }> {
  try {
    const ctl = new AbortController()
    const t = window.setTimeout(() => ctl.abort(), 1500)
    const r = await fetch(`${AGENT}?nonce=${nonce}`, { signal: ctl.signal })
    window.clearTimeout(t)
    return r.ok ? await r.json() : {}
  } catch { return {} }
}

export async function claimMaster(): Promise<void> {
  try {
    const { nonce } = await api.masterNonce()
    let who: { device_uid?: string; proof?: string } = {}
    try {
      const ctl = new AbortController()
      const t = window.setTimeout(() => ctl.abort(), 1500)
      const r = await fetch(`${AGENT}?nonce=${nonce}`, { signal: ctl.signal })
      window.clearTimeout(t)
      if (r.ok) who = await r.json()
    } catch { /* no agent on this device: the admin is master from this browser */ }
    await api.masterClaim({ device_label: deviceLabel(), nonce, ...who })
  } catch { /* never blocks the sign-in */ }
}

/** Once per browser session for an admin whose stored sign-in is restored (opening the portal). */
export function claimMasterOnce(userId: number): void {
  const k = `smartlab.master.${userId}`
  try { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, '1') } catch { /* ignore */ }
  void claimMaster()
}
