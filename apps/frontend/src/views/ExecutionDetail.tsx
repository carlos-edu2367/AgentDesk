import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { useExecutionEvents } from '../hooks/useExecutionEvents'
import { executionsApi } from '../api/executions'
import type { Execution, ExecutionEvent } from '../types/domain'

const EVENT_LABELS: Record<string, string> = {
  execution_created: 'Execution created',
  execution_started: 'Execution started',
  agent_started: 'Agent started',
  prompt_built: 'Prompt built',
  model_request_started: 'Model request started',
  model_chunk: 'Streaming...',
  model_completed: 'Model response complete',
  agent_completed: 'Agent completed',
  execution_completed: 'Execution completed',
  execution_failed: 'Execution failed',
  execution_cancelled: 'Execution cancelled',
  tool_call_ignored: 'Tool call ignored',
  error: 'Error',
}

export function ExecutionDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [execution, setExecution] = useState<Execution | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(false)
  const { events, connectionStatus } = useExecutionEvents(id ?? null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Accumulate model chunks into a single streaming text
  const streamingText = events
    .filter(e => e.type === 'model_chunk')
    .map(e => (e.content.delta as string) ?? '')
    .join('')

  useEffect(() => {
    if (!id) return
    executionsApi.get(id)
      .then(setExecution)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  // Refresh execution status when SSE closes
  useEffect(() => {
    if (connectionStatus === 'closed' && id) {
      executionsApi.get(id).then(setExecution).catch(() => {})
    }
  }, [connectionStatus, id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  const handleCancel = async () => {
    if (!id || !execution) return
    setCancelling(true)
    try {
      await executionsApi.cancel(id)
    } finally {
      setCancelling(false)
    }
  }

  if (loading) return <LoadingState />

  const visibleEvents = events.filter(e => e.type !== 'model_chunk')
  const isTerminal = ['completed', 'failed', 'cancelled'].includes(execution?.status ?? '')

  return (
    <div>
      <TopBar
        title="Execution Detail"
        actions={
          <div className="flex items-center gap-2">
            {!isTerminal && execution && (
              <button className="btn-danger text-xs" onClick={handleCancel} disabled={cancelling}>
                {cancelling ? 'Cancelling...' : 'Cancel'}
              </button>
            )}
            <button className="btn-ghost text-xs" onClick={() => navigate('/executions')}>
              Back
            </button>
          </div>
        }
      />

      {/* Header */}
      <div className="card mb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-slate-300 mb-1">Input</p>
            <p className="text-slate-100">{execution?.user_input ?? '...'}</p>
          </div>
          <div className="shrink-0 flex flex-col items-end gap-1">
            {execution?.status && <StatusBadge status={execution.status} />}
            {connectionStatus === 'open' && (
              <span className="text-xs text-blue-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
                Live
              </span>
            )}
          </div>
        </div>
        {execution?.created_at && (
          <p className="text-xs text-slate-500 mt-2">{new Date(execution.created_at).toLocaleString()}</p>
        )}
      </div>

      {/* Streaming response */}
      {streamingText && (
        <div className="card mb-4 border-blue-500/20">
          <p className="text-xs text-blue-400 mb-2">Streaming response</p>
          <p className="text-sm text-slate-200 whitespace-pre-wrap">{streamingText}</p>
        </div>
      )}

      {/* Final result */}
      {execution?.result && (
        <div className="card mb-4 border-green-500/20">
          <p className="text-xs text-green-400 mb-2">Final result</p>
          <p className="text-sm text-slate-200 whitespace-pre-wrap">{execution.result}</p>
        </div>
      )}

      {execution?.error && (
        <div className="card mb-4 border-red-500/20">
          <p className="text-xs text-red-400 mb-2">Error</p>
          <p className="text-sm text-red-300 whitespace-pre-wrap">{execution.error}</p>
        </div>
      )}

      {/* Timeline */}
      <div className="card">
        <p className="text-sm font-semibold text-slate-300 mb-3">Timeline</p>
        {visibleEvents.length === 0 ? (
          <p className="text-slate-500 text-sm">No events yet.</p>
        ) : (
          <div className="space-y-2">
            {visibleEvents.map(ev => (
              <EventCard key={ev.id} event={ev} />
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function EventCard({ event }: { event: ExecutionEvent }) {
  const [expanded, setExpanded] = useState(false)
  const label = EVENT_LABELS[event.type] ?? event.type
  const isError = event.type === 'error' || event.type === 'execution_failed'
  const isSuccess = event.type === 'execution_completed' || event.type === 'agent_completed'

  const hasContent = Object.keys(event.content).length > 0

  return (
    <div className={`rounded-md border px-3 py-2 text-xs ${
      isError ? 'border-red-500/30 bg-red-500/5' :
      isSuccess ? 'border-green-500/30 bg-green-500/5' :
      'border-slate-700 bg-slate-800/50'
    }`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`font-medium ${isError ? 'text-red-300' : isSuccess ? 'text-green-300' : 'text-slate-300'}`}>
            {label}
          </span>
          <span className="text-slate-600">{event.source}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-slate-600">
            {new Date(event.created_at).toLocaleTimeString()}
          </span>
          {hasContent && (
            <button
              className="text-slate-500 hover:text-slate-300 transition-colors"
              onClick={() => setExpanded(v => !v)}
            >
              {expanded ? '▲' : '▼'}
            </button>
          )}
        </div>
      </div>
      {expanded && hasContent && (
        <pre className="mt-2 text-slate-400 text-xs overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(event.content, null, 2)}
        </pre>
      )}
    </div>
  )
}
