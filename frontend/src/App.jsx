import { Routes, Route, Link } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import CallList from './components/CallList'
import CallDetail from './components/CallDetail'
import AudioUpload from './components/AudioUpload'

export default function App() {
  return (
    <div className="min-h-screen">
      <nav className="bg-indigo-700 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-8">
          <Link to="/" className="text-xl font-bold tracking-tight">
            Call Monitor
          </Link>
          <div className="flex gap-6 text-sm font-medium">
            <Link to="/" className="hover:text-indigo-200">Dashboard</Link>
            <Link to="/calls" className="hover:text-indigo-200">Calls</Link>
            <Link to="/upload" className="hover:text-indigo-200">Upload</Link>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/calls" element={<CallList />} />
          <Route path="/calls/:id" element={<CallDetail />} />
          <Route path="/upload" element={<AudioUpload />} />
        </Routes>
      </main>
    </div>
  )
}
