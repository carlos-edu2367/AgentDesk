import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ChatThread, type ChatTurnVM } from '../components/chat/ChatThread'
import { LogsDrawer } from '../components/chat/LogsDrawer'
import { conversationsApi } from '../api/conversations'
import { useExecutionEvents } from '../hooks/useExecutionEvents'
import type { ConversationDetail } from '../types/domain'

export function ConversationView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [logsOpen, setLogsOpen] = useState(false)

  // The turn currently streaming over SSE (not yet persisted into `detail`).
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null)
  const [pendingInput, setPendingInput] = useState('')

  const { events: liveEvents, connectionStatus } = useExecutionEvents(activeExecutionId)
  const bottomRef = useRef<HTMLDivElement>(null)

  const fetchDetail = async () => {
    if (!id) return
    const d = await conversationsApi.get(id).catch(e => {
      setError(String(e))
      return null
    })
    if (d) setDetail(d)
  }

  useEffect(() => {
    if (!id) return
    setLoading(true)
    conversationsApi.get(id)
      .then(setDetail)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [id])

  // When the streaming turn finishes, fold it into the persisted detail.
  useEffect(() => {
    if (connectionStatus === 'closed' && activeExecutionId) {
      fetchDetail().then(() => {
        setActiveExecutionId(null)
        setPendingInput('')
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionStatus, activeExecutionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [liveEvents, detail])

  const turns: ChatTurnVM[] = useMemo(() => {
    const persisted = (detail?.turns ?? []).map(t => ({
      id: t.execution.id,
      userInput: t.execution.user_input,
      events: t.events,
      result: t.execution.result,
    }))
    const alreadyPersisted = new Set(persisted.map(t => t.id))
    if (activeExecutionId && !alreadyPersisted.has(activeExecutionId)) {
      persisted.push({
        id: activeExecutionId,
        userInput: pendingInput,
        events: liveEvents,
        result: null,
        // @ts-expect-error pending is part of ChatTurnVM
        pending: connectionStatus !== 'closed',
      })
    }
    return persisted
  }, [detail, activeExecutionId, pendingInput, liveEvents, connectionStatus])

  const drawerEvents = activeExecutionId
    ? liveEvents
    : detail?.turns[detail.turns.length - 1]?.events ?? []

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || !message.trim() || sending) return
    const text = message.trim()
    setSending(true)
    setError(null)
    try {
      setActiveExecutionId(null)
      const res = await conversationsApi.sendMessage(id, { message: text, stream: true })
      setMessage('')
      setPendingInput(text)
      setActiveExecutionId(res.execution_id)
    } catch (err) {
      setError(String(err))
    } finally {
      setSending(false)
    }
  }

  if (loading) return <LoadingState message="Loading conversation..." />

  const title = detail?.conversation.title || 'Conversation'
  const isTeam = detail?.conversation.type === 'team'

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)]">
      <TopBar
        title={title}
        description={isTeam ? 'Chat with the team leader' : 'Chat with the agent'}
        actions={
          <div className="flex items-center gap-2">
            {connectionStatus === 'open' && (
              <span className="text-xs text-blue-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
                Live
              </span>
            )}
            <LogsDrawer events={drawerEvents} open={false} onToggle={() => setLogsOpen(o => !o)} />
            <button className="btn-ghost text-xs" onClick={() => navigate(isTeam ? '/teams' : '/agents')}>
              Back
            </button>
          </div>
        }
      />

      {error && (
        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md p-3 mb-3">
          {error}
        </div>
      )}

      <div className="flex flex-1 min-h-0 gap-0">
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex-1 overflow-y-auto pr-2">
            <ChatThread turns={turns} />
            <div ref={bottomRef} />
          </div>

          <form onSubmit={handleSend} className="mt-3 flex gap-2 items-end">
            <textarea
              className="form-textarea flex-1 min-h-[52px] max-h-40"
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="Send a message…"
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend(e as unknown as React.FormEvent)
                }
              }}
            />
            <button type="submit" className="btn-primary" disabled={sending || !message.trim()}>
              {sending ? 'Sending…' : 'Send'}
            </button>
          </form>
        </div>

        {logsOpen && (
          <LogsDrawer events={drawerEvents} open onToggle={() => setLogsOpen(false)} />
        )}
      </div>
    </div>
  )
}
