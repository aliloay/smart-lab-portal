import { useEffect, useState } from 'react'
import {
  CalendarClock, Cpu, Database, Image, KeyRound, ShieldCheck, Timer, Wrench,
} from 'lucide-react'
import { SystemConfig, api } from '../lib/api'
import { ErrorBanner, KV, Notice, PageHeader, SectionTitle, Skeleton } from '../components/ui'

/**
 * Read-only by design: the configuration comes from the server's
 * environment. Changing access policy from a browser tab is exactly the kind
 * of convenience an access-control system should not offer.
 */
export default function Settings() {
  const [c, setC] = useState<SystemConfig | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { api.systemConfig().then(setC).catch(e => setError(e.message)) }, [])

  return (
    <div className="max-w-5xl">
      <PageHeader eyebrow="Administration" title="Settings"
        sub="How this deployment is configured. Values come from the backend environment (.env) and are shown read-only." />
      {error && <ErrorBanner message={error} />}
      {!c ? <Skeleton className="h-80" /> : (
        <div className="space-y-6">
          <Notice icon={<ShieldCheck size={15} />}>
            To change a value, edit <span className="mono">backend/.env</span> (or the Docker
            environment) and restart the API. Policy is deliberately not editable from the browser.
          </Notice>

          <div className="grid md:grid-cols-2 gap-5">
            <section>
              <SectionTitle icon={<CalendarClock size={15} />}>Booking policy</SectionTitle>
              <div className="card p-4"><dl>
                <KV label="Approval">{c.booking_auto_approve ? 'Automatic' : 'Staff approval required'}</KV>
                <KV label="Maximum length">{c.max_booking_hours} hours</KV>
                <KV label="Grace at the door">{c.booking_grace_minutes} min either side</KV>
                <KV label="Reminder">{c.booking_reminder_minutes} min before start</KV>
              </dl></div>
            </section>
            <section>
              <SectionTitle icon={<KeyRound size={15} />}>Credentials & sessions</SectionTitle>
              <div className="card p-4"><dl>
                <KV label="QR token entropy">{c.qr_token_bytes * 8} bits ({c.qr_token_bytes} bytes)</KV>
                <KV label="Login session">{Math.round(c.access_token_expire_minutes / 60)} hours</KV>
                <KV label="Environment" mono>{c.environment}</KV>
              </dl></div>
            </section>
            <section>
              <SectionTitle icon={<Cpu size={15} />}>Devices</SectionTitle>
              <div className="card p-4"><dl>
                <KV label="Offline after">{c.device_stale_seconds} s without a heartbeat</KV>
                <KV label="Device authentication">Shared key (X-Device-Key)</KV>
                <KV label="Relay control">Firmware only - no API endpoint opens a door</KV>
              </dl></div>
            </section>
            <section>
              <SectionTitle icon={<Image size={15} />}>Issue photos</SectionTitle>
              <div className="card p-4"><dl>
                <KV label="Storage" mono>{c.storage_backend}</KV>
                <KV label="Maximum file size">{c.max_upload_mb} MB</KV>
                <KV label="Photos per issue">{c.max_photos_per_issue}</KV>
                <KV label="Stored resolution">up to {c.image_max_dimension} px, metadata stripped</KV>
              </dl></div>
            </section>
            <section className="md:col-span-2">
              <SectionTitle icon={<Timer size={15} />} sub="An unresolved issue past these limits counts as overdue.">
                Maintenance service levels
              </SectionTitle>
              <div className="card p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(c.issue_sla_hours).map(([k, v]) => (
                  <div key={k} className="well p-3"><div className="label">{k.toLowerCase()}</div>
                    <div className="mt-1 font-display text-xl text-white">{v} h</div></div>
                ))}
              </div>
            </section>
            <section className="md:col-span-2">
              <SectionTitle icon={<Database size={15} />}>Security model</SectionTitle>
              <div className="card p-5 grid md:grid-cols-2 gap-x-8 gap-y-2 text-[13px] text-slate-300">
                {[
                  'The backend validates the booking; the QR carries no identity or time.',
                  'The time window and the laboratory are checked server-side on every scan.',
                  'Cancelled, revoked, unknown or wrong-lab credentials are refused and logged.',
                  'The biometric must match the identity from step 1.',
                  'The backend never drives the relay - it cannot open a door.',
                  'If the backend is unreachable, a booking QR fails closed.',
                  'Students see only their own bookings, events and reports.',
                  'No fingerprint or face templates are stored in the database.',
                ].map(t => <div key={t} className="flex gap-2"><ShieldCheck size={14} className="text-ok-soft shrink-0 mt-0.5" />{t}</div>)}
              </div>
            </section>
            <section className="md:col-span-2">
              <SectionTitle icon={<Wrench size={15} />}>Branding</SectionTitle>
              <div className="card p-4 text-[13px] text-slate-300">
                The GIU logo is served from
                <span className="mono"> frontend/public/brand/giu-logo.png</span> (transparent,
                reversed for dark backgrounds). To use another file set
                <span className="mono"> VITE_INSTITUTION_LOGO</span> - see
                <span className="mono"> public/brand/README.md</span>.
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  )
}
