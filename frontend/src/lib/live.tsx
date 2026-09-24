/**
 * One live connection for the whole portal.
 *
 * Previously each page opened its own unauthenticated socket. Now a single
 * authenticated WebSocket is shared: pages subscribe to the messages they
 * care about, and the notification count updates the moment the server
 * raises one. The connection reconnects with backoff, and every consumer
 * still loads its data over REST - the socket only makes it fresher, it is
 * never the only source of truth.
 */
import {
  createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState,
} from 'react'
import { AccessEvent, Notification, api, getToken } from './api'

export type LiveMessage =
  | { type: 'access_event'; event: AccessEvent }
  | { type: 'notification'; user_id: number; notification: Notification }
  | { type: 'staff'; kind: string; issue_id?: number; event?: string }

type Handler = (m: LiveMessage) => void

interface LiveCtx {
  connected: boolean
  unread: number
  refreshUnread: () => void
  subscribe: (h: Handler) => () => void
}

const Ctx = createContext<LiveCtx>({
  connected: false, unread: 0, refreshUnread: () => {}, subscribe: () => () => {},
})

export function LiveProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false)
  const [unread, setUnread] = useState(0)
  const handlers = useRef(new Set<Handler>())

  const refreshUnread = useCallback(() => {
    api.unreadCount().then(r => setUnread(r.unread)).catch(() => {})
  }, [])

  useEffect(() => {
    let ws: WebSocket | null = null
    let stopped = false
    let retry = 0
    let timer: number | undefined
    let keepalive: number | undefined

    const open = () => {
      const token = getToken()
      if (!token || stopped) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/activity?token=${encodeURIComponent(token)}`)
      ws.onopen = () => { retry = 0; setConnected(true) }
      ws.onmessage = m => {
        let msg: LiveMessage
        try { msg = JSON.parse(m.data) } catch { return }
        if (msg.type === 'notification') setUnread(n => n + 1)
        handlers.current.forEach(h => { try { h(msg) } catch { /* one bad consumer */ } })
      }
      ws.onclose = () => {
        setConnected(false)
        if (stopped) return
        // 1s, 2s, 4s ... capped at 30s.
        timer = window.setTimeout(open, Math.min(30000, 1000 * 2 ** retry++))
      }
      ws.onerror = () => ws?.close()
    }
    open()
    keepalive = window.setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)

    return () => {
      stopped = true
      window.clearTimeout(timer)
      window.clearInterval(keepalive)
      ws?.close()
    }
  }, [])

  // The count is re-read from the database periodically, so a dropped frame
  // can never leave the badge wrong for long.
  useEffect(() => {
    refreshUnread()
    const t = window.setInterval(refreshUnread, 60000)
    return () => window.clearInterval(t)
  }, [refreshUnread])

  const subscribe = useCallback((h: Handler) => {
    handlers.current.add(h)
    return () => { handlers.current.delete(h) }
  }, [])

  return (
    <Ctx.Provider value={{ connected, unread, refreshUnread, subscribe }}>
      {children}
    </Ctx.Provider>
  )
}

export const useLive = () => useContext(Ctx)

/** Subscribe to live messages for the lifetime of a component. */
export function useLiveMessages(handler: Handler) {
  const { subscribe } = useLive()
  const ref = useRef(handler)
  ref.current = handler
  useEffect(() => subscribe(m => ref.current(m)), [subscribe])
}
