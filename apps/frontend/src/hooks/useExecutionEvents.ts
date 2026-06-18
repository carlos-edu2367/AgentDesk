import { useState, useEffect, useRef } from 'react'
import type { ExecutionEvent } from '../types/domain'
import { api } from '../api/client'

type ConnectionStatus = 'connecting' | 'open' | 'closed' | 'error'

export function useExecutionEvents(executionId: string | null) {
  const [events, setEvents] = useState<ExecutionEvent[]>([])
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('closed')
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!executionId) return

    setEvents([])
    setConnectionStatus('connecting')

    const url = `${api.getBaseUrl()}/api/executions/${executionId}/events`
    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => setConnectionStatus('open')

    es.onmessage = (e: MessageEvent<string>) => {
      try {
        const raw = JSON.parse(e.data) as Record<string, unknown>
        if (raw['type'] === 'sse_close_connection') {
          es.close()
          setConnectionStatus('closed')
          return
        }
        setEvents(prev => [...prev, raw as unknown as ExecutionEvent])
      } catch {
        // ignore malformed events
      }
    }

    es.onerror = () => {
      setConnectionStatus('error')
      es.close()
    }

    return () => {
      es.close()
      esRef.current = null
      setConnectionStatus('closed')
    }
  }, [executionId])

  return { events, connectionStatus }
}
