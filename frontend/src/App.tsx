import { lazy, ReactNode, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import { isAdmin, isStaff, useAuth } from './lib/auth'
import { LiveProvider } from './lib/live'

import Login from './pages/Login'
import StudentDashboard from './pages/dashboards/StudentDashboard'
import StaffDashboard from './pages/dashboards/StaffDashboard'
import AdminDashboard from './pages/dashboards/AdminDashboard'
import Labs from './pages/Labs'
import LabDetail from './pages/LabDetail'
import Book from './pages/Book'
import MyBookings from './pages/MyBookings'
import Reservations from './pages/Reservations'
import BookingDetail from './pages/BookingDetail'
import BookingQr from './pages/BookingQr'
import SessionDetail from './pages/SessionDetail'
import Simulation from './pages/Simulation'
import AccessMonitor from './pages/AccessMonitor'
import Devices from './pages/Devices'
import Equipment from './pages/Equipment'
import AssetDetail from './pages/AssetDetail'
import Alerts from './pages/Alerts'
import Users from './pages/Users'
import Settings from './pages/Settings'
import ReportIssue from './pages/issues/ReportIssue'
import IssueList from './pages/issues/IssueList'
import IssueDetail from './pages/issues/IssueDetail'
import Notifications from './pages/Notifications'
import Profile from './pages/Profile'

// Charts pull in Recharts; load them only when a chart page is opened.
const Reports = lazy(() => import('./pages/Reports'))

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

  return (
    <LiveProvider>
      <Layout>
        <Routes>
          <Route path="/" element={home} />
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
          <Route path="/profile" element={<Profile />} />

          <Route path="/admin/bookings" element={staffOnly(<Reservations />)} />
          <Route path="/admin/access" element={staffOnly(<AccessMonitor />)} />
          <Route path="/admin/devices" element={staffOnly(<Devices />)} />
          <Route path="/admin/equipment" element={staffOnly(<Equipment />)} />
          <Route path="/admin/alerts" element={staffOnly(<Alerts />)} />
          <Route path="/admin/reports" element={staffOnly(<Chunk><Reports /></Chunk>)} />
          <Route path="/demo" element={staffOnly(<Simulation />)} />
          <Route path="/admin/users" element={adminOnly(<Users />)} />
          <Route path="/admin/settings" element={adminOnly(<Settings />)} />

          {/* Earlier addresses keep working. */}
          <Route path="/admin" element={<Navigate to="/" replace />} />
          <Route path="/me" element={<Navigate to="/" replace />} />
          <Route path="/admin/access-events" element={<Navigate to="/admin/access" replace />} />
          <Route path="/admin/assets" element={<Navigate to="/admin/equipment" replace />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </LiveProvider>
  )
}
