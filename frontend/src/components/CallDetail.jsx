import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchCallDetail, fetchCallStatus, deleteCall, audioUrl } from '../api/client'
import TonalityChart from './TonalityChart'
import ScoreCard from './ScoreCard'
import ReviewPanel from './ReviewPanel'
import { useAuth } from '../contexts/AuthContext'

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function CallDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [call, setCall] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { user } = useAuth()

  useEffect(() => {
    let interval
    const load = async () => {
      try {
        const data = await fetchCallDetail(id)
        setCall(data)
        setLoading(false)
        // Poll while processing
        if (['pending', 'processing', 'connecting', 'in_progress'].includes(data.status)) {
          interval = setInterval(async () => {
            const status = await fetchCallStatus(id)
            if (status.status !== data.status) {
              const updated = await fetchCallDetail(id)
              setCall(updated)
              if (updated.status === 'completed' || updated.status === 'failed') {
                clearInterval(interval)
              }
            }
          }, 3000)
        }
      } catch (e) {
        setError(e.message)
        setLoading(false)
      }
    }
    load()
    return () => clearInterval(interval)
  }, [id])

  const handleDelete = async () => {
    if (!confirm('Delete this call?')) return
    await deleteCall(id)
    navigate('/calls')
  }

  if (loading) return <p className="text-gray-500">Loading...</p>
  if (error) return <p className="text-red-600">Error: {error}</p>
  if (!call) return <p className="text-red-600">Call not found</p>

  const statusColors = {
    pending: 'text-yellow-600',
    connecting: 'text-orange-600',
    in_progress: 'text-blue-600',
    processing: 'text-blue-600',
    completed: 'text-green-600',
    failed: 'text-red-600',
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{call.title}</h1>
          <p className="text-sm text-gray-500">
            {new Date(call.date).toLocaleString()} &middot;{' '}
            <span className={statusColors[call.status]}>{call.status}</span>
            {call.duration && ` \u00b7 ${formatTime(call.duration)}`}
            {call.source_type === 'twilio' && (
              <>
                {' · '}
                <span className="bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded text-xs">
                  {call.call_direction || 'call'}
                </span>
                {call.connection_mode && (
                  <span className="bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded text-xs ml-1">
                    {call.connection_mode}
                  </span>
                )}
              </>
            )}
          </p>
        </div>
        <button onClick={handleDelete} className="text-red-500 hover:text-red-700 text-sm border border-red-300 px-3 py-1 rounded">
          Delete
        </button>
      </div>

      {call.error_message && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded mb-6 text-sm">
          {call.error_message}
        </div>
      )}

      {['pending', 'processing', 'connecting', 'in_progress'].includes(call.status) && (
        <div className="bg-blue-50 border border-blue-200 text-blue-700 p-4 rounded mb-6 flex items-center gap-3">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          Processing... This may take a minute.
        </div>
      )}

      {/* Audio Player */}
      {call.audio_filename && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-2">Audio</h2>
          <audio controls className="w-full" src={audioUrl(call.audio_filename)} />
        </div>
      )}

      {/* Tonality Summary */}
      {call.tonality && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Tonality Analysis</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500 mb-1">Overall Sentiment</p>
              <p className="text-xl font-bold capitalize">{call.tonality.overall_sentiment}</p>
              <p className="text-sm text-gray-500">
                Score: {call.tonality.overall_score?.toFixed(2)}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500 mb-1">Tone</p>
              <div className="flex flex-wrap gap-2">
                {(call.tonality.tone_labels || []).map(t => (
                  <span key={t} className="bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded text-xs capitalize">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {call.tonality.summary && (
            <div className="bg-white rounded-lg shadow p-4 mb-4">
              <p className="text-sm text-gray-500 mb-1">Summary</p>
              <p className="text-sm">{call.tonality.summary}</p>
            </div>
          )}

          {/* Sentiment timeline chart */}
          {call.tonality.sentiment_scores?.length > 0 && (
            <TonalityChart data={call.tonality.sentiment_scores} keyMoments={call.tonality.key_moments} />
          )}

          {/* Key moments */}
          {call.tonality.key_moments?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-4 mt-4">
              <p className="text-sm text-gray-500 mb-2">Key Moments</p>
              <ul className="space-y-2">
                {call.tonality.key_moments.map((m, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="font-mono text-gray-400 whitespace-nowrap">{formatTime(m.time)}</span>
                    <span className="bg-yellow-100 text-yellow-800 px-1.5 py-0.5 rounded text-xs">{m.emotion}</span>
                    <span>{m.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Quality Score */}
      {call.score && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Quality Score</h2>
          <div className={`grid grid-cols-1 ${user?.role !== 'worker' ? 'md:grid-cols-2' : ''} gap-4`}>
            <ScoreCard score={call.score} review={call.review} />
            {user?.role !== 'worker' && (
              <ReviewPanel
                callId={call.id}
                score={call.score}
                review={call.review}
                onReviewSubmitted={() => fetchCallDetail(id).then(setCall)}
              />
            )}
          </div>
        </div>
      )}

      {/* Transcript */}
      {call.transcript && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Transcript</h2>
          <div className="bg-white rounded-lg shadow p-4 max-h-96 overflow-y-auto space-y-3">
            {call.transcript.segments?.length > 0 ? (
              call.transcript.segments.map((seg, i) => {
                const prevSpeaker = i > 0 ? call.transcript.segments[i - 1].speaker : null
                const showSpeaker = seg.speaker && seg.speaker !== prevSpeaker
                const firstSpeaker = call.transcript.segments.find(s => s.speaker)?.speaker
                const isFirstSpeaker = seg.speaker === firstSpeaker
                return (
                  <div key={i} className="flex gap-3 text-sm">
                    <span className="font-mono text-gray-400 whitespace-nowrap text-xs mt-0.5">
                      {formatTime(seg.start)}
                    </span>
                    <div>
                      {showSpeaker && (
                        <span className={`text-xs font-semibold mr-1 ${
                          isFirstSpeaker ? 'text-indigo-600' : 'text-emerald-600'
                        }`}>
                          {seg.speaker}:
                        </span>
                      )}
                      <span>{seg.text}</span>
                    </div>
                  </div>
                )
              })
            ) : (
              <p className="text-sm whitespace-pre-wrap">{call.transcript.full_text}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
