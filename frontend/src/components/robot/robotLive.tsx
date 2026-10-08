/**
 * Robots, live: one fetch, then the WebSocket keeps joints and states current
 * (robot_state for staff, up to 5 a second; robot_status for everyone). A slow
 * poll (15 s) only re-checks staleness - "no new data" turns into
 * TELEMETRY_STALE / OFFLINE from the server, never into "stationary".
 */
import { useCallback, useEffect, useState } from 'react'
import { Robot, RobotState, HomeState, api } from '../../lib/api'
import { useLiveMessages } from '../../lib/live'
import { Chip, Tone } from '../ui'

export function useRobots() {
  const [robots, setRobots] = useState<Robot[] | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(() => {
    api.robots().then(r => { setRobots(r); setError('') })
      .catch(e => setError(e instanceof Error ? e.message : 'Could not load robots'))
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 15000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => {
    if (m.type === 'robot_state') {
      setRobots(list => list?.map(r => r.device_id !== m.device_id ? r : {
        ...r, state: m.state as RobotState, q: m.q, qd: m.qd, joints_moving: m.joints_moving,
        home: m.home as HomeState, telemetry_age_ms: m.telemetry_age_ms, last_seen_at: new Date().toISOString(),
      }) ?? null)
    } else if (m.type === 'robot_status') {
      setRobots(list => {
        if (!list || !list.some(r => r.device_id === m.device_id)) { load(); return list }
        return list.map(r => r.device_id !== m.device_id ? r
          : { ...r, state: m.state as RobotState, home: m.home as HomeState })
      })
    }
  })
  return { robots, error, reload: load }
}

export const STATE_TONE: Record<string, Tone> = {
  MOVING: 'ok', STATIONARY: 'info', TELEMETRY_STALE: 'warn', OFFLINE: 'bad', UNKNOWN: 'idle',
}
export const STATE_TEXT: Record<string, string> = {
  MOVING: 'Moving', STATIONARY: 'Stationary', TELEMETRY_STALE: 'Telemetry stale', OFFLINE: 'Offline',
  UNKNOWN: 'No data',
}
export const HOME_TONE: Record<string, Tone> = { HOME: 'ok', NEAR_HOME: 'info', NOT_HOME: 'warn', UNKNOWN: 'idle' }
export const HOME_TEXT: Record<string, string> = {
  HOME: 'Home', NEAR_HOME: 'Near home', NOT_HOME: 'Not home', UNKNOWN: 'Home: not calibrated / no data',
}

export function RobotStateChip({ state }: { state: string }) {
  return <Chip tone={STATE_TONE[state] ?? 'idle'} dot>{STATE_TEXT[state] ?? state}</Chip>
}

export function HomeChip({ home, state }: { home: string; state: string }) {
  // Moving takes precedence: never show "Home" while the arm is moving.
  if (state === 'MOVING') return <Chip tone="idle">Home: —</Chip>
  return <Chip tone={HOME_TONE[home] ?? 'idle'}>{HOME_TEXT[home] ?? home}</Chip>
}

export function DemoBadge() {
  return <Chip tone="violet" className="font-bold tracking-wide">DEMO DATA · simulation</Chip>
}
