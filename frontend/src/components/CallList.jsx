import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchCalls, deleteCall } from '../api/client'

function StatusBadge({ status }) {
  const colors = {
    pending: 'bg-yellow-100 text-yellow-800',
    processing: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-gray-100'}`}>
      {status}
    </span>
  )
}

function formatDuration(seconds) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function ReviewStatusBadge({ status }) {
  const colors = {
    unreviewed: 'bg-gray-100 text-gray-800',
    approved: 'bg-green-100 text-green-800',
    flagged: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-gray-100'}`}>
      {status || 'unreviewed'}
    </span>
  )
}

function RatingBadge({ rating }) {
  if (rating == null) return <span className="text-gray-400">-</span>
  const color =
    rating >= 8 ? 'text-green-600' :
    rating >= 6 ? 'text-yellow-600' :
    rating >= 4 ? 'text-orange-600' : 'text-red-600'
  return <span className={`font-medium ${color}`}>{rating.toFixed(1)}</span>
}

export default function CallList() {
  const [calls, setCalls] = useState([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    fetchCalls().then(setCalls).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id) => {
    if (!confirm('Delete this call?')) return
    await deleteCall(id)
    load()
  }

  if (loading) return <p className="text-gray-500">Loading...</p>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">All Calls</h1>
        <Link to="/upload" className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700">
          Upload New
        </Link>
      </div>

      {calls.length === 0 ? (
        <p className="text-gray-500">No calls yet.</p>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2">Duration</th>
                <th className="px-4 py-2">Source</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Sentiment</th>
                <th className="px-4 py-2">Rating</th>
                <th className="px-4 py-2">Review</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {calls.map(c => (
                <tr key={c.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2">
                    <Link to={`/calls/${c.id}`} className="text-indigo-600 hover:underline">{c.title}</Link>
                  </td>
                  <td className="px-4 py-2">{new Date(c.date).toLocaleString()}</td>
                  <td className="px-4 py-2">{formatDuration(c.duration)}</td>
                  <td className="px-4 py-2 capitalize">{c.source_type}</td>
                  <td className="px-4 py-2"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-2">
                    {c.overall_sentiment ? (
                      <span className={
                        c.overall_score > 0.2 ? 'text-green-600' :
                        c.overall_score < -0.2 ? 'text-red-600' : 'text-gray-600'
                      }>
                        {c.overall_sentiment} ({c.overall_score?.toFixed(2)})
                      </span>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-2"><RatingBadge rating={c.overall_rating} /></td>
                  <td className="px-4 py-2"><ReviewStatusBadge status={c.review_status} /></td>
                  <td className="px-4 py-2">
                    <button onClick={() => handleDelete(c.id)} className="text-red-500 hover:text-red-700 text-xs">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
