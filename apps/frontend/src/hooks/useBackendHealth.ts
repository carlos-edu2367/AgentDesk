import { useState, useEffect, useCallback } from 'react'
import { healthApi } from '../api/storage'

type Status = 'checking' | 'online' | 'offline'

export function useBackendHealth(intervalMs = 10000) {
  const [status, setStatus] = useState<Status>('checking')

  const check = useCallback(async () => {
    try {
      const res = await healthApi.check()
      setStatus(res.status === 'ok' ? 'online' : 'offline')
    } catch {
      setStatus('offline')
    }
  }, [])

  useEffect(() => {
    check()
    const id = setInterval(check, intervalMs)
    return () => clearInterval(id)
  }, [check, intervalMs])

  return { status, refresh: check }
}
