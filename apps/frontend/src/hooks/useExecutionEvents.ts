import { useState, useEffect, useRef } from 'react'
import type { ExecutionEvent } from '../types/domain'
import { api } from '../api/client'

type ConnectionStatus = 'connecting' | 'open' | 'closed' | 'error'

export function useExecutionEvents(executionId: string | null, reconnectKey = 0) {
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
        const incoming = raw as unknown as ExecutionEvent
        setEvents(prev => {
          // Dedup by id: on reconnect (e.g. after approval) the backend replays
          // persisted events that may overlap with live ones still in flight.
          if (incoming.id && prev.some(e => e.id === incoming.id)) return prev
          const next = [...prev, incoming]
          // Cap to the last 2000 events so very long runs don't exhaust memory
          // or freeze the renderer. Tool/lifecycle events take priority because
          // the backend no longer replays raw streaming tokens (model_chunk).
          return next.length > 2000 ? next.slice(-2000) : next
        })
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
  }, [executionId, reconnectKey])

  return { events, connectionStatus }
}
