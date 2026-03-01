import { useState, useEffect } from 'react'
import { fetchAuditLog } from '../api/client'

export default function AuditLog() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const limit = 50

  const loadLogs = (newOffset) => {
    setLoading(true)
    fetchAuditLog({ limit, offset: newOffset })
      .then((res) => {
        setLogs(res.data)
        setOffset(newOffset)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadLogs(0) }, [])

  const actionColors = {
    login: 'bg-green-100 text-green-800',
    logout: 'bg-gray-100 text-gray-800',
    view_call: 'bg-blue-100 text-blue-800',
    view_transcript: 'bg-blue-100 text-blue-800',
    upload_call: 'bg-indigo-100 text-indigo-800',
    delete_call: 'bg-red-100 text-red-800',
    submit_review: 'bg-yellow-100 text-yellow-800',
    update_review: 'bg-yellow-100 text-yellow-800',
    create_user: 'bg-purple-100 text-purple-800',
    update_role: 'bg-purple-100 text-purple-800',
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Audit Log</h1>

      {loading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resource</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-500">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm font-medium">{log.user_name || 'Unknown'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${actionColors[log.action] || 'bg-gray-100'}`}>
                        {log.action.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {log.resource_type && `${log.resource_type} #${log.resource_id}`}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400 font-mono">{log.ip_address}</td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr><td colSpan="5" className="px-4 py-8 text-center text-gray-500">No audit log entries.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between mt-4">
            <button
              onClick={() => loadLogs(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="text-sm text-indigo-600 hover:underline disabled:text-gray-400 disabled:no-underline"
            >
              Previous
            </button>
            <button
              onClick={() => loadLogs(offset + limit)}
              disabled={logs.length < limit}
              className="text-sm text-indigo-600 hover:underline disabled:text-gray-400 disabled:no-underline"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
