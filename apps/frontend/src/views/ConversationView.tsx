import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ChatThread, type ChatTurnVM } from '../components/chat/ChatThread'
import { LogsDrawer } from '../components/chat/LogsDrawer'
import { conversationsApi } from '../api/conversations'
import { workspacesApi } from '../api/workspaces'
import { approvalsApi } from '../api/approvals'
import { executionsApi } from '../api/executions'
import { useExecutionEvents } from '../hooks/useExecutionEvents'
import { groupTurnEvents } from '../lib/groupEvents'
import type { ApprovalMode, ConversationDetail, ExecutionEvent, ExecutionStatus, Workspace } from '../types/domain'

// Backend events that mark the end of a turn (agent or team).
const TERMINAL_EVENT_TYPES = new Set([
  'execution_completed',
  'execution_failed',
  'execution_cancelled',
  'team_completed',
  'team_failed',
])

// Execution statuses where the turn is still in flight. The backend keeps
// running these in a background task even after the chat is closed, so when we
// reopen a conversation we reconnect the SSE stream instead of showing a frozen
// turn.
const NON_TERMINAL_STATUSES: ReadonlySet<ExecutionStatus> = new Set([
  'pending',
  'running',
  'waiting_approval',
])

// Merge a turn's persisted events with the events streaming live over SSE,
// deduping by id. On reconnect the persisted snapshot and the live stream
// overlap; without this the live updates would be dropped for a turn that was
// already in `detail`.
function mergeEvents(persisted: ExecutionEvent[], live: ExecutionEvent[]): ExecutionEvent[] {
  const seen = new Set(persisted.map(e => e.id).filter(Boolean))
  return [...persisted, ...live.filter(e => !e.id || !seen.has(e.id))]
}

export function ConversationView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [logsOpen, setLogsOpen] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [approvalMode, setApprovalMode] = useState<ApprovalMode>('manual')
  const [resolvingApprovalId, setResolvingApprovalId] = useState<string | null>(null)
  // Per-chat step budget (empty = use engine default). Kept as a string so the
  // input can be cleared; coerced to a number/null when persisted and sent.
  const [maxStepsInput, setMaxStepsInput] = useState('')

  // Computer-use flag for this chat. Requires the agent to have the computer_use capability.
  const [computerUseEnabled, setComputerUseEnabled] = useState(false)

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
      setMaxStepsInput(d.conversation.max_steps != null ? String(d.conversation.max_steps) : '')
      setComputerUseEnabled(d.conversation.computer_use_enabled ?? false)
    }
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
        setMaxStepsInput(d.conversation.max_steps != null ? String(d.conversation.max_steps) : '')
        setComputerUseEnabled(d.conversation.computer_use_enabled ?? false)
        // If the latest turn is still in flight, reconnect its live stream. The
        // backend has been working (or waiting on approval) the whole time the
        // chat was closed; this resumes streaming instead of showing it frozen.
        const last = d.turns[d.turns.length - 1]?.execution
        if (last && NON_TERMINAL_STATUSES.has(last.status)) {
          setPendingInput(last.user_input)
          setActiveExecutionId(last.id)
        }
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
    const persisted: ChatTurnVM[] = (detail?.turns ?? []).map(t => {
      // The active turn may already be persisted (e.g. we reopened the chat
      // mid-run). Fold the live SSE events into it and keep it marked pending so
      // the "Working…" indicator and Stop button stay visible.
      if (t.execution.id === activeExecutionId) {
        return {
          id: t.execution.id,
          userInput: t.execution.user_input,
          events: mergeEvents(t.events, activeEvents),
          result: t.execution.result,
          pending: true,
        }
      }
      return {
        id: t.execution.id,
        userInput: t.execution.user_input,
        events: t.events,
        result: t.execution.result,
      }
    })
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

  // The agent is actively generating when there's an in-flight turn that isn't
  // paused waiting for an approval (the approve/reject UI takes over there).
  const activeTurn = turns.find(t => t.id === activeExecutionId)
  const awaitingApproval = activeTurn ? Boolean(groupTurnEvents(activeTurn.events).pendingApproval) : false
  const canStop = Boolean(activeExecutionId) && !awaitingApproval

  const handleStop = async () => {
    if (!activeExecutionId) return
    setStopping(true)
    setError(null)
    try {
      // The engine emits a terminal `execution_cancelled` event over SSE, which
      // folds the turn into history via the effect above.
      await executionsApi.cancel(activeExecutionId)
    } catch (err) {
      setError(String(err))
    } finally {
      setStopping(false)
    }
  }

  // Parse the step-limit input into a positive integer, or null when blank/invalid.
  const parsedMaxSteps = (): number | null => {
    const n = parseInt(maxStepsInput, 10)
    return Number.isFinite(n) && n > 0 ? n : null
  }

  const persistMaxSteps = async () => {
    if (!id) return
    const value = parsedMaxSteps()
    // Normalize the field so an invalid/blank entry shows as cleared.
    setMaxStepsInput(value != null ? String(value) : '')
    if (value === (detail?.conversation.max_steps ?? null)) return
    try {
      await conversationsApi.update(id, { max_steps: value })
      setDetail(d => (d ? { ...d, conversation: { ...d.conversation, max_steps: value } } : d))
    } catch (err) {
      setError(String(err))
    }
  }

  const toggleComputerUse = async () => {
    if (!id) return
    const next = !computerUseEnabled
    setComputerUseEnabled(next)
    try {
      await conversationsApi.update(id, { computer_use_enabled: next })
      setDetail(d => d ? { ...d, conversation: { ...d.conversation, computer_use_enabled: next } } : d)
    } catch (err) {
      setComputerUseEnabled(!next)
      setError(String(err))
    }
  }

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
        max_steps: parsedMaxSteps(),
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
                    <button type="button" className="underline" onClick={() => navigate('/config/workspaces')}>
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
            <div className="col-span-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-300">
              <label className="inline-flex select-none items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-600 bg-slate-900"
                  checked={approvalMode === 'auto'}
                  onChange={e => setApprovalMode(e.target.checked ? 'auto' : 'manual')}
                />
                Auto-approval
              </label>
              <label className="inline-flex select-none items-center gap-2">
                <span>Step limit</span>
                <input
                  type="number"
                  min={1}
                  className="form-input h-7 w-20 text-xs"
                  value={maxStepsInput}
                  placeholder={isTeam ? '30' : '10'}
                  onChange={e => setMaxStepsInput(e.target.value)}
                  onBlur={persistMaxSteps}
                  title="Max runtime steps for this chat. Leave blank to use the default."
                />
              </label>
              <label
                className="inline-flex select-none items-center gap-2"
                title="Enables screen.perceive / screen.click / screen.type tools. Requires computer_use capability on the agent."
              >
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-600 bg-slate-900"
                  checked={computerUseEnabled}
                  onChange={toggleComputerUse}
                />
                Computer Use
              </label>
            </div>
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
            <div className="flex items-center gap-2">
              {canStop && (
                <button
                  type="button"
                  className="btn-danger"
                  aria-label="Stop the agent"
                  onClick={handleStop}
                  disabled={stopping}
                >
                  {stopping ? 'Stopping…' : '■ Stop'}
                </button>
              )}
              <button type="submit" className="btn-primary" disabled={sending || !message.trim()}>
                {sending ? 'Sending…' : 'Send'}
              </button>
            </div>
          </form>
        </div>

        {logsOpen && (
          <LogsDrawer events={drawerEvents} open onToggle={() => setLogsOpen(false)} />
        )}
      </div>
    </div>
  )
}
