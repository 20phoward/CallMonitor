import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchDashboardStats } from '../api/client'

function SentimentBadge({ sentiment, score }) {
  const colors = {
    positive: 'bg-green-100 text-green-800',
    negative: 'bg-red-100 text-red-800',
    neutral: 'bg-gray-100 text-gray-800',
    mixed: 'bg-yellow-100 text-yellow-800',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${colors[sentiment] || colors.neutral}`}>
      {sentiment} {score != null && `(${score > 0 ? '+' : ''}${score.toFixed(2)})`}
    </span>
  )
}

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

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchDashboardStats().then(setStats).catch(e => setError(e.message))
  }, [])

  if (error) return <p className="text-red-600">Error: {error}</p>
  if (!stats) return <p className="text-gray-500">Loading...</p>

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg shadow p-5">
          <p className="text-sm text-gray-500">Total Calls</p>
          <p className="text-3xl font-bold">{stats.total_calls}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-5">
          <p className="text-sm text-gray-500">Completed</p>
          <p className="text-3xl font-bold">{stats.completed_calls}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-5">
          <p className="text-sm text-gray-500">Avg Sentiment</p>
          <p className="text-3xl font-bold">
            {stats.avg_sentiment_score != null ? stats.avg_sentiment_score.toFixed(2) : 'N/A'}
          </p>
        </div>
      </div>

      {/* Recent calls */}
      <h2 className="text-lg font-semibold mb-3">Recent Calls</h2>
      {stats.recent_calls.length === 0 ? (
        <p className="text-gray-500">No calls yet. <Link to="/upload" className="text-indigo-600 underline">Upload one</Link>.</p>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Sentiment</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_calls.map(c => (
                <tr key={c.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2">
                    <Link to={`/calls/${c.id}`} className="text-indigo-600 hover:underline">{c.title}</Link>
                  </td>
                  <td className="px-4 py-2">{new Date(c.date).toLocaleString()}</td>
                  <td className="px-4 py-2"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-2">
                    {c.overall_sentiment
                      ? <SentimentBadge sentiment={c.overall_sentiment} score={c.overall_score} />
                      : <span className="text-gray-400">-</span>}
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
