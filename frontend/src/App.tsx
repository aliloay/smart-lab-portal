import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import { isStaff, useAuth } from './lib/auth'

import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Labs from './pages/Labs'
import LabDetail from './pages/LabDetail'
import Book from './pages/Book'
import Bookings from './pages/Bookings'
import BookingQr from './pages/BookingQr'
import AdminOverview from './pages/AdminOverview'
import AdminEvents from './pages/AdminEvents'
import AdminReports from './pages/AdminReports'
import { AdminAlerts, AdminAssets, AdminDevices, AdminUsers } from './pages/AdminTables'

export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="min-h-screen grid place-items-center">
      <Spinner label="Restoring session" />
    </div>
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  // Staff-only routes are gated here AND on the server. The client gate is
  // for usability; the server's is the one that matters.
  const staff = isStaff(user)

  return (
    <Layout>
      <Routes>
        {/*
          The home route is role-dependent.

          Giving an administrator the student dashboard - "your bookings",
          "book a laboratory" - is the same mistake as putting "New booking"
          in their sidebar: it answers a question they are not asking. A
          student wants to know when they next get in; staff and admins want
          to know what the building is doing right now.

          Every route still exists for every role. Only the landing page
          differs, and the server enforces the actual permissions regardless.
        */}
        <Route path="/" element={staff ? <AdminOverview /> : <Dashboard />} />
        <Route path="/me" element={<Dashboard />} />
        <Route path="/labs" element={<Labs />} />
        <Route path="/labs/:id" element={<LabDetail />} />
        <Route path="/book" element={<Book />} />
        <Route path="/bookings" element={<Bookings />} />
        <Route path="/bookings/:id/qr" element={<BookingQr />} />

        <Route path="/admin" element={staff ? <AdminOverview /> : <Navigate to="/" replace />} />
        <Route path="/admin/bookings" element={staff ? <Bookings all /> : <Navigate to="/" replace />} />
        <Route path="/admin/access-events" element={staff ? <AdminEvents /> : <Navigate to="/" replace />} />
        <Route path="/admin/users" element={staff ? <AdminUsers /> : <Navigate to="/" replace />} />
        <Route path="/admin/devices" element={staff ? <AdminDevices /> : <Navigate to="/" replace />} />
        <Route path="/admin/assets" element={staff ? <AdminAssets /> : <Navigate to="/" replace />} />
        <Route path="/admin/alerts" element={staff ? <AdminAlerts /> : <Navigate to="/" replace />} />
        <Route path="/admin/reports" element={staff ? <AdminReports /> : <Navigate to="/" replace />} />

        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}
