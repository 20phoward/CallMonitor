import { useState, useEffect } from 'react'
import { fetchTeams, createTeam } from '../api/client'

export default function TeamManagement() {
  const [teams, setTeams] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const loadTeams = () => {
    fetchTeams()
      .then((res) => setTeams(res.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadTeams() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await createTeam({ name })
      setName('')
      setShowForm(false)
      loadTeams()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create team')
    }
  }

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

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {teams.map((t) => (
          <div key={t.id} className="bg-white rounded-lg shadow-sm p-4">
            <h3 className="font-semibold">{t.name}</h3>
            <p className="text-sm text-gray-500">Created {new Date(t.created_at).toLocaleDateString()}</p>
          </div>
        ))}
        {teams.length === 0 && <p className="text-gray-500 col-span-full">No teams yet.</p>}
      </div>
    </div>
  )
}
