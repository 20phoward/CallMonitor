import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Device } from '@twilio/voice-sdk'
import { dialCall, getTwilioToken } from '../api/client'

function formatTimer(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export default function CallDialer() {
  const navigate = useNavigate()
  const [patientPhone, setPatientPhone] = useState('')
  const [workerPhone, setWorkerPhone] = useState('')
  const [title, setTitle] = useState('')
  const [patientName, setPatientName] = useState('')
  const [mode, setMode] = useState('browser')
  const [callState, setCallState] = useState('idle') // idle, connecting, active, ended
  const [callId, setCallId] = useState(null)
  const [error, setError] = useState('')
  const [timer, setTimer] = useState(0)

  const deviceRef = useRef(null)
  const connectionRef = useRef(null)
  const timerRef = useRef(null)

  const initDevice = useCallback(async () => {
    try {
      const { token } = await getTwilioToken()
      const device = new Device(token, {
        codecPreferences: ['opus', 'pcmu'],
        logLevel: 'warn',
      })
      device.on('error', (err) => {
        console.error('Twilio Device error:', err)
        setError(`Device error: ${err.message}`)
        setCallState('idle')
      })
      deviceRef.current = device
    } catch (err) {
      console.error('Failed to init Twilio Device:', err)
      setError('Failed to initialize calling. Check Twilio configuration.')
    }
  }, [])

  useEffect(() => {
    initDevice()
    return () => {
      if (deviceRef.current) {
        deviceRef.current.destroy()
      }
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [initDevice])

  const startTimer = () => {
    setTimer(0)
    timerRef.current = setInterval(() => {
      setTimer((t) => t + 1)
    }, 1000)
  }

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const handleDial = async () => {
    setError('')
    setCallState('connecting')

    try {
      const data = await dialCall({
        patient_phone: patientPhone,
        mode,
        worker_phone: mode === 'phone' ? workerPhone : undefined,
        title: title || `Call to ${patientPhone}`,
        patient_name: patientName || undefined,
      })
      setCallId(data.call_id)

      if (mode === 'browser') {
        if (!deviceRef.current) {
          throw new Error('Twilio Device not initialized')
        }
        const call = await deviceRef.current.connect({
          params: {
            To: patientPhone,
            callId: String(data.call_id),
          },
        })

        call.on('accept', () => {
          setCallState('active')
          startTimer()
        })

        call.on('disconnect', () => {
          setCallState('ended')
          stopTimer()
        })

        call.on('cancel', () => {
          setCallState('idle')
          stopTimer()
        })

        call.on('error', (err) => {
          setError(`Call error: ${err.message}`)
          setCallState('idle')
          stopTimer()
        })

        connectionRef.current = call
      } else {
        setCallState('active')
        startTimer()
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to place call')
      setCallState('idle')
    }
  }

  const handleHangUp = () => {
    if (connectionRef.current) {
      connectionRef.current.disconnect()
    }
    stopTimer()
    setCallState('ended')
  }

  const handleViewCall = () => {
    if (callId) {
      navigate(`/calls/${callId}`)
    }
  }

  return (
    <div className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-6">Place a Call</h1>

      {callState === 'idle' && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Call Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Patient check-in"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Patient Phone Number</label>
            <input
              type="tel"
              value={patientPhone}
              onChange={(e) => setPatientPhone(e.target.value)}
              placeholder="+15551234567"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Patient Name</label>
            <input
              type="text"
              value={patientName}
              onChange={(e) => setPatientName(e.target.value)}
              placeholder="e.g. Lionel"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Connection Mode</label>
            <div className="flex gap-3">
              <button
                onClick={() => setMode('browser')}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-medium transition ${
                  mode === 'browser'
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <span className="block text-lg mb-1">🎧</span>
                Browser
                <span className="block text-xs text-gray-500 mt-0.5">Use headset</span>
              </button>
              <button
                onClick={() => setMode('phone')}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-medium transition ${
                  mode === 'phone'
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <span className="block text-lg mb-1">📱</span>
                Phone
                <span className="block text-xs text-gray-500 mt-0.5">Ring my phone</span>
              </button>
            </div>
          </div>

          {mode === 'phone' && (
            <div>
              <label className="block text-sm font-medium mb-1">Your Phone Number</label>
              <input
                type="tel"
                value={workerPhone}
                onChange={(e) => setWorkerPhone(e.target.value)}
                placeholder="+15559876543"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          )}

          {error && (
            <div className="bg-red-50 text-red-600 p-3 rounded text-sm">{error}</div>
          )}

          <button
            onClick={handleDial}
            disabled={!patientPhone || (mode === 'phone' && !workerPhone)}
            className="w-full bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-lg"
          >
            Call
          </button>
        </div>
      )}

      {callState === 'connecting' && (
        <div className="text-center py-12">
          <div className="animate-pulse text-6xl mb-4">📞</div>
          <p className="text-lg font-medium text-gray-700">Connecting...</p>
          <p className="text-sm text-gray-500 mt-1">{patientPhone}</p>
        </div>
      )}

      {callState === 'active' && (
        <div className="text-center py-8">
          <div className="text-6xl mb-4">🟢</div>
          <p className="text-3xl font-mono font-bold text-gray-800 mb-2">{formatTimer(timer)}</p>
          <p className="text-sm text-gray-500 mb-6">
            Connected to {patientPhone}
            <span className="ml-2 text-xs bg-gray-200 px-2 py-0.5 rounded">
              {mode === 'browser' ? 'Browser' : 'Phone'}
            </span>
          </p>
          <button
            onClick={handleHangUp}
            className="bg-red-600 text-white px-8 py-3 rounded-full font-medium hover:bg-red-700 text-lg"
          >
            Hang Up
          </button>
        </div>
      )}

      {callState === 'ended' && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">✅</div>
          <p className="text-lg font-medium text-gray-700 mb-1">Call Ended</p>
          <p className="text-sm text-gray-500 mb-6">
            Duration: {formatTimer(timer)} — Recording is being processed
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={handleViewCall}
              className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700"
            >
              View Call Details
            </button>
            <button
              onClick={() => {
                setCallState('idle')
                setPatientPhone('')
                setPatientName('')
                setWorkerPhone('')
                setTitle('')
                setTimer(0)
                setCallId(null)
                setError('')
              }}
              className="border border-gray-300 px-6 py-2 rounded-lg font-medium hover:bg-gray-50"
            >
              New Call
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
