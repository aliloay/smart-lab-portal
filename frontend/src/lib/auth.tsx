import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { api, getToken, setToken, User } from './api'

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
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
    setUser(await api.me())
  }

  function logout() {
    setToken(null)
    setUser(null)
    location.href = '/login'
  }

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)

export const isStaff = (u: User | null) =>
  u?.role === 'ADMIN' || u?.role === 'LAB_STAFF'
