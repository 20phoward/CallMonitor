import { useState, useEffect } from 'react'
import { fetchUsers, register, fetchTeams, updateUser, deleteUser } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export default function UserManagement() {
  const [users, setUsers] = useState([])
  const [teams, setTeams] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({ email: '', password: '', name: '', role: 'worker', team_id: '' })
  const [error, setError] = useState('')
  const { user: currentUser } = useAuth()

  const loadData = () => {
    Promise.all([fetchUsers(), fetchTeams()])
      .then(([usersRes, teamsRes]) => {
        setUsers(usersRes.data)
        setTeams(teamsRes.data)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const data = { ...formData }
      if (data.team_id) data.team_id = parseInt(data.team_id)
      else delete data.team_id
      await register(data)
      setFormData({ email: '', password: '', name: '', role: 'worker', team_id: '' })
      setShowForm(false)
      loadData()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user')
    }
  }

  const handleRoleChange = async (userId, newRole) => {
    try {
      await updateUser(userId, { role: newRole })
      loadData()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update role')
    }
  }

  const handleTeamChange = async (userId, teamId) => {
    try {
      await updateUser(userId, { team_id: teamId || null })
      loadData()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update team')
    }
  }

  const handleDelete = async (userId, userName) => {
    if (!confirm(`Remove ${userName}? They will no longer be able to log in.`)) return
    try {
      await deleteUser(userId)
      loadData()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to remove user')
    }
  }

  const roleColor = {
    admin: 'text-purple-600 bg-purple-50',
    supervisor: 'text-blue-600 bg-blue-50',
    worker: 'text-green-600 bg-green-50',
  }

  const teamName = (teamId) => {
    const t = teams.find(t => t.id === teamId)
    return t ? t.name : ''
  }

  if (loading) return <div className="text-center py-8">Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">User Management</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 transition text-sm">
          {showForm ? 'Cancel' : 'New User'}
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6 max-w-lg">
          {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}
          <form onSubmit={handleCreate} className="space-y-4">
            <input type="text" placeholder="Full Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            <input type="email" placeholder="Email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            <input type="password" placeholder="Password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            <p className="text-xs text-gray-500">Min 8 chars, uppercase, lowercase, and number</p>
            <div className="flex space-x-4">
              <select value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })} className="border border-gray-300 rounded-md px-3 py-2">
                <option value="worker">Worker</option>
                <option value="supervisor">Supervisor</option>
                <option value="admin">Admin</option>
              </select>
              <select value={formData.team_id} onChange={(e) => setFormData({ ...formData, team_id: e.target.value })} className="border border-gray-300 rounded-md px-3 py-2">
                <option value="">No Team</option>
                {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <button type="submit" className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 text-sm">Create User</button>
          </form>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Team</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 font-medium">{u.name}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{u.email}</td>
                <td className="px-6 py-4">
                  {u.id === currentUser?.id ? (
                    <span className={`px-2 py-1 rounded text-xs font-medium ${roleColor[u.role]}`}>
                      {u.role} (you)
                    </span>
                  ) : (
                    <select value={u.role} onChange={(e) => handleRoleChange(u.id, e.target.value)} className={`px-2 py-1 rounded text-xs font-medium border-0 cursor-pointer ${roleColor[u.role]}`}>
                      <option value="admin">admin</option>
                      <option value="supervisor">supervisor</option>
                      <option value="worker">worker</option>
                    </select>
                  )}
                </td>
                <td className="px-6 py-4">
                  {u.id === currentUser?.id ? (
                    <span className="text-sm text-gray-500">{teamName(u.team_id) || '—'}</span>
                  ) : (
                    <select value={u.team_id || ''} onChange={(e) => handleTeamChange(u.id, e.target.value ? parseInt(e.target.value) : null)} className="text-sm border border-gray-200 rounded px-2 py-1 cursor-pointer">
                      <option value="">No Team</option>
                      {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  )}
                </td>
                <td className="px-6 py-4">
                  {u.id !== currentUser?.id && (
                    <button onClick={() => handleDelete(u.id, u.name)} className="text-red-600 hover:text-red-800 text-sm">
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
