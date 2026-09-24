/**
 * The remaining administrative views. They share one table shell because
 * they are the same interaction: filter a list, read status, act on a row.
 */
import { useEffect, useState } from 'react'
import { api, Alert, Asset, Device, User } from '../lib/api'
import { fmtDateTime, relative } from '../lib/time'
import { Boxes, Bell, Cpu, Users as UsersIcon } from 'lucide-react'
import { Chip, EmptyState, Skeleton, StateDot } from '../components/ui'

export function AdminUsers() {
  const [rows, setRows] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => { api.users().then(setRows).finally(() => setLoading(false)) }, [])
  if (loading) return <div className="space-y-2">{[0,1,2,3,4].map(i=><Skeleton key={i} className="h-10" />)}</div>

  return (
    <div>
      <h1 className="page-title">Users</h1>
      <p className="page-sub">
        The <span className="font-mono text-slate-400">auth subject</span> is
        the link to the door hardware — it must match the enrolled biometric
        identity exactly, or the second factor can never be verified.
      </p>
      <div className="card mt-5 overflow-hidden">
        {rows.length === 0 ? <EmptyState title="No users" /> : (
          <table className="w-full">
            <thead><tr>
              <th className="th">Name</th><th className="th">Email</th>
              <th className="th">Role</th><th className="th">Auth subject</th>
              <th className="th">Department</th><th className="th">Status</th>
            </tr></thead>
            <tbody>
              {rows.map(u => (
                <tr key={u.id} className="tr">
                  <td className="td text-slate-200">{u.full_name}</td>
                  <td className="td text-slate-500">{u.email}</td>
                  <td className="td">
                    <Chip kind={u.role === 'ADMIN' ? 'info' :
                                      u.role === 'LAB_STAFF' ? 'warn' : 'idle'}>
                      {u.role.replace('_',' ')}
                    </Chip>
                  </td>
                  <td className="td">
                    {u.auth_subject
                      ? <span className="mono text-accent-400">{u.auth_subject}</span>
                      : <span className="text-xs text-slate-600">not enrolled</span>}
                  </td>
                  <td className="td text-slate-500">{u.department ?? '—'}</td>
                  <td className="td">
                    <Chip kind={u.is_active ? 'ok' : 'bad'}>
                      {u.is_active ? 'Active' : 'Disabled'}
                    </Chip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export function AdminDevices() {
  const [rows, setRows] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    const load = () => api.devices().then(setRows).finally(() => setLoading(false))
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])
  if (loading) return <div className="space-y-2">{[0,1,2,3,4].map(i=><Skeleton key={i} className="h-10" />)}</div>

  return (
    <div>
      <h1 className="page-title">Devices</h1>
      <p className="page-sub">
        Liveness is derived from heartbeats. A device that has never reported
        shows no data rather than being assumed offline.
      </p>
      <div className="card mt-5 overflow-hidden">
        {rows.length === 0 ? <EmptyState title="No devices registered" /> : (
          <table className="w-full">
            <thead><tr>
              <th className="th">Device</th><th className="th">Type</th>
              <th className="th">Address</th><th className="th">Firmware</th>
              <th className="th">Door</th><th className="th">Last seen</th>
              <th className="th">State</th>
            </tr></thead>
            <tbody>
              {rows.map(d => (
                <tr key={d.id} className="tr">
                  <td className="td">
                    <div className="text-slate-200">{d.name}</div>
                    <div className="text-xs font-mono text-slate-600">{d.device_uid}</div>
                  </td>
                  <td className="td text-slate-500 text-xs">
                    {d.device_type.replace(/_/g,' ')}
                  </td>
                  <td className="td mono text-slate-500">
                    {d.ip_address ?? '—'}
                  </td>
                  <td className="td text-xs text-slate-500">
                    {d.firmware_version ?? '—'}
                  </td>
                  <td className="td">
                    <StateDot state={d.door_closed} labels={['Closed','Open']} />
                  </td>
                  <td className="td text-xs text-slate-500">
                    {d.last_seen_at ? relative(d.last_seen_at) : 'never'}
                  </td>
                  <td className="td">
                    <StateDot state={d.last_seen_at === null ? null : d.is_online}
                              labels={['Online','Offline']} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export function AdminAssets() {
  const [rows, setRows] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const load = () => api.assets().then(setRows).finally(() => setLoading(false))
  useEffect(() => { load() }, [])
  if (loading) return <div className="space-y-2">{[0,1,2,3,4].map(i=><Skeleton key={i} className="h-10" />)}</div>

  return (
    <div>
      <h1 className="page-title">Equipment</h1>
      <div className="card mt-5 overflow-hidden">
        {rows.length === 0 ? <EmptyState title="No equipment registered" /> : (
          <table className="w-full">
            <thead><tr>
              <th className="th">Asset</th><th className="th">Tag</th>
              <th className="th">Category</th><th className="th">Status</th>
              <th className="th"></th>
            </tr></thead>
            <tbody>
              {rows.map(a => (
                <tr key={a.id} className="tr">
                  <td className="td text-slate-200">{a.name}</td>
                  <td className="td mono text-slate-500">{a.asset_tag}</td>
                  <td className="td text-slate-500">{a.category || '—'}</td>
                  <td className="td">
                    <Chip kind={a.status === 'AVAILABLE' ? 'ok' :
                                      a.status === 'MAINTENANCE' ? 'warn' : 'idle'}>
                      {a.status.replace('_',' ')}
                    </Chip>
                  </td>
                  <td className="td text-right">
                    {a.status === 'AVAILABLE' ? (
                      <button onClick={() => api.checkoutAsset(a.id).then(load)}
                              className="text-xs text-accent-400 hover:text-accent-300">
                        Check out
                      </button>
                    ) : a.status === 'CHECKED_OUT' ? (
                      <button onClick={() => api.returnAsset(a.id).then(load)}
                              className="text-xs text-slate-400 hover:text-white">
                        Return
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export function AdminAlerts() {
  const [rows, setRows] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => { api.alerts().then(setRows).finally(() => setLoading(false)) }, [])
  if (loading) return <div className="space-y-2">{[0,1,2,3,4].map(i=><Skeleton key={i} className="h-10" />)}</div>

  return (
    <div>
      <h1 className="page-title">Alerts</h1>
      <div className="card mt-5 overflow-hidden">
        {rows.length === 0 ? (
          <EmptyState title="No alerts" detail="Nothing requires attention." />
        ) : (
          <table className="w-full">
            <thead><tr>
              <th className="th">Severity</th><th className="th">Title</th>
              <th className="th">Detail</th><th className="th">Raised</th>
              <th className="th">State</th>
            </tr></thead>
            <tbody>
              {rows.map(a => (
                <tr key={a.id} className="tr">
                  <td className="td">
                    <Chip kind={a.severity === 'CRITICAL' ? 'bad' :
                                      a.severity === 'WARNING' ? 'warn' : 'info'}>
                      {a.severity}
                    </Chip>
                  </td>
                  <td className="td text-slate-200">{a.title}</td>
                  <td className="td text-slate-500 max-w-md truncate">{a.detail}</td>
                  <td className="td text-slate-500 text-xs">{fmtDateTime(a.created_at)}</td>
                  <td className="td">
                    <Chip kind={a.is_resolved ? 'idle' : 'warn'}>
                      {a.is_resolved ? 'Resolved' : 'Open'}
                    </Chip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
