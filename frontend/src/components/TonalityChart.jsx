import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

function formatTick(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white shadow rounded px-3 py-2 text-xs border">
      <p className="font-medium">{formatTick(d.time)}</p>
      <p>Score: {d.score.toFixed(2)}</p>
      <p className="capitalize">{d.label}</p>
    </div>
  )
}

export default function TonalityChart({ data, keyMoments }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-sm text-gray-500 mb-3">Sentiment Over Time</p>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="time" tickFormatter={formatTick} tick={{ fontSize: 11 }} />
          <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke="#999" strokeDasharray="3 3" />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
          {(keyMoments || []).map((m, i) => (
            <ReferenceLine key={i} x={m.time} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: m.emotion, fontSize: 10, fill: '#d97706' }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
