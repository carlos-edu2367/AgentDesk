import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ChatThread, type ChatTurnVM } from '../components/chat/ChatThread'
import { LogsDrawer } from '../components/chat/LogsDrawer'
import { conversationsApi } from '../api/conversations'
import { workspacesApi } from '../api/workspaces'
import { approvalsApi } from '../api/approvals'
import { useExecutionEvents } from '../hooks/useExecutionEvents'
import type { ApprovalMode, Conversation, ConversationDetail, Workspace } from '../types/domain'

// Backend events that mark the end of a turn (agent or team).
const TERMINAL_EVENT_TYPES = new Set([
  'execution_completed',
  'execution_failed',
  'execution_cancelled',
  'team_completed',
  'team_failed',
])

export function ConversationView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [logsOpen, setLogsOpen] = useState(false)
  const [approvalMode, setApprovalMode] = useState<ApprovalMode>('manual')
  const [resolvingApprovalId, setResolvingApprovalId] = useState<string | null>(null)

  // Sibling chats (same agent/team) for the left rail + new-chat action.
  const [siblings, setSiblings] = useState<Conversation[]>([])
  // Workspaces granted to this chat (so file/terminal tools can run).
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [workspaceIds, setWorkspaceIds] = useState<string[]>([])
  const [workspacePanelOpen, setWorkspacePanelOpen] = useState(false)

  // The turn currently streaming over SSE (not yet persisted into `detail`).
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null)
  const [pendingInput, setPendingInput] = useState('')
  const [sseReconnectKey, setSseReconnectKey] = useState(0)

  const { events: liveEvents, connectionStatus } = useExecutionEvents(activeExecutionId, sseReconnectKey)
  const bottomRef = useRef<HTMLDivElement>(null)

  const fetchDetail = async () => {
    if (!id) return
    const d = await conversationsApi.get(id).catch(e => {
      setError(String(e))
      return null
    })
    if (d) {
      setDetail(d)
      setWorkspaceIds(d.conversation.workspace_ids ?? [])
    }
  }

  const loadSiblings = async (conv: Conversation) => {
    const list = await conversationsApi
      .list({ type: conv.type, target_id: conv.target_id, limit: 100 })
      .catch(() => [])
    setSiblings(list)
  }

  useEffect(() => {
    if (!id) return
    // Reset the in-flight turn when switching chats; otherwise the previous
    // chat's streaming turn (activeExecutionId) leaks into every conversation we
    // open, showing the same trailing messages everywhere.
    setActiveExecutionId(null)
    setPendingInput('')
    setError(null)
    setLoading(true)
    conversationsApi.get(id)
      .then(d => {
        setDetail(d)
        setWorkspaceIds(d.conversation.workspace_ids ?? [])
        loadSiblings(d.conversation)
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    workspacesApi.list().then(setWorkspaces).catch(() => setWorkspaces([]))
  }, [])

  // Fold the streaming turn into persisted history once the backend emits a
  // terminal event. We key off the events (not `connectionStatus`) because the
  // hook's status starts at 'closed' before the SSE opens — reacting to that
  // would tear the stream down immediately.
  useEffect(() => {
    if (!activeExecutionId) return
    // Match on execution_id: when switching turns, liveEvents can briefly still
    // hold the previous turn's terminal event before the hook resets it.
    const finished = liveEvents.some(
      e => e.execution_id === activeExecutionId && TERMINAL_EVENT_TYPES.has(e.type),
    )
    if (finished) {
      fetchDetail().then(() => {
        setActiveExecutionId(null)
        setPendingInput('')
        if (detail) loadSiblings(detail.conversation)
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveEvents, activeExecutionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [liveEvents, detail])

  // Only events belonging to the active execution (liveEvents can briefly carry
  // the previous turn's events across a turn switch).
  const activeEvents = useMemo(
    () => liveEvents.filter(e => e.execution_id === activeExecutionId),
    [liveEvents, activeExecutionId],
  )

  const turns: ChatTurnVM[] = useMemo(() => {
    const persisted: ChatTurnVM[] = (detail?.turns ?? []).map(t => ({
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
        events: activeEvents,
        result: null,
        pending: true,
      })
    }
    return persisted
  }, [detail, activeExecutionId, pendingInput, activeEvents])

  const drawerEvents = activeExecutionId
    ? activeEvents
    : detail?.turns[detail.turns.length - 1]?.events ?? []

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || !message.trim() || sending) return
    const text = message.trim()
    setSending(true)
    setError(null)
    try {
      setActiveExecutionId(null)
      const res = await conversationsApi.sendMessage(id, {
        message: text,
        stream: true,
        approval_mode: approvalMode,
        workspace_ids: workspaceIds,
      })
      setMessage('')
      setPendingInput(text)
      setActiveExecutionId(res.execution_id)
    } catch (err) {
      setError(String(err))
    } finally {
      setSending(false)
    }
  }

  const handleNewChat = async () => {
    if (!detail) return
    setError(null)
    try {
      const conv = await conversationsApi.create({
        type: detail.conversation.type,
        target_id: detail.conversation.target_id,
        title: '',
      })
      // Carry the current workspace grant over to the fresh chat.
      if (workspaceIds.length) {
        await conversationsApi.update(conv.id, { workspace_ids: workspaceIds }).catch(() => {})
      }
      navigate(`/conversations/${conv.id}`)
    } catch (err) {
      setError(String(err))
    }
  }

  const toggleWorkspace = async (wsId: string) => {
    if (!id) return
    const next = workspaceIds.includes(wsId)
      ? workspaceIds.filter(x => x !== wsId)
      : [...workspaceIds, wsId]
    setWorkspaceIds(next)
    try {
      await conversationsApi.update(id, { workspace_ids: next })
    } catch (err) {
      setError(String(err))
    }
  }

  const handleResolveApproval = async (
    executionId: string,
    approvalId: string,
    approved: boolean,
  ) => {
    setError(null)
    setResolvingApprovalId(approvalId)
    try {
      await approvalsApi.resolve(executionId, approvalId, approved, undefined, approvalMode)
      // Force SSE to reconnect so resumed execution events stream live.
      // (activeExecutionId hasn't changed, so a plain setActiveExecutionId is a no-op.)
      setSseReconnectKey(k => k + 1)
      await fetchDetail()
    } catch (err) {
      setError(String(err))
    } finally {
      setResolvingApprovalId(null)
    }
  }

  if (loading) return <LoadingState message="Loading conversation..." />

  const title = detail?.conversation.title || 'Conversation'
  const isTeam = detail?.conversation.type === 'team'
  const grantedCount = workspaceIds.length

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

      <div className="flex flex-1 min-h-0 gap-3">
        {/* Left rail: all chats for this agent/team + new chat */}
        <aside className="hidden md:flex w-60 shrink-0 flex-col border border-slate-700 rounded-lg bg-slate-900/40 overflow-hidden">
          <div className="p-2 border-b border-slate-700">
            <button className="btn-primary w-full text-xs" onClick={handleNewChat}>
              + New chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {siblings.length === 0 ? (
              <p className="text-xs text-slate-500 px-1 py-2">No chats yet.</p>
            ) : (
              siblings.map(c => (
                <button
                  key={c.id}
                  onClick={() => navigate(`/conversations/${c.id}`)}
                  className={`block w-full text-left rounded-md px-2 py-1.5 text-xs truncate transition-colors ${
                    c.id === id
                      ? 'bg-slate-700 text-slate-100'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                  title={c.title || 'Untitled chat'}
                >
                  {c.title || 'Untitled chat'}
                </button>
              ))
            )}
          </div>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col">
          {/* Workspace grant control */}
          <div className="mb-2">
            <button
              type="button"
              className="btn-ghost text-xs"
              onClick={() => setWorkspacePanelOpen(o => !o)}
            >
              📁 Workspaces: {grantedCount > 0 ? `${grantedCount} granted` : 'none'} {workspacePanelOpen ? '▲' : '▼'}
            </button>
            {workspacePanelOpen && (
              <div className="mt-2 rounded-md border border-slate-700 bg-slate-900/40 p-3">
                {workspaces.length === 0 ? (
                  <p className="text-xs text-slate-500">
                    No workspaces.{' '}
                    <button type="button" className="underline" onClick={() => navigate('/workspaces')}>
                      Create one
                    </button>{' '}
                    to let this chat read/write files or run commands.
                  </p>
                ) : (
                  <div className="space-y-2">
                    <p className="text-xs text-slate-400">
                      Grant workspaces so the agent can use filesystem/terminal tools in this chat.
                    </p>
                    {workspaces.map(w => (
                      <label key={w.id} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={workspaceIds.includes(w.id)}
                          onChange={() => toggleWorkspace(w.id)}
                          className="rounded border-slate-600 bg-slate-800 text-blue-500"
                        />
                        <span className="text-sm text-slate-300">{w.name}</span>
                        <span className="text-xs text-slate-500 truncate">{w.paths[0]}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto pr-2">
            <ChatThread
              turns={turns}
              resolvingApprovalId={resolvingApprovalId}
              onResolveApproval={handleResolveApproval}
            />
            <div ref={bottomRef} />
          </div>

          <form onSubmit={handleSend} className="mt-3 grid grid-cols-[1fr_auto] gap-2 items-end">
            <label className="col-span-2 inline-flex select-none items-center gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-600 bg-slate-900"
                checked={approvalMode === 'auto'}
                onChange={e => setApprovalMode(e.target.checked ? 'auto' : 'manual')}
              />
              Auto-approval
            </label>
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
