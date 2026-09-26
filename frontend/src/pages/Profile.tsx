import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CalendarCheck, DoorOpen, Fingerprint, KeyRound, ScanFace, ShieldCheck, UserRound, Wrench,
} from 'lucide-react'
import { Booking, Issue, api } from '../lib/api'
import { roleLabel, useAuth } from '../lib/auth'
import { fmtDate } from '../lib/time'
import { Avatar, Chip, KV, MetricCard, Notice, PageHeader, SectionTitle } from '../components/ui'
import { Bloom, GridField } from '../components/visual'
import { AccessSetupChecklist, useAccessSetup } from '../components/AccessSetup'

export default function Profile() {
  const { user } = useAuth()
  const setup = useAccessSetup()
  const [bookings, setBookings] = useState<Booking[] | null>(null)
  const [issues, setIssues] = useState<Issue[] | null>(null)
  useEffect(() => {
    api.bookings().then(b => setBookings(b.filter(x => x.user_id === user?.id))).catch(() => setBookings([]))
    api.issues({ mine: true }).then(setIssues).catch(() => setIssues([]))
  }, [user?.id])
  if (!user) return null

  const visits = (bookings ?? []).filter(b => b.first_entry_at)
  const enrolled = !!user.auth_subject

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader eyebrow="Account" title="Profile" />
      <section className="relative card overflow-hidden">
        <GridField /><Bloom />
        <div className="relative p-6 sm:p-7 flex flex-wrap items-center gap-5">
          <Avatar name={user.full_name} size={72} />
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-2xl font-semibold text-white">{user.full_name}</h2>
            <div className="text-[13.5px] text-slate-300">{user.email}</div>
            <div className="mt-2 flex gap-2 flex-wrap">
              <Chip tone="info">{roleLabel(user.role)}</Chip>
              {user.department && <Chip tone="idle">{user.department}</Chip>}
              <Chip tone={user.is_active ? 'ok' : 'bad'} dot>{user.is_active ? 'Active' : 'Disabled'}</Chip>
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Bookings" value={bookings ? bookings.length : null} icon={<CalendarCheck size={16} />} to="/bookings" />
        <MetricCard label="Laboratory visits" value={bookings ? visits.length : null} icon={<DoorOpen size={16} />}
                    info="Bookings where the door recorded you entering." />
        <MetricCard label="Reports filed" value={issues ? issues.length : null} icon={<Wrench size={16} />} to="/issues" />
        <MetricCard label="Door identity" value={enrolled ? user.auth_subject : 'Not enrolled'}
                    animate={false} tone={enrolled ? 'ok' : 'warn'} icon={<KeyRound size={16} />} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <section>
          <SectionTitle icon={<UserRound size={15} />}>Account details</SectionTitle>
          <div className="card p-4"><dl>
            <KV label="Name">{user.full_name}</KV>
            <KV label="Email">{user.email}</KV>
            <KV label="Role">{roleLabel(user.role)}</KV>
            <KV label="Student ID">{user.student_id ?? '—'}</KV>
            <KV label="Department">{user.department ?? '—'}</KV>
            <KV label="Member since">{user.created_at ? fmtDate(user.created_at) : '—'}</KV>
          </dl></div>
        </section>
        <section>
          <SectionTitle icon={<ShieldCheck size={15} />}>Lab access setup</SectionTitle>
          <div className="card p-5 space-y-4">
            {setup ? <>
              <p className={`text-[13px] ${setup.complete ? 'text-ok-soft' : 'text-amber-100/90'}`}>{setup.summary}</p>
              <AccessSetupChecklist setup={setup} />
            </> : <div className="text-[13px] text-slate-400">Loading…</div>}
            <Notice icon={<ScanFace size={15} />}>
              At the door: first your booking QR code or RFID card, then your fingerprint or face,
              which must belong to the same person. Your fingerprint stays inside the door's sensor
              and face images stay on the face server; the portal stores only whether they are
              registered.
            </Notice>
            <Link to="/bookings" className="btn-ghost btn-sm">View my bookings and entries</Link>
          </div>
        </section>
      </div>
    </div>
  )
}
