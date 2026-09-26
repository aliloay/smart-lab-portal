import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react'
import { api, getToken, setToken, User } from './api'

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => void
  refresh: () => Promise<void>
}

const Ctx = createContext<AuthCtx>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore the session on load. A token in storage is not proof of a valid
  // session - it may have expired - so it is verified against /auth/me
  // before any protected UI renders.
  useEffect(() => {
    if (!getToken()) { setLoading(false); return }
    api.me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const r = await api.login(email, password)
    setToken(r.access_token)
    const me = await api.me()
    // A fresh sign-in shows the "finish your lab access setup" banner again.
    try { sessionStorage.removeItem(`smartlab.setupBanner.${me.id}`) } catch { /* ignore */ }
    setUser(me)
    return me
  }

  function logout() {
    setToken(null)
    setUser(null)
    location.href = '/login'
  }

  const refresh = useCallback(async () => { setUser(await api.me()) }, [])

  return (
    <Ctx.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </Ctx.Provider>
  )
}

export const useAuth = () => useContext(Ctx)

export const isStaff = (u: User | null) =>
  u?.role === 'ADMIN' || u?.role === 'LAB_STAFF'

export const isAdmin = (u: User | null) => u?.role === 'ADMIN'

export const roleLabel = (r?: string) =>
  r === 'ADMIN' ? 'Administrator' : r === 'LAB_STAFF' ? 'Laboratory staff' : 'Student'

/** "Dr. Ramy Amir ..." -> "Ramy": the name to greet someone by. */
export function firstName(full?: string | null): string {
  const words = (full ?? '').split(/\s+/).filter(Boolean)
  const TITLES = /^(dr|prof|eng|mr|mrs|ms|miss)\.?$/i
  return words.find(w => !TITLES.test(w)) ?? words[0] ?? ''
}
