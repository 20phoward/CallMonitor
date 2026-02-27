function ScoreBar({ label, score, override }) {
  const effective = override ?? score
  const pct = effective != null ? (effective / 10) * 100 : 0
  const color =
    effective >= 8 ? 'bg-green-500' :
    effective >= 6 ? 'bg-yellow-500' :
    effective >= 4 ? 'bg-orange-500' : 'bg-red-500'

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-gray-600">
          {effective != null ? effective.toFixed(1) : 'N/A'}
          {override != null && <span className="text-indigo-600 text-xs ml-1">(overridden)</span>}
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function ScoreCard({ score, review }) {
  if (!score) return null

  const overrides = review?.score_overrides || {}
  const categories = [
    { key: 'empathy', label: 'Empathy & Compassion' },
    { key: 'professionalism', label: 'Professionalism' },
    { key: 'resolution', label: 'Resolution & Follow-through' },
    { key: 'compliance', label: 'Compliance & Safety' },
  ]

  const effectiveOverall = categories.reduce((sum, c) => {
    return sum + (overrides[c.key] ?? score[c.key] ?? 0)
  }, 0) / 4

  const ratingColor =
    effectiveOverall >= 8 ? 'text-green-600' :
    effectiveOverall >= 6 ? 'text-yellow-600' :
    effectiveOverall >= 4 ? 'text-orange-600' : 'text-red-600'

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">Quality Score</p>
        <p className={`text-2xl font-bold ${ratingColor}`}>
          {effectiveOverall.toFixed(1)}<span className="text-sm text-gray-400">/10</span>
        </p>
      </div>
      <div className="space-y-3">
        {categories.map(c => (
          <ScoreBar
            key={c.key}
            label={c.label}
            score={score[c.key]}
            override={overrides[c.key]}
          />
        ))}
      </div>
      {score.category_details && (
        <details className="mt-4">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
            View AI reasoning
          </summary>
          <div className="mt-2 space-y-2">
            {categories.map(c => (
              score.category_details[c.key]?.reasoning && (
                <div key={c.key} className="text-xs text-gray-600">
                  <span className="font-medium">{c.label}:</span>{' '}
                  {score.category_details[c.key].reasoning}
                </div>
              )
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
