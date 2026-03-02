import { useState, useEffect } from 'react'
import { fetchTeams, createTeam, fetchUsers, updateUser } from '../api/client'

const roleColor = {
  admin: 'text-purple-600 bg-purple-50',
  supervisor: 'text-blue-600 bg-blue-50',
  worker: 'text-green-600 bg-green-50',
}

export default function TeamManagement() {
  const [teams, setTeams] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const loadData = () => {
    Promise.all([fetchTeams(), fetchUsers()])
      .then(([teamsRes, usersRes]) => {
        setTeams(teamsRes.data)
        setUsers(usersRes.data)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await createTeam({ name })
      setName('')
      setShowForm(false)
      loadData()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create team')
    }
  }

  const handleMoveUser = async (userId, newTeamId) => {
    try {
      await updateUser(userId, { team_id: newTeamId || null })
      loadData()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to move user')
    }
  }

  const membersOf = (teamId) => users.filter(u => u.team_id === teamId)
  const unassigned = users.filter(u => !u.team_id)

  if (loading) return <div className="text-center py-8">Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Team Management</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 transition text-sm">
          {showForm ? 'Cancel' : 'New Team'}
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6 max-w-lg">
          {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}
          <form onSubmit={handleCreate} className="flex gap-4">
            <input type="text" placeholder="Team Name" value={name} onChange={(e) => setName(e.target.value)} className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            <button type="submit" className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 text-sm">Create</button>
          </form>
        </div>
      )}

      <div className="space-y-6">
        {teams.map((t) => {
          const members = membersOf(t.id)
          return (
            <div key={t.id} className="bg-white rounded-lg shadow-sm overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-lg">{t.name}</h3>
                  <p className="text-xs text-gray-500">{members.length} member{members.length !== 1 ? 's' : ''}</p>
                </div>
              </div>
              {members.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 uppercase border-b">
                      <th className="px-6 py-2">Name</th>
                      <th className="px-6 py-2">Role</th>
                      <th className="px-6 py-2">Move to</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {members.map(u => (
                      <tr key={u.id} className="hover:bg-gray-50">
                        <td className="px-6 py-3 font-medium">{u.name}</td>
                        <td className="px-6 py-3">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${roleColor[u.role]}`}>{u.role}</span>
                        </td>
                        <td className="px-6 py-3">
                          <select value={u.team_id || ''} onChange={(e) => handleMoveUser(u.id, e.target.value ? parseInt(e.target.value) : null)} className="text-sm border border-gray-200 rounded px-2 py-1 cursor-pointer">
                            <option value="">Unassigned</option>
                            {teams.map(team => <option key={team.id} value={team.id}>{team.name}</option>)}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="px-6 py-4 text-sm text-gray-400">No members yet</p>
              )}
            </div>
          )
        })}

        {/* Unassigned users */}
        {unassigned.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <div className="px-6 py-4 bg-yellow-50 border-b">
              <h3 className="font-semibold text-lg text-yellow-800">Unassigned</h3>
              <p className="text-xs text-yellow-600">{unassigned.length} user{unassigned.length !== 1 ? 's' : ''} not on a team</p>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 uppercase border-b">
                  <th className="px-6 py-2">Name</th>
                  <th className="px-6 py-2">Role</th>
                  <th className="px-6 py-2">Assign to</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {unassigned.map(u => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-6 py-3 font-medium">{u.name}</td>
                    <td className="px-6 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${roleColor[u.role]}`}>{u.role}</span>
                    </td>
                    <td className="px-6 py-3">
                      <select value="" onChange={(e) => handleMoveUser(u.id, e.target.value ? parseInt(e.target.value) : null)} className="text-sm border border-gray-200 rounded px-2 py-1 cursor-pointer">
                        <option value="">Select team...</option>
                        {teams.map(team => <option key={team.id} value={team.id}>{team.name}</option>)}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {teams.length === 0 && <p className="text-gray-500">No teams yet. Create one to get started.</p>}
      </div>
    </div>
  )
}
