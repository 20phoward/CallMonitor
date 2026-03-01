import { useState } from 'react'
import { submitReview } from '../api/client'

const CATEGORIES = [
  { key: 'empathy', label: 'Empathy' },
  { key: 'professionalism', label: 'Professionalism' },
  { key: 'resolution', label: 'Resolution' },
  { key: 'compliance', label: 'Compliance' },
]

function ReviewStatusBadge({ status }) {
  const styles = {
    unreviewed: 'bg-gray-100 text-gray-800',
    approved: 'bg-green-100 text-green-800',
    flagged: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${styles[status] || styles.unreviewed}`}>
      {status}
    </span>
  )
}

export default function ReviewPanel({ callId, score, review, onReviewSubmitted }) {
  const [status, setStatus] = useState(review?.status || 'unreviewed')
  const [notes, setNotes] = useState(review?.notes || '')
  const [overrides, setOverrides] = useState(review?.score_overrides || {})
  const [editingScore, setEditingScore] = useState(null)
  const [saving, setSaving] = useState(false)

  const handleOverride = (key, value) => {
    const num = parseFloat(value)
    if (isNaN(num) || num < 0 || num > 10) return
    setOverrides(prev => ({ ...prev, [key]: Math.round(num * 10) / 10 }))
    setEditingScore(null)
  }

  const handleSubmit = async (newStatus) => {
    setSaving(true)
    try {
      const result = await submitReview(callId, {
        status: newStatus,
        score_overrides: Object.keys(overrides).length > 0 ? overrides : null,
        notes: notes || null,
      })
      setStatus(result.status)
      if (onReviewSubmitted) onReviewSubmitted(result)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">Supervisor Review</p>
        <ReviewStatusBadge status={status} />
      </div>

      {/* Score overrides */}
      {score && (
        <div className="mb-4">
          <p className="text-xs text-gray-500 mb-2">Click a score to override:</p>
          <div className="grid grid-cols-2 gap-2">
            {CATEGORIES.map(c => (
              <div key={c.key} className="flex items-center justify-between bg-gray-50 rounded px-2 py-1">
                <span className="text-xs">{c.label}</span>
                {editingScore === c.key ? (
                  <input
                    type="number"
                    min="0"
                    max="10"
                    step="0.5"
                    defaultValue={overrides[c.key] ?? score[c.key] ?? ''}
                    className="w-14 text-xs border rounded px-1 py-0.5"
                    autoFocus
                    onBlur={e => handleOverride(c.key, e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleOverride(c.key, e.target.value)}
                  />
                ) : (
                  <button
                    onClick={() => setEditingScore(c.key)}
                    className={`text-xs font-medium px-1 rounded hover:bg-gray-200 ${
                      overrides[c.key] != null ? 'text-indigo-600' : 'text-gray-700'
                    }`}
                  >
                    {(overrides[c.key] ?? score[c.key])?.toFixed(1) ?? 'N/A'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Notes */}
      <textarea
        value={notes}
        onChange={e => setNotes(e.target.value)}
        placeholder="Optional review notes..."
        className="w-full border rounded-lg p-2 text-sm mb-4 h-20 resize-none"
      />

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => handleSubmit('approved')}
          disabled={saving}
          className="flex-1 bg-green-600 text-white py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Approve'}
        </button>
        <button
          onClick={() => handleSubmit('flagged')}
          disabled={saving}
          className="flex-1 bg-red-600 text-white py-2 rounded-lg text-sm hover:bg-red-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Flag'}
        </button>
      </div>
    </div>
  )
}
