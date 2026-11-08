import type { PcLan } from './api'

/** One status for a lab PC from its two independent sources (2026-10-21):
 *  the LAN check (cable + powered, nothing installed on the PC) and the agent's heartbeat
 *  (signed-in user, screen, controls). The LAN answer wins for OFF: an unplugged PC is off at
 *  once, not 90 s later when its last heartbeat goes stale. */
export type PcStatus = { word: string; tone: 'ok' | 'idle' | 'warn' | 'bad'; agent: boolean }

export function pcStatus(e: { online: boolean | null; state: string | null; lan?: PcLan | null }): PcStatus {
  // 2026-11-03 lab: PC-6 reports through the engineer PC's relay (GIU network) - the laptop's LAN scan only sees
  // the Smart Lab cable, so it said "off" while the agent reported every 30 s. A live agent wins over the scan.
  if (e.lan && !e.lan.present && !e.online) return { word: 'off', tone: 'bad', agent: false }
  if (e.online) {
    const s = (e.state ?? 'on').toLowerCase()
    return { word: s, tone: e.state === 'FAULT' ? 'bad' : e.state === 'RUNNING' ? 'ok' : 'idle', agent: true }
  }
  if (e.lan?.present) return { word: 'on · agent not running', tone: 'warn', agent: false }
  return { word: e.online === false ? 'offline' : 'no data', tone: 'bad', agent: false }
}
