import { lazy, ReactNode, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import EmergencyMessage from './components/EmergencyMessage'
import HazardAlarm from './components/HazardAlarm'
import WelcomeIntro from './components/WelcomeIntro'
import { Spinner } from './components/ui'
import { firstName, isAdmin, isStaff, useAuth } from './lib/auth'
import { LiveProvider } from './lib/live'
import { watchDeployments } from './lib/version'

import Login from './pages/Login'
import StudentDashboard from './pages/dashboards/StudentDashboard'
import StaffDashboard from './pages/dashboards/StaffDashboard'
import AdminDashboard from './pages/dashboards/AdminDashboard'
// Every page is its own small file, loaded when first opened - and all of
// them are fetched quietly in the background right after sign-in
// (prefetchPages), so later clicks are instant without a big first load.
import Welcome from './pages/Welcome'   // eager: sign-in fades straight into it, no dashboard flash
const loadLabs = () => import('./pages/Labs')
const Labs = lazy(loadLabs)
const loadLabDetail = () => import('./pages/LabDetail')
const LabDetail = lazy(loadLabDetail)
const loadBook = () => import('./pages/Book')
const Book = lazy(loadBook)
const loadMyBookings = () => import('./pages/MyBookings')
const MyBookings = lazy(loadMyBookings)
const loadReservations = () => import('./pages/Reservations')
const Reservations = lazy(loadReservations)
const loadBookingDetail = () => import('./pages/BookingDetail')
const BookingDetail = lazy(loadBookingDetail)
const loadBookingQr = () => import('./pages/BookingQr')
const BookingQr = lazy(loadBookingQr)
const loadSessionDetail = () => import('./pages/SessionDetail')
const SessionDetail = lazy(loadSessionDetail)
const loadSimulation = () => import('./pages/Simulation')
const Simulation = lazy(loadSimulation)
const loadExperiments = () => import('./pages/Experiments')
const Experiments = lazy(loadExperiments)
const loadAccessMonitor = () => import('./pages/AccessMonitor')
const AccessMonitor = lazy(loadAccessMonitor)
const loadDevices = () => import('./pages/Devices')
const Devices = lazy(loadDevices)
const loadEquipment = () => import('./pages/Equipment')
const Equipment = lazy(loadEquipment)
const loadSecurity = () => import('./pages/Security')
const Security = lazy(loadSecurity)
const loadAssetDetail = () => import('./pages/AssetDetail')
const AssetDetail = lazy(loadAssetDetail)
const Incidents = lazy(() => import('./pages/Incidents'))
const Reliability = lazy(() => import('./pages/Reliability'))
const loadAlerts = () => import('./pages/Alerts')
const Alerts = lazy(loadAlerts)
const loadUsers = () => import('./pages/Users')
const Users = lazy(loadUsers)
const loadSettings = () => import('./pages/Settings')
const Settings = lazy(loadSettings)
const loadEmergency = () => import('./pages/Emergency')
const Emergency = lazy(loadEmergency)
const loadReportIssue = () => import('./pages/issues/ReportIssue')
const ReportIssue = lazy(loadReportIssue)
const loadIssueList = () => import('./pages/issues/IssueList')
const IssueList = lazy(loadIssueList)
const loadIssueDetail = () => import('./pages/issues/IssueDetail')
const IssueDetail = lazy(loadIssueDetail)
const Share = lazy(() => import('./pages/Share'))
const loadNotifications = () => import('./pages/Notifications')
const Notifications = lazy(loadNotifications)
const loadProfile = () => import('./pages/Profile')
const Profile = lazy(loadProfile)
const PREFETCH = [loadLabs, loadLabDetail, loadBook, loadMyBookings, loadReservations, loadBookingDetail, loadBookingQr, loadSessionDetail, loadSimulation, loadExperiments, loadAccessMonitor, loadDevices, loadEquipment, loadSecurity, loadAssetDetail, loadAlerts, loadUsers, loadSettings, loadEmergency, loadReportIssue, loadIssueList, loadIssueDetail, loadNotifications, loadProfile,
  () => import('./pages/Reports'), () => import('./pages/Operations'), () => import('./pages/CommandCenter'),
  () => import('./pages/Robots'),
  // 2026-10-19: these were missing, so their first click waited ~1 s for the download.
  () => import('./pages/Incidents'), () => import('./pages/Reliability'), () => import('./pages/SystemAnalytics'),
  () => import('./pages/Monitor'), () => import('./pages/RobotDetail')]
let prefetched = false
function prefetchPages() {
  if (prefetched) return
  prefetched = true
  const idle = (cb: () => void) => ('requestIdleCallback' in window
    ? (window as unknown as { requestIdleCallback: (f: () => void) => void }).requestIdleCallback(cb)
    : globalThis.setTimeout(cb, 300))
  // One after another while the browser is idle: never competes with the page in use.
  const next = (i: number) => { if (i < PREFETCH.length) idle(() => { PREFETCH[i]().catch(() => {}).finally(() => next(i + 1)) }) }
  window.setTimeout(() => next(0), 1500)
}

// Charts pull in Recharts; load them only when a chart page is opened.
const Reports = lazy(() => import('./pages/Reports'))
const Operations = lazy(() => import('./pages/Operations'))
const SystemAnalytics = lazy(() => import('./pages/SystemAnalytics'))
// Command Center and robot pages carry three.js: loaded only when opened.
const CommandCenter = lazy(() => import('./pages/CommandCenter'))
const Robots = lazy(() => import('./pages/Robots'))
const RobotDetail = lazy(() => import('./pages/RobotDetail'))
const Monitor = lazy(() => import('./pages/Monitor'))
const ReportPrint = lazy(() => import('./pages/ReportPrint'))

function Chunk({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Spinner label="Loading" />}>{children}</Suspense>
}

export default function App() {
  const { user, loading } = useAuth()
  const loc = useLocation()

  if (loading) {
    return <div className="min-h-screen grid place-items-center">
      <Spinner label="Restoring session" />
    </div>
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={
          <Navigate to={`/login${loc.pathname !== '/' ? `?next=${encodeURIComponent(loc.pathname)}` : ''}`}
                    replace />} />
      </Routes>
    )
  }

  // Role gates here are for usability; the server's are the ones that matter.
  const staff = isStaff(user)
  const admin = isAdmin(user)
  const staffOnly = (el: ReactNode) => staff ? el : <Navigate to="/" replace />
  const adminOnly = (el: ReactNode) => admin ? el : <Navigate to="/" replace />

  const home = admin ? <AdminDashboard /> : staff ? <StaffDashboard /> : <StudentDashboard />
  prefetchPages()
  watchDeployments()

  // The wall screen: full screen, outside the portal frame (no sidebar).
  if (staff && loc.pathname === '/monitor') {
    return <LiveProvider><Chunk><Monitor /></Chunk><SafetyLayer /></LiveProvider>
  }
  // The Command Center on a wall screen: no sidebar, full screen.
  if (staff && loc.pathname === '/wall') {
    return <LiveProvider><Chunk><CommandCenter wall /></Chunk><SafetyLayer /></LiveProvider>
  }
  // The printable weekly / monthly report: its own page, white, for "Save as PDF".
  if (staff && loc.pathname === '/report') {
    return <><Chunk><ReportPrint /></Chunk><SafetyLayer /></>
  }

  // Sign-in lands here: straight from the login screen into the full-screen welcome, never via the dashboard frame.
  if (loc.pathname === '/login') return <AfterSignIn />
  if (loc.pathname === '/welcome') return <LiveProvider><Welcome /><SafetyLayer /></LiveProvider>

  return (
    <LiveProvider>
      <WelcomeIntro name={firstName(user.full_name)} />
      <Layout>
        <Suspense fallback={<Spinner label="Loading" />}>
        <Routes>
          <Route path="/" element={home} />
          <Route path="/welcome" element={<Welcome />} />
          <Route path="/labs" element={<Labs />} />
          <Route path="/labs/:id" element={<LabDetail />} />
          <Route path="/book" element={<Book />} />
          <Route path="/bookings" element={staff ? <Navigate to="/admin/bookings" replace />
                                                 : <MyBookings />} />
          <Route path="/bookings/:id" element={<BookingDetail />} />
          <Route path="/bookings/:id/qr" element={<BookingQr />} />
          <Route path="/sessions/:id" element={<SessionDetail />} />
          <Route path="/equipment/:id" element={<AssetDetail />} />
          <Route path="/issues" element={<IssueList />} />
          <Route path="/issues/new" element={<ReportIssue />} />
          <Route path="/issues/:id" element={<IssueDetail />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/share" element={<Share />} />
          <Route path="/profile" element={<Profile />} />

          <Route path="/admin/bookings" element={staffOnly(<Reservations />)} />
          <Route path="/admin/access" element={staffOnly(<AccessMonitor />)} />
          <Route path="/admin/devices" element={staffOnly(<Devices />)} />
          <Route path="/admin/equipment" element={staffOnly(<Equipment />)} />
          <Route path="/admin/security" element={staffOnly(<Security />)} />
          <Route path="/command" element={staffOnly(<Chunk><CommandCenter /></Chunk>)} />
          <Route path="/robots" element={<Chunk><Robots /></Chunk>} />
          <Route path="/robots/:id" element={staffOnly(<Chunk><RobotDetail /></Chunk>)} />
          <Route path="/inventory" element={<Navigate to="/admin/equipment?tab=consumables" replace />} />
          <Route path="/admin/alerts" element={staffOnly(<Alerts />)} />
          <Route path="/admin/incidents" element={staffOnly(<Incidents />)} />
          <Route path="/admin/reliability" element={staffOnly(<Chunk><Reliability /></Chunk>)} />
          <Route path="/admin/reports" element={staffOnly(<Chunk><Reports /></Chunk>)} />
          <Route path="/admin/operations" element={staffOnly(<Chunk><Operations /></Chunk>)} />
          <Route path="/admin/system" element={staffOnly(<Chunk><SystemAnalytics /></Chunk>)} />
          <Route path="/demo" element={staffOnly(<Simulation />)} />
          <Route path="/admin/users" element={staffOnly(<Users />)} />
          <Route path="/admin/experiments" element={staffOnly(<Experiments />)} />
          <Route path="/admin/settings" element={adminOnly(<Settings />)} />
          <Route path="/admin/emergency" element={adminOnly(<Emergency />)} />

          {/* Earlier addresses keep working. */}
          <Route path="/admin" element={<Navigate to="/" replace />} />
          <Route path="/me" element={<Navigate to="/" replace />} />
          <Route path="/admin/access-events" element={<Navigate to="/admin/access" replace />} />
          <Route path="/admin/assets" element={<Navigate to="/admin/equipment" replace />} />
          <Route path="/login" element={<AfterSignIn />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </Layout>
    </LiveProvider>
  )
}

/** Right after sign-in the signed-in routes render while the URL is still /login: go to the ?next=
 *  deep link, the Command Center on its own port, or else the /welcome story. */
function AfterSignIn() {
  const next = new URLSearchParams(useLocation().search).get('next')
  const home = ['8080', '8443'].includes(window.location.port) ? '/command' : '/welcome'
  const ok = next && next.startsWith('/') && !next.startsWith('//')
  return <Navigate to={home === '/welcome' && ok ? `/welcome?next=${encodeURIComponent(next!)}` : ok ? next! : home} replace />
}

/** The evacuation alarm and the administrator's emergency message belong on EVERY signed-in screen, also the
 *  full-screen ones outside the portal frame (2026-10-20: /welcome - where every sign-in lands - /monitor, /wall and
 *  /report showed neither; e2e/emergency_message.mjs timed out). After the page in the DOM: on top at equal z-index. */
function SafetyLayer() {
  return <><HazardAlarm /><EmergencyMessage /></>
}
