/**
 * Robots, live: one fetch, then the WebSocket keeps joints and states current
 * (robot_state for staff, up to 5 a second; robot_status for everyone). A slow
 * poll (15 s) only re-checks staleness - "no new data" turns into
 * TELEMETRY_STALE / OFFLINE from the server, never into "stationary".
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Robot, RobotState, HomeState, api } from '../../lib/api'
import { useLiveMessages } from '../../lib/live'
import { Chip, Tone } from '../ui'

const STALE_S = 3, OFFLINE_S = 30

/** The state as of now: data that stopped arriving is stale / offline at once,
 *  not only at the next poll ("moving" never lingers after telemetry stops). */
export function effective(r: Robot, now: number): Robot & { stale: boolean } {
  const age = r.last_seen_at ? (now - Date.parse(r.last_seen_at)) / 1000 : Infinity
  let state = r.state
  if (age > OFFLINE_S) state = 'OFFLINE'
  else if (age > STALE_S && (state === 'MOVING' || state === 'STATIONARY')) state = 'TELEMETRY_STALE'
  return { ...r, state, stale: state === 'TELEMETRY_STALE' || state === 'OFFLINE' }
}

export function useNow(everyMs = 1000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), everyMs); return () => window.clearInterval(t) }, [everyMs])
  return now
}

export function useRobots({ includeStoppedDemos = false } = {}) {
  const [raw, setRobots] = useState<Robot[] | null>(null)
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
  const now = useNow()
  const all = useMemo(() => raw?.map(r => effective(r, now)) ?? null, [raw, now])
  // A simulation that is not running is not a robot in the lab: hidden unless asked for.
  const robots = useMemo(() => all?.filter(r => includeStoppedDemos || !(r.demo && r.state === 'OFFLINE')) ?? null,
                         [all, includeStoppedDemos])
  const stoppedDemos = (all?.length ?? 0) - (robots?.length ?? 0)
  return { robots, stoppedDemos, error, reload: load }
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
  HOME: 'Home', NEAR_HOME: 'Near home', NOT_HOME: 'Not home', UNKNOWN: 'Home: not set',
}

export function RobotStateChip({ state }: { state: string }) {
  return <Chip tone={STATE_TONE[state] ?? 'idle'} dot>{STATE_TEXT[state] ?? state}</Chip>
}

export function HomeChip({ home, state }: { home: string; state: string }) {
  // Moving takes precedence: never show "Home" while the arm is moving.
  if (state === 'MOVING') return <Chip tone="idle">Home: —</Chip>
  return <Chip tone={HOME_TONE[home] ?? 'idle'}>{HOME_TEXT[home] ?? home}</Chip>
}

export const FUSION: Record<string, { text: string; tone: Tone; why: string }> = {
  MOVEMENT_VERIFIED: { text: 'Movement verified', tone: 'ok', why: "Telemetry says moving and the camera saw motion in the robot's box." },
  MOVEMENT_TELEMETRY_ONLY: { text: 'Telemetry only', tone: 'warn', why: "Telemetry says moving; the camera saw no motion in the box (box placement, camera angle or the motion is too small to see)." },
  VISUALLY_OCCLUDED: { text: 'Camera view blocked', tone: 'info', why: "Telemetry says moving; a person stands in front of the robot's box." },
  STATIONARY_VERIFIED: { text: 'Still (both agree)', tone: 'info', why: "Telemetry and camera both see no movement." },
  STATIONARY: { text: 'Still (telemetry)', tone: 'idle', why: "Telemetry says still; no usable camera view to compare." },
  VISUAL_ANOMALY: { text: 'Sensor disagreement', tone: 'bad', why: "The camera sees motion in the robot's box while telemetry says still." },
  VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE: { text: 'Motion seen, no telemetry', tone: 'bad', why: "Telemetry is down and the camera sees motion in the robot's box." },
  TELEMETRY_STALE: { text: 'Telemetry stale', tone: 'warn', why: "No recent telemetry and the camera sees nothing moving." },
  OFFLINE: { text: 'Offline', tone: 'bad', why: "No telemetry." },
  SIMULATION: { text: 'Simulation - not compared', tone: 'violet', why: "Demo telemetry is never compared with the real camera." },
  UNKNOWN: { text: 'Unknown', tone: 'idle', why: "Not enough data." },
}

export function FusionChip({ fusion }: { fusion?: string | null }) {
  const f = FUSION[fusion ?? 'UNKNOWN'] ?? FUSION.UNKNOWN
  return <span title={f.why}><Chip tone={f.tone}>{f.text}</Chip></span>
}

export function DemoBadge() {
  return <Chip tone="violet" className="font-bold tracking-wide">DEMO DATA · simulation</Chip>
}
