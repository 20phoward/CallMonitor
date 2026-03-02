import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { fetchTrends, fetchTeamComparison, fetchCompliance, exportCsvUrl, exportPdfUrl } from '../api/client'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'

const PRESETS = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
]

function formatDate(d) {
  return d.toISOString().split('T')[0]
}

export default function Reports() {
  const { user } = useAuth()
  const [startDate, setStartDate] = useState(() => formatDate(new Date(Date.now() - 90 * 86400000)))
  const [endDate, setEndDate] = useState(() => formatDate(new Date()))
  const [period, setPeriod] = useState('weekly')
  const [trends, setTrends] = useState(null)
  const [teamData, setTeamData] = useState(null)
  const [compliance, setCompliance] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = { start_date: startDate, end_date: endDate }
      const trendsData = await fetchTrends({ ...params, period })
      setTrends(trendsData)

      if (user.role !== 'worker') {
        const teamComp = await fetchTeamComparison(params)
        setTeamData(teamComp)
      }

      const comp = await fetchCompliance(params)
      setCompliance(comp)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load reports')
    } finally {
      setLoading(false)
    }
  }, [startDate, endDate, period, user.role])

  useEffect(() => { loadData() }, [loadData])

  const applyPreset = (days) => {
    setEndDate(formatDate(new Date()))
    setStartDate(formatDate(new Date(Date.now() - days * 86400000)))
  }

  const handleExport = (format) => {
    const params = { report_type: 'calls', start_date: startDate, end_date: endDate }
    const token = localStorage.getItem('access_token')
    const url = format === 'csv' ? exportCsvUrl(params) : exportPdfUrl(params)
    // Use fetch with auth header to download
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(resp => resp.blob())
      .then(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `report-calls-${endDate}.${format}`
        a.click()
        URL.revokeObjectURL(a.href)
      })
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading reports...</div>
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Reports & Analytics</h1>
        <div className="flex gap-2">
          <button onClick={() => handleExport('csv')}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50">Export CSV</button>
          <button onClick={() => handleExport('pdf')}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50">Export PDF</button>
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-600 p-3 rounded text-sm">{error}</div>}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 flex flex-wrap items-center gap-4">
        <div className="flex gap-1">
          {PRESETS.map(p => (
            <button key={p.days} onClick={() => applyPreset(p.days)}
              className="px-3 py-1 text-xs border rounded-full hover:bg-indigo-50 hover:border-indigo-300">
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            className="border rounded px-2 py-1" />
          <span className="text-gray-400">to</span>
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            className="border rounded px-2 py-1" />
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label className="text-gray-600">Period:</label>
          <select value={period} onChange={e => setPeriod(e.target.value)}
            className="border rounded px-2 py-1">
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <button onClick={loadData}
          className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">
          Apply
        </button>
      </div>

      {/* Trends Chart */}
      {trends && trends.buckets.some(b => b.call_count > 0) && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Performance Trends</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends.buckets.filter(b => b.call_count > 0)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="start_date" tick={{ fontSize: 11 }}
                tickFormatter={v => v.slice(5)} />
              <YAxis yAxisId="rating" domain={[0, 10]} />
              <YAxis yAxisId="sentiment" orientation="right" domain={[-1, 1]} />
              <Tooltip />
              <Legend />
              <Line yAxisId="rating" type="monotone" dataKey="avg_rating"
                stroke="#6366f1" strokeWidth={2} name="Avg Rating" dot />
              <Line yAxisId="sentiment" type="monotone" dataKey="avg_sentiment"
                stroke="#10b981" strokeWidth={2} name="Avg Sentiment" dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Team/Worker Comparison Charts */}
      {teamData && user.role === 'admin' && teamData.teams.length > 0 && (
        <>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">Avg Rating by Team</h2>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={teamData.teams}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="team_name" />
                <YAxis domain={[0, 10]} />
                <Tooltip />
                <Bar dataKey="avg_rating" fill="#6366f1" name="Avg Rating" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Call Volume by Team</h2>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={teamData.teams}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="team_name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="call_count" fill="#a5b4fc" name="Call Count" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Flagged Calls by Team</h2>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={teamData.teams}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="team_name" />
                  <YAxis domain={[0, 100]} unit="%" />
                  <Tooltip />
                  <Bar dataKey="flagged_pct" fill="#ef4444" name="Flagged %" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
      {teamData && user.role === 'supervisor' && teamData.workers && teamData.workers.length > 0 && (
        <>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">Avg Rating by Worker</h2>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={teamData.workers}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="worker_name" />
                <YAxis domain={[0, 10]} />
                <Tooltip />
                <Bar dataKey="avg_rating" fill="#6366f1" name="Avg Rating" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Call Volume by Worker</h2>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={teamData.workers}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="worker_name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="call_count" fill="#a5b4fc" name="Call Count" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Flagged Calls by Worker</h2>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={teamData.workers}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="worker_name" />
                  <YAxis domain={[0, 100]} unit="%" />
                  <Tooltip />
                  <Bar dataKey="flagged_pct" fill="#ef4444" name="Flagged %" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      {/* Compliance Summary */}
      {compliance && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Compliance</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-indigo-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-indigo-700">
                {compliance.score_compliance.passing_pct}%
              </div>
              <div className="text-xs text-gray-600 mt-1">Score Compliance</div>
              <div className="text-xs text-gray-400">
                {compliance.score_compliance.passing_calls}/{compliance.score_compliance.total_calls} calls
              </div>
            </div>
            <div className="bg-green-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-green-700">
                {compliance.review_completion.review_pct}%
              </div>
              <div className="text-xs text-gray-600 mt-1">Review Completion</div>
              <div className="text-xs text-gray-400">
                {compliance.review_completion.reviewed_count}/{compliance.review_completion.total_completed_calls} calls
              </div>
            </div>
            <div className="bg-yellow-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-yellow-700">
                {compliance.review_completion.avg_days_to_review ?? '—'}
              </div>
              <div className="text-xs text-gray-600 mt-1">Avg Days to Review</div>
            </div>
            <div className="bg-red-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-red-700">
                {compliance.review_completion.unreviewed_backlog}
              </div>
              <div className="text-xs text-gray-600 mt-1">Unreviewed Backlog</div>
            </div>
          </div>

          {compliance.score_compliance.failing_workers.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Workers Below Threshold ({compliance.score_compliance.threshold})
              </h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="py-2">Worker</th>
                    <th className="py-2">Avg Score</th>
                    <th className="py-2">Calls Below</th>
                  </tr>
                </thead>
                <tbody>
                  {compliance.score_compliance.failing_workers.map(w => (
                    <tr key={w.worker_id} className="border-b">
                      <td className="py-2">{w.name}</td>
                      <td className="py-2 text-red-600">{w.avg_score}</td>
                      <td className="py-2">{w.calls_below}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
