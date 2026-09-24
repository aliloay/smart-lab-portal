import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity, Boxes, Camera, CircuitBoard, Cpu, DoorClosed, Fingerprint,
  Gauge, MapPin, Radio, ScanFace, Server, Users,
} from 'lucide-react'
import { AccessEvent, Asset, Device, LabStatus, api } from '../lib/api'
import { fmtClock, fmtDateTime } from '../lib/time'
import {
  Chip, Dot, EmptyState, SectionTitle, Skeleton, StateDot, eventTone,
} from '../components/ui'
import { Bloom, CircuitTrace, GridField, RoboticArm } from '../components/visual'

export default function LabDetail() {
  const { id } = useParams()
  const labId = Number(id)
  const [status, setStatus] = useState<LabStatus | null>(null)
  const [events, setEvents] = useState<AccessEvent[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [devices, setDevices] = useState<Device[]>([])
  const [sensors, setSensors] = useState<unknown[]>([])
  const [liveConnected, setLiveConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    api.lab(labId).then(setStatus).catch(() => {})
    api.labActivity(labId).then(setEvents).catch(() => {})
    api.assets(labId).then(setAssets).catch(() => {})
    api.devices().then(d => setDevices(d.filter(x => x.lab_id === labId))).catch(() => {})
    api.labSensors(labId).then(setSensors).catch(() => setSensors([]))
  }, [labId])

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/activity?lab_id=${labId}`)
    wsRef.current = ws
    ws.onopen = () => setLiveConnected(true)
    ws.onclose = () => setLiveConnected(false)
    ws.onerror = () => setLiveConnected(false)
    ws.onmessage = m => {
      try {
        const ev = JSON.parse(m.data) as AccessEvent
        setEvents(p => [ev, ...p].slice(0, 120))
        if (ev.event_type.startsWith('DOOR') || ev.event_type.startsWith('ACCESS')) {
          api.lab(labId).then(setStatus).catch(() => {})
        }
      } catch { /* malformed frame */ }
    }
    const ka = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)
    return () => { clearInterval(ka); ws.close() }
  }, [labId])

  if (!status) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-28 w-full rounded-xl" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      </div>
    )
  }

  const { lab } = status
  const dev = (t: string) => devices.find(d => d.device_type === t)
  const master = dev('MASTER_CONTROLLER')
  const camera = dev('CAMERA')
  const faceSrv = dev('FACE_SERVER')

  return (
    <div className="space-y-7">
      {/* --------------------------------------------------------- hero */}
      <section className="relative card overflow-hidden">
        <GridField />
        <Bloom />
        <RoboticArm className="absolute -right-8 -top-10 w-[260px] h-auto
                               opacity-[.3] hidden md:block" />
        <div className="relative p-6 sm:p-7">
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="mono text-accent-400">{lab.code}</span>
                <span className="text-slate-700">·</span>
                <span className="text-[11px] text-slate-500">{lab.category}</span>
              </div>
              <h1 className="mt-2 text-[24px] font-semibold text-white tracking-tight">
                {lab.name}
              </h1>
              <p className="mt-2 text-sm text-slate-400 max-w-2xl leading-relaxed">
                {lab.description || 'No description provided.'}
              </p>
              <div className="mt-3 flex items-center gap-4 text-[12px] text-slate-500">
                <span className="flex items-center gap-1.5">
                  <MapPin size={12} />{lab.location || 'Location not set'}
                </span>
                <span className="flex items-center gap-1.5">
                  <Users size={12} />Capacity {lab.capacity}
                </span>
              </div>
            </div>

            {lab.has_controller ? (
              <Chip tone={status.occupied ? 'warn' : 'ok'}>
                {status.occupied ? 'Occupied' : 'Available'}
              </Chip>
            ) : (
              <Chip tone="idle">No access hardware</Chip>
            )}
          </div>
        </div>
      </section>

      {/* --------------------------------------- cyber-physical system */}
      <section>
        <SectionTitle icon={<CircuitBoard size={14} />}>
          Cyber-physical system
        </SectionTitle>

        {lab.has_controller ? (
          <div className="relative card p-5 overflow-hidden">
            <CircuitTrace className="absolute top-2 right-4 w-32 opacity-40" />
            <div className="relative grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              <Node icon={<DoorClosed size={15} />} title="Door"
                    state={status.door_closed} labels={['Locked', 'Open']} />
              <Node icon={<Cpu size={15} />} title="Master controller"
                    state={status.controller_online} labels={['Online', 'Offline']}
                    detail={master?.device_uid} />
              <Node icon={<Camera size={15} />} title="Entry camera"
                    state={status.camera_online} labels={['Online', 'Offline']}
                    detail={camera?.ip_address ?? undefined} />
              <Node icon={<Server size={15} />} title="Face recognition"
                    state={faceSrv?.last_seen_at ? faceSrv.is_online : null}
                    labels={['Online', 'Offline']}
                    detail={faceSrv?.ip_address ?? undefined} />
              <Node icon={<Radio size={15} />} title="RFID reader"
                    state={status.controller_online} labels={['Ready', 'Unavailable']}
                    detail="Reported by the controller" />
              <Node icon={<Fingerprint size={15} />} title="Fingerprint"
                    state={status.controller_online} labels={['Ready', 'Unavailable']}
                    detail="Reported by the controller" />
            </div>

            <p className="relative mt-4 text-[11px] text-slate-600 leading-relaxed">
              Reader and sensor states are inferred from the controller's
              heartbeat — they are not independently reported, so a controller
              that is online with a broken reader will still show ready here.
            </p>
          </div>
        ) : (
          <div className="card">
            <EmptyState icon={<CircuitBoard size={20} />}
              title="No access-control hardware installed"
              detail="This laboratory can be booked and credentials are issued
                      normally, but there is no door controller to respond to
                      them yet." />
          </div>
        )}
      </section>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* ------------------------------------------------- activity */}
        <div className="lg:col-span-2">
          <SectionTitle icon={<Activity size={14} />}
            action={
              <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
                <Dot tone={liveConnected ? 'ok' : 'idle'} live={liveConnected} />
                {liveConnected ? 'Live' : 'Reconnecting'}
              </span>}>
            Access activity
          </SectionTitle>

          <div className="card max-h-[540px] overflow-y-auto">
            {events.length === 0 ? (
              <EmptyState icon={<Activity size={20} />}
                title="No activity recorded"
                detail="Events appear here the moment they happen at the door." />
            ) : (
              <ol className="relative divide-y divide-ink-700/60">
                {events.map((e, i) => (
                  <motion.li key={`${e.id}-${i}`}
                    initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: .22 }}
                    className="px-5 py-3 flex items-start gap-3">
                    <span className="mono text-slate-600 pt-0.5 shrink-0 tnum">
                      {fmtClock(e.created_at)}
                    </span>
                    <Chip tone={eventTone(e.event_type)}>
                      {e.event_type.replace(/_/g, ' ')}
                    </Chip>
                    <span className="flex-1 min-w-0 text-xs text-slate-400">
                      {e.message}
                      {e.user_name && (
                        <span className="text-slate-600"> · {e.user_name}</span>
                      )}
                    </span>
                  </motion.li>
                ))}
              </ol>
            )}
          </div>
        </div>

        {/* ------------------------------------------------- side rail */}
        <div className="space-y-6">
          <div>
            <SectionTitle icon={<Users size={14} />}>Occupancy</SectionTitle>
            <div className="card-pad">
              {status.current_users.length === 0 ? (
                <div className="text-sm text-slate-500">Nobody currently inside</div>
              ) : (
                <ul className="space-y-2">
                  {status.current_users.map(n => (
                    <li key={n} className="flex items-center gap-2 text-sm text-slate-300">
                      <Dot tone="ok" live />{n}
                    </li>
                  ))}
                </ul>
              )}
              {status.next_booking_at && (
                <div className="mt-4 pt-3 border-t border-ink-700 text-xs text-slate-500">
                  Next booking {fmtDateTime(status.next_booking_at)}
                </div>
              )}
            </div>
          </div>

          <div>
            <SectionTitle icon={<Gauge size={14} />}>Environment</SectionTitle>
            <div className="card-pad">
              {sensors.length === 0 ? (
                <>
                  <div className="text-sm text-slate-500">No data available</div>
                  <p className="mt-1.5 text-[11px] text-slate-600 leading-relaxed">
                    No environmental sensor node is reporting for this
                    laboratory. Temperature, humidity and air quality appear
                    here once one is deployed.
                  </p>
                </>
              ) : (
                <div className="text-sm text-slate-300">
                  {sensors.length} readings recorded
                </div>
              )}
            </div>
          </div>

          <div>
            <SectionTitle icon={<Boxes size={14} />}>
              Equipment
              <span className="ml-1.5 text-slate-600 font-normal">
                ({assets.length})
              </span>
            </SectionTitle>
            <div className="card divide-y divide-ink-700/60 max-h-72 overflow-y-auto">
              {assets.length === 0
                ? <EmptyState icon={<Boxes size={18} />} title="No equipment registered" />
                : assets.map(a => (
                    <div key={a.id}
                         className="px-5 py-3 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[13px] text-slate-200 truncate">{a.name}</div>
                        <div className="mono text-slate-600">{a.asset_tag}</div>
                      </div>
                      <Chip tone={a.status === 'AVAILABLE' ? 'ok'
                                : a.status === 'MAINTENANCE' ? 'warn' : 'idle'}>
                        {a.status.replace('_', ' ')}
                      </Chip>
                    </div>
                  ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Node({ icon, title, state, labels, detail }: {
  icon: React.ReactNode
  title: string
  state: boolean | null
  labels: [string, string]
  detail?: string
}) {
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-900/50 p-3.5">
      <div className="flex items-center gap-2 text-slate-400">
        <span className="text-accent-400">{icon}</span>
        <span className="text-[12px]">{title}</span>
      </div>
      <div className="mt-2.5">
        <StateDot state={state} labels={labels} size="md" />
      </div>
      {detail && <div className="mono text-slate-600 mt-1.5 truncate">{detail}</div>}
    </div>
  )
}
