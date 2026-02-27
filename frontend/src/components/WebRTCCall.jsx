import { useState, useRef, useCallback } from 'react'

/**
 * WebRTC in-browser calling component (stretch goal).
 * Uses the signaling API for basic peer-to-peer voice calls.
 */
export default function WebRTCCall() {
  const [sessionId, setSessionId] = useState('')
  const [status, setStatus] = useState('idle') // idle, calling, connected
  const [mode, setMode] = useState(null) // 'caller' or 'callee'
  const pcRef = useRef(null)
  const localStreamRef = useRef(null)
  const remoteAudioRef = useRef()

  const cleanup = useCallback(() => {
    pcRef.current?.close()
    pcRef.current = null
    localStreamRef.current?.getTracks().forEach(t => t.stop())
    localStreamRef.current = null
    setStatus('idle')
    setMode(null)
  }, [])

  const createPeerConnection = () => {
    const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
    pc.ontrack = (e) => {
      if (remoteAudioRef.current) {
        remoteAudioRef.current.srcObject = e.streams[0]
      }
    }
    pc.oniceconnectionstatechange = () => {
      if (pc.iceConnectionState === 'disconnected' || pc.iceConnectionState === 'failed') {
        cleanup()
      }
    }
    pcRef.current = pc
    return pc
  }

  const startCall = async () => {
    if (!sessionId) return
    setMode('caller')
    setStatus('calling')

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    localStreamRef.current = stream

    const pc = createPeerConnection()
    stream.getTracks().forEach(t => pc.addTrack(t, stream))

    // Collect ICE candidates
    pc.onicecandidate = async (e) => {
      if (e.candidate) {
        await fetch('/api/webrtc/ice-candidate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, candidate: e.candidate.toJSON() }),
        })
      }
    }

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    await fetch('/api/webrtc/offer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, sdp: offer.sdp, type: offer.type }),
    })

    // Poll for answer
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`/api/webrtc/answer/${sessionId}`)
        if (res.ok) {
          const answer = await res.json()
          await pc.setRemoteDescription(new RTCSessionDescription(answer))
          setStatus('connected')
          clearInterval(poll)
        }
      } catch {}
    }, 1000)
  }

  const joinCall = async () => {
    if (!sessionId) return
    setMode('callee')
    setStatus('calling')

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    localStreamRef.current = stream

    const pc = createPeerConnection()
    stream.getTracks().forEach(t => pc.addTrack(t, stream))

    pc.onicecandidate = async (e) => {
      if (e.candidate) {
        await fetch('/api/webrtc/ice-candidate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, candidate: e.candidate.toJSON() }),
        })
      }
    }

    const offerRes = await fetch(`/api/webrtc/offer/${sessionId}`)
    const offer = await offerRes.json()
    await pc.setRemoteDescription(new RTCSessionDescription(offer))

    const answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    await fetch('/api/webrtc/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, sdp: answer.sdp, type: answer.type }),
    })

    setStatus('connected')
  }

  return (
    <div className="max-w-md mx-auto">
      <h2 className="text-lg font-semibold mb-4">WebRTC Call (Experimental)</h2>

      <div className="space-y-3">
        <input
          type="text"
          value={sessionId}
          onChange={e => setSessionId(e.target.value)}
          placeholder="Enter a session ID (share with peer)"
          className="w-full border rounded-lg px-3 py-2 text-sm"
          disabled={status !== 'idle'}
        />

        {status === 'idle' && (
          <div className="flex gap-2">
            <button onClick={startCall} disabled={!sessionId} className="flex-1 bg-green-600 text-white py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50">
              Start Call
            </button>
            <button onClick={joinCall} disabled={!sessionId} className="flex-1 bg-blue-600 text-white py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
              Join Call
            </button>
          </div>
        )}

        {status === 'calling' && (
          <p className="text-blue-600 text-sm">Connecting...</p>
        )}

        {status === 'connected' && (
          <div className="space-y-2">
            <p className="text-green-600 text-sm font-medium">Connected ({mode})</p>
            <button onClick={cleanup} className="w-full bg-red-600 text-white py-2 rounded-lg text-sm hover:bg-red-700">
              End Call
            </button>
          </div>
        )}
      </div>

      <audio ref={remoteAudioRef} autoPlay />
    </div>
  )
}
