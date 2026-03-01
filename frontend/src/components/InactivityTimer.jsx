import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'

const TIMEOUT_MS = 15 * 60 * 1000
const WARNING_MS = 13 * 60 * 1000

export default function InactivityTimer() {
  const { user, logout } = useAuth()
  const [showWarning, setShowWarning] = useState(false)

  useEffect(() => {
    if (!user) return

    let warningTimeout
    let logoutTimeout

    const startTimers = () => {
      clearTimeout(warningTimeout)
      clearTimeout(logoutTimeout)
      setShowWarning(false)

      warningTimeout = setTimeout(() => setShowWarning(true), WARNING_MS)
      logoutTimeout = setTimeout(() => {
        logout()
        window.location.href = '/login'
      }, TIMEOUT_MS)
    }

    const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart']
    const handleActivity = () => {
      startTimers()
    }

    events.forEach((e) => window.addEventListener(e, handleActivity))
    startTimers()

    return () => {
      events.forEach((e) => window.removeEventListener(e, handleActivity))
      clearTimeout(warningTimeout)
      clearTimeout(logoutTimeout)
    }
  }, [user, logout])

  if (!showWarning) return null

  return (
    <div className="fixed bottom-4 right-4 bg-yellow-50 border border-yellow-300 text-yellow-800 px-4 py-3 rounded-lg shadow-lg z-50">
      <p className="text-sm font-medium">Session expiring soon</p>
      <p className="text-xs">Move your mouse or press a key to stay logged in.</p>
    </div>
  )
}
