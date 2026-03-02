import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import Login from './components/Login'
import ProtectedRoute from './components/ProtectedRoute'
import InactivityTimer from './components/InactivityTimer'
import Dashboard from './components/Dashboard'
import CallList from './components/CallList'
import CallDetail from './components/CallDetail'
import AudioUpload from './components/AudioUpload'
import CallDialer from './components/CallDialer'
import UserManagement from './components/UserManagement'
import TeamManagement from './components/TeamManagement'
import AuditLog from './components/AuditLog'
import Reports from './components/Reports'

function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const roleColors = {
    admin: 'bg-purple-200 text-purple-800',
    supervisor: 'bg-blue-200 text-blue-800',
    worker: 'bg-green-200 text-green-800',
  }

  return (
    <nav className="bg-indigo-700 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/" className="text-xl font-bold tracking-tight">Call Monitor</Link>
          <div className="flex gap-6 text-sm font-medium">
            <Link to="/" className="hover:text-indigo-200">Dashboard</Link>
            <Link to="/calls" className="hover:text-indigo-200">Calls</Link>
            <Link to="/upload" className="hover:text-indigo-200">Upload</Link>
            <Link to="/call" className="hover:text-indigo-200">Call</Link>
            <Link to="/reports" className="hover:text-indigo-200">Reports</Link>
            {user.role === 'admin' && (
              <>
                <Link to="/users" className="hover:text-indigo-200">Users</Link>
                <Link to="/teams" className="hover:text-indigo-200">Teams</Link>
                <Link to="/audit-log" className="hover:text-indigo-200">Audit Log</Link>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span>{user.name}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${roleColors[user.role]}`}>
            {user.role}
          </span>
          <button onClick={handleLogout} className="text-indigo-200 hover:text-white ml-2">
            Logout
          </button>
        </div>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <InactivityTimer />

      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/calls" element={<ProtectedRoute><CallList /></ProtectedRoute>} />
          <Route path="/calls/:id" element={<ProtectedRoute><CallDetail /></ProtectedRoute>} />
          <Route path="/upload" element={<ProtectedRoute><AudioUpload /></ProtectedRoute>} />
          <Route path="/call" element={<ProtectedRoute><CallDialer /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute roles={['admin']}><UserManagement /></ProtectedRoute>} />
          <Route path="/teams" element={<ProtectedRoute roles={['admin']}><TeamManagement /></ProtectedRoute>} />
          <Route path="/audit-log" element={<ProtectedRoute roles={['admin']}><AuditLog /></ProtectedRoute>} />
        </Routes>
      </main>
    </div>
  )
}
