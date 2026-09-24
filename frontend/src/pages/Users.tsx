import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Pencil, Search, ShieldCheck, UserPlus, Users as UsersIcon } from 'lucide-react'
import { Role, User, api } from '../lib/api'
import { roleLabel, useAuth } from '../lib/auth'
import {
  Avatar, Chip, Drawer, EmptyState, ErrorBanner, Field, MetricCard, Modal, Notice, PageHeader,
  Select, Skeleton,
} from '../components/ui'

const ROLE_TONE = { ADMIN: 'violet', LAB_STAFF: 'info', STUDENT: 'idle' } as const

export default function Users() {
  const { user: me } = useAuth()
  const [rows, setRows] = useState<User[] | null>(null)
  const [q, setQ] = useState('')
  const [role, setRole] = useState('')
  const [editing, setEditing] = useState<User | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => api.users().then(setRows)
    .catch(e => { setError(e.message); setRows([]) }), [])
  useEffect(() => { load() }, [load])

  const list = useMemo(() => (rows ?? []).filter(u => (!role || u.role === role) &&
    (!q || `${u.full_name} ${u.email} ${u.auth_subject ?? ''} ${u.department ?? ''}`.toLowerCase()
      .includes(q.toLowerCase()))), [rows, q, role])
  const count = (r: Role) => (rows ?? []).filter(u => u.role === r).length

  return (
    <div>
      <PageHeader eyebrow="Administration" title="Users & roles"
        sub="Accounts, roles, and the auth subject that links a person to the door hardware."
        actions={<button className="btn-primary" onClick={() => setCreating(true)}><UserPlus size={16} />Add user</button>} />
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <MetricCard label="Accounts" value={rows ? rows.length : null} icon={<UsersIcon size={15} />}
                    hint={rows ? `${rows.filter(u => u.is_active).length} active` : undefined} />
        <MetricCard label="Students" value={rows ? count('STUDENT') : null} />
        <MetricCard label="Laboratory staff" value={rows ? count('LAB_STAFF') : null} tone="info" />
        <MetricCard label="Administrators" value={rows ? count('ADMIN') : null} tone="violet" />
      </div>

      <div className="mb-4"><Notice icon={<ShieldCheck size={15} />}>
        The <b>auth subject</b> (e.g. <span className="mono">USER1</span>) must match the label enrolled in
        the fingerprint sensor and the face server. If it does not, step 2 can never be matched to step 1
        and every entry is refused - the safe failure, but check it first when a valid booking is denied.
      </Notice></div>

      <div className="card p-4 mb-4 grid sm:grid-cols-3 gap-3">
        <div className="relative sm:col-span-2">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input pl-9" placeholder="Name, email, auth subject, department" value={q}
                 onChange={e => setQ(e.target.value)} aria-label="Search users" />
        </div>
        <Select value={role} onChange={setRole}
                options={[['', 'All roles'], ['STUDENT', 'Students'], ['LAB_STAFF', 'Laboratory staff'], ['ADMIN', 'Administrators']]} />
      </div>

      <div className="card overflow-hidden">
        {rows === null ? <div className="p-4"><Skeleton className="h-60" /></div>
          : list.length === 0 ? <EmptyState icon={<UsersIcon size={20} />} title="No users match" />
          : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px]">
                <thead><tr>
                  <th className="th">Person</th><th className="th">Role</th><th className="th">Auth subject</th>
                  <th className="th">Department</th><th className="th">Status</th><th className="th"></th>
                </tr></thead>
                <tbody>
                  {list.map(u => (
                    <tr key={u.id} className="tr">
                      <td className="td"><div className="flex items-center gap-3">
                        <Avatar name={u.full_name} size={32} />
                        <div className="min-w-0"><div className="text-slate-100">{u.full_name}
                          {u.id === me?.id && <span className="text-[11px] text-accent-300"> · you</span>}</div>
                          <div className="text-[12px] text-slate-400">{u.email}</div></div></div></td>
                      <td className="td"><Chip tone={ROLE_TONE[u.role]}>{roleLabel(u.role)}</Chip></td>
                      <td className="td">{u.auth_subject ? <span className="mono text-accent-200">{u.auth_subject}</span>
                        : <span className="text-[12px] text-slate-500">not enrolled</span>}</td>
                      <td className="td text-slate-300">{u.department ?? '—'}</td>
                      <td className="td"><Chip tone={u.is_active ? 'ok' : 'bad'} dot>{u.is_active ? 'Active' : 'Disabled'}</Chip></td>
                      <td className="td text-right"><button className="btn-quiet btn-sm" onClick={() => setEditing(u)}>
                        <Pencil size={13} />Edit</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>

      <Drawer open={!!editing} onClose={() => setEditing(null)} title="Edit user" subtitle={editing?.email}>
        {editing && <EditUser u={editing} self={editing.id === me?.id}
                              onSaved={() => { setEditing(null); load() }} />}
      </Drawer>
      {creating && <CreateUser onClose={() => setCreating(false)} onSaved={() => { setCreating(false); load() }} />}
    </div>
  )
}

function EditUser({ u, self, onSaved }: { u: User; self: boolean; onSaved: () => void }) {
  const [f, setF] = useState({ full_name: u.full_name, role: u.role, is_active: u.is_active,
    auth_subject: u.auth_subject ?? '', department: u.department ?? '', student_id: u.student_id ?? '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await api.updateUser(u.id, { ...f, auth_subject: f.auth_subject.trim() || null,
        department: f.department || null, student_id: f.student_id || null })
      onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed') } finally { setBusy(false) }
  }
  return (
    <form onSubmit={save} className="space-y-4">
      {error && <ErrorBanner message={error} />}
      <Field label="Full name"><input className="input" value={f.full_name} required
        onChange={e => setF({ ...f, full_name: e.target.value })} /></Field>
      <Field label="Role" hint={self ? 'You cannot change your own role.' : undefined}>
        <select className="input" value={f.role} disabled={self}
                onChange={e => setF({ ...f, role: e.target.value as Role })}>
          <option value="STUDENT">Student</option><option value="LAB_STAFF">Laboratory staff</option>
          <option value="ADMIN">Administrator</option></select></Field>
      <Field label="Auth subject" hint="Must match the enrolled fingerprint / face label, e.g. USER1.">
        <input className="input mono" value={f.auth_subject} maxLength={32}
               onChange={e => setF({ ...f, auth_subject: e.target.value })} /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Department"><input className="input" value={f.department}
          onChange={e => setF({ ...f, department: e.target.value })} /></Field>
        <Field label="Student ID"><input className="input" value={f.student_id}
          onChange={e => setF({ ...f, student_id: e.target.value })} /></Field>
      </div>
      <label className="flex items-center gap-2.5 text-sm text-slate-200">
        <input type="checkbox" checked={f.is_active} disabled={self} className="accent-sky-500"
               onChange={e => setF({ ...f, is_active: e.target.checked })} />
        Account active {self && <span className="text-slate-500">(cannot disable yourself)</span>}</label>
      <button className="btn-primary w-full" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button>
    </form>
  )
}

function CreateUser({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ email: '', full_name: '', password: '', role: 'STUDENT' as Role,
    auth_subject: '', department: '', student_id: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await api.createUser({ ...f, auth_subject: f.auth_subject.trim() || null,
        department: f.department || null, student_id: f.student_id || null })
      onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed') } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title="Add user">
      <form onSubmit={save} className="space-y-3">
        {error && <ErrorBanner message={error} />}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Full name"><input className="input" required value={f.full_name}
            onChange={e => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label="Role"><select className="input" value={f.role}
            onChange={e => setF({ ...f, role: e.target.value as Role })}>
            <option value="STUDENT">Student</option><option value="LAB_STAFF">Laboratory staff</option>
            <option value="ADMIN">Administrator</option></select></Field>
        </div>
        <Field label="Email"><input className="input" type="email" required value={f.email}
          onChange={e => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Initial password" hint="At least 8 characters. Share it securely."><input className="input"
          type="password" minLength={8} required value={f.password}
          onChange={e => setF({ ...f, password: e.target.value })} /></Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Auth subject"><input className="input mono" value={f.auth_subject} placeholder="USER3"
            onChange={e => setF({ ...f, auth_subject: e.target.value })} /></Field>
          <Field label="Department"><input className="input" value={f.department}
            onChange={e => setF({ ...f, department: e.target.value })} /></Field>
          <Field label="Student ID"><input className="input" value={f.student_id}
            onChange={e => setF({ ...f, student_id: e.target.value })} /></Field>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button>
        </div>
      </form>
    </Modal>
  )
}
