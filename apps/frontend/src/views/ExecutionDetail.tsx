import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { useExecutionEvents } from '../hooks/useExecutionEvents'
import { executionsApi } from '../api/executions'
import { approvalsApi } from '../api/approvals'
import type { Execution, ExecutionEvent, ApprovalRequest, ExecutionDetailResponse } from '../types/domain'

const EVENT_LABELS: Record<string, string> = {
  execution_created: 'Execution created',
  execution_started: 'Execution started',
  execution_waiting_approval: 'Waiting for approval',
  execution_resumed: 'Execution resumed',
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
  tool_call_requested: 'Tool call requested',
  tool_call_validated: 'Tool call validated',
  tool_call_denied: 'Tool call denied',
  tool_executed: 'Tool executed',
  tool_result: 'Tool result',
  tool_failed: 'Tool failed',
  plugin_tool_call_requested: 'Plugin tool requested',
  plugin_tool_started: 'Plugin tool started',
  plugin_tool_completed: 'Plugin tool completed',
  plugin_tool_failed: 'Plugin tool failed',
  plugin_disabled_tool_blocked: 'Plugin disabled',
  mcp_tool_call_requested: 'MCP tool requested',
  mcp_tool_started: 'MCP tool started',
  mcp_tool_completed: 'MCP tool completed',
  mcp_tool_failed: 'MCP tool failed',
  mcp_server_disabled_tool_blocked: 'MCP server disabled',
  mcp_server_not_associated: 'MCP server not associated',
  approval_requested: 'Approval requested',
  approval_approved: 'Approved',
  approval_rejected: 'Rejected',
  approval_auto_granted: 'Auto-approved',
  terminal_started: 'Terminal started',
  terminal_completed: 'Terminal completed',
  terminal_failed: 'Terminal failed',
  terminal_timeout: 'Terminal timeout',
  memory_lookup: 'Memory lookup',
  memory_lookup_result: 'Memories found',
  memory_created: 'Memory created',
  memory_updated: 'Memory updated',
  memory_deleted: 'Memory deleted',
  memory_embedding_generated: 'Embedding generated',
  memory_embedding_failed: 'Embedding failed',
  memory_usage_recorded: 'Memory usage recorded',
  skills_loaded: 'Skills loaded',
  skills_truncated: 'Skills truncated',
  skill_injected: 'Skill injected',
  skill_load_failed: 'Skill load failed',
  subagent_call_requested: 'Subagent call requested',
  subagent_started: 'Subagent started',
  subagent_completed: 'Subagent completed',
  subagent_failed: 'Subagent failed',
  team_started: 'Team started',
  leader_started: 'Leader started',
  leader_plan_created: 'Leader plan created',
  member_assigned: 'Member assigned',
  member_started: 'Member started',
  member_completed: 'Member completed',
  member_failed: 'Member failed',
  leader_review_started: 'Leader review started',
  leader_finalized: 'Leader finalized response',
  team_completed: 'Team completed',
  team_failed: 'Team failed',
  error: 'Error',
}

const TOOL_EVENT_TYPES = new Set([
  'tool_call_requested', 'tool_call_validated', 'tool_call_denied',
  'tool_executed', 'tool_result', 'tool_failed', 'tool_call_ignored',
  'plugin_tool_call_requested', 'plugin_tool_started', 'plugin_tool_completed',
  'plugin_tool_failed', 'plugin_disabled_tool_blocked',
  'mcp_tool_call_requested', 'mcp_tool_started', 'mcp_tool_completed',
  'mcp_tool_failed', 'mcp_server_disabled_tool_blocked', 'mcp_server_not_associated',
])

const APPROVAL_EVENT_TYPES = new Set([
  'approval_requested', 'approval_approved', 'approval_rejected', 'approval_auto_granted',
  'execution_waiting_approval', 'execution_resumed',
])

const TEAM_EVENT_TYPES = new Set([
  'team_started', 'leader_started', 'leader_plan_created',
  'member_assigned', 'member_started', 'member_completed', 'member_failed',
  'subagent_call_requested', 'subagent_started', 'subagent_completed', 'subagent_failed',
  'leader_review_started', 'leader_finalized', 'team_completed', 'team_failed',
])

const SKILL_EVENT_TYPES = new Set([
  'skills_loaded', 'skills_truncated', 'skill_injected', 'skill_load_failed',
])

const RISK_COLORS: Record<string, string> = {
  high: 'text-red-400 bg-red-500/10 border-red-500/30',
  medium: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  low: 'text-green-400 bg-green-500/10 border-green-500/30',
}

export function ExecutionDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [execution, setExecution] = useState<Execution | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(false)
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [detail, setDetail] = useState<ExecutionDetailResponse | null>(null)
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [exporting, setExporting] = useState<'json' | 'markdown' | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const { events, connectionStatus } = useExecutionEvents(id ?? null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const streamingText = events
    .filter(e => e.type === 'model_chunk')
    .map(e => (e.content.delta as string) ?? '')
    .join('')

  const fetchExecution = useCallback(async () => {
    if (!id) return
    const ex = await executionsApi.get(id).catch(() => null)
    if (ex) setExecution(ex)
    const detailFn = executionsApi.detail
    if (detailFn) {
      const nextDetail = await detailFn(id).catch(() => null)
      if (nextDetail) {
        setDetail(nextDetail)
        setExecution(nextDetail.execution)
        setApprovals(nextDetail.approvals)
      }
    }
  }, [id])

  const fetchApprovals = useCallback(async () => {
    if (!id) return
    const list = await approvalsApi.listForExecution(id).catch(() => [])
    setApprovals(list)
  }, [id])

  useEffect(() => {
    if (!id) return
    executionsApi.get(id)
      .then(setExecution)
      .catch(() => {})
      .finally(() => setLoading(false))
    executionsApi.detail?.(id).then(nextDetail => {
      setDetail(nextDetail)
      setExecution(nextDetail.execution)
      setApprovals(nextDetail.approvals)
    }).catch(() => {})
    fetchApprovals()
  }, [id, fetchApprovals])

  // Refresh when SSE closes (execution finished or went to waiting_approval)
  useEffect(() => {
    if (connectionStatus === 'closed' && id) {
      fetchExecution()
      fetchApprovals()
    }
  }, [connectionStatus, id, fetchExecution, fetchApprovals])

  // Re-fetch when events bring approval signals
  useEffect(() => {
    const last = events[events.length - 1]
    if (!last) return
    if (APPROVAL_EVENT_TYPES.has(last.type)) {
      fetchApprovals()
      fetchExecution()
    }
  }, [events, fetchApprovals, fetchExecution])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [events])

  // Poll for approvals while execution is waiting
  useEffect(() => {
    if (execution?.status !== 'waiting_approval') return
    const interval = setInterval(() => {
      fetchApprovals()
      fetchExecution()
    }, 3000)
    return () => clearInterval(interval)
  }, [execution?.status, fetchApprovals, fetchExecution])

  const handleCancel = async () => {
    if (!id || !execution) return
    setCancelling(true)
    try {
      await executionsApi.cancel(id)
    } finally {
      setCancelling(false)
    }
  }

  const handleResolveApproval = async (approval: ApprovalRequest, approved: boolean) => {
    if (!id) return
    setResolvingId(approval.id)
    try {
      await approvalsApi.resolve(id, approval.id, approved, approved ? undefined : rejectReason)
      setRejectReason('')
      await fetchApprovals()
      await fetchExecution()
    } catch (e) {
      alert(`Error: ${String(e)}`)
    } finally {
      setResolvingId(null)
    }
  }

  const handleExport = async (format: 'json' | 'markdown') => {
    if (!id) return
    setExporting(format)
    try {
      await executionsApi.export(id, format)
    } finally {
      setExporting(null)
    }
  }

  if (loading) return <LoadingState />

  const visibleEvents = events.filter(e => e.type !== 'model_chunk')
  const isTerminal = ['completed', 'failed', 'cancelled'].includes(execution?.status ?? '')
  const isWaitingApproval = execution?.status === 'waiting_approval'
  const pendingApprovals = approvals.filter(a => a.status === 'pending')

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
            {execution?.approval_mode === 'auto' && (
              <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded px-2 py-0.5">
                Auto-approval active
              </span>
            )}
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

      {/* Auto-approval warning */}
      {execution?.approval_mode === 'auto' && !isTerminal && (
        <div className="card mb-4 border-amber-500/20 bg-amber-500/5">
          <p className="text-xs text-amber-400">
            ⚡ Auto-approval active — authorized critical actions will execute without confirmation.
          </p>
        </div>
      )}

      {/* Pending approvals panel */}
      {isWaitingApproval && pendingApprovals.length > 0 && (
        <div className="mb-4 space-y-3">
          <p className="text-sm font-semibold text-amber-300">Pending Approvals</p>
          {pendingApprovals.map(approval => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              rejectReason={rejectReason}
              onRejectReasonChange={setRejectReason}
              onApprove={() => handleResolveApproval(approval, true)}
              onReject={() => handleResolveApproval(approval, false)}
              isLoading={resolvingId === approval.id}
            />
          ))}
        </div>
      )}

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

      <div className="card mb-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
          {['Overview', 'Timeline', 'Approvals', 'Tools', 'Memory', 'Skills', 'Plugins', 'MCP', 'Audit', 'Export'].map(section => (
            <span key={section} className="text-xs rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-300">
              {section}
            </span>
          ))}
        </div>

        <section className="mb-4">
          <h2 className="text-sm font-semibold text-slate-200 mb-2">Overview</h2>
          <dl className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
            <DetailMeta label="Status" value={execution?.status ?? '-'} />
            <DetailMeta label="Type" value={execution?.type ?? '-'} />
            <DetailMeta label="Target" value={execution?.target_id ?? '-'} />
            <DetailMeta label="Approval mode" value={execution?.approval_mode ?? '-'} />
            <DetailMeta label="Started" value={execution?.created_at ? new Date(execution.created_at).toLocaleString() : '-'} />
            <DetailMeta label="Completed" value={execution?.completed_at ? new Date(execution.completed_at).toLocaleString() : '-'} />
            <DetailMeta label="Critical actions" value={String(detail?.summary.critical_actions_count ?? 0)} />
            <DetailMeta label="Auto-approved" value={String(detail?.summary.auto_approved_count ?? 0)} />
          </dl>
        </section>

        <DetailList title="Tools" items={detail?.summary.tools_used ?? []} />
        <DetailList title="Memory" items={detail?.summary.memories_used ?? []} />
        <DetailList title="Skills" items={detail?.summary.skills_used ?? []} />
        <DetailList title="Plugins" items={detail?.summary.plugins_used ?? []} />
        <DetailList title="MCP" items={detail?.summary.mcp_servers_used ?? []} />

        <section className="mb-4">
          <h2 className="text-sm font-semibold text-slate-200 mb-2">Audit</h2>
          {detail?.audit_logs?.length ? (
            <div className="space-y-2">
              {detail.audit_logs.map(log => (
                <div key={log.id} className="rounded border border-slate-700 bg-slate-900 p-2 text-xs">
                  <span className="text-slate-400">{log.event_type}</span>
                  <span className="mx-2 text-slate-600">|</span>
                  <span className="text-slate-300">{log.summary}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">No audit logs.</p>
          )}
        </section>

        <section>
          <h2 className="text-sm font-semibold text-slate-200 mb-2">Export</h2>
          <div className="flex gap-2">
            <button className="btn-secondary text-xs" onClick={() => handleExport('json')} disabled={exporting === 'json'}>
              Export JSON
            </button>
            <button className="btn-secondary text-xs" onClick={() => handleExport('markdown')} disabled={exporting === 'markdown'}>
              Export Markdown
            </button>
          </div>
        </section>
      </div>

      {/* Resolved approvals (history) */}
      {approvals.filter(a => a.status !== 'pending').length > 0 && (
        <div className="card mb-4">
          <p className="text-sm font-semibold text-slate-300 mb-3">Approval History</p>
          <div className="space-y-2">
            {approvals
              .filter(a => a.status !== 'pending')
              .map(a => (
                <div key={a.id} className="text-xs flex items-center gap-2 text-slate-400">
                  <span className={`font-mono ${a.status === 'approved' ? 'text-green-400' : 'text-red-400'}`}>
                    {a.status === 'approved' ? '✓' : '✗'}
                  </span>
                  <span className="font-mono text-slate-300">{a.tool}</span>
                  <span className="text-slate-500">—</span>
                  <span>{a.status}</span>
                  {a.rejection_reason && (
                    <span className="text-slate-500">({a.rejection_reason})</span>
                  )}
                </div>
              ))}
          </div>
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

function DetailMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950 p-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-300 break-all">{value}</dd>
    </div>
  )
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="mb-4">
      <h2 className="text-sm font-semibold text-slate-200 mb-2">{title}</h2>
      {items.length === 0 ? (
        <p className="text-xs text-slate-500">None recorded.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {items.map(item => (
            <span key={item} className="text-xs rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-300">
              {item}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}

function ApprovalCard({
  approval, rejectReason, onRejectReasonChange, onApprove, onReject, isLoading,
}: {
  approval: ApprovalRequest
  rejectReason: string
  onRejectReasonChange: (v: string) => void
  onApprove: () => void
  onReject: () => void
  isLoading: boolean
}) {
  const [showRejectInput, setShowRejectInput] = useState(false)
  const riskClass = RISK_COLORS[approval.risk_level] ?? RISK_COLORS.medium

  return (
    <div className={`rounded-lg border p-4 ${riskClass}`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm font-semibold">{approval.tool}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded border ${riskClass}`}>
              {approval.risk_level}
            </span>
          </div>
          <p className="text-sm text-slate-300">{approval.summary}</p>
        </div>
        <span className="text-xs text-slate-500 shrink-0">
          {new Date(approval.created_at).toLocaleTimeString()}
        </span>
      </div>

      {Object.keys(approval.arguments).length > 0 && (
        <pre className="text-xs text-slate-400 bg-slate-900/50 rounded p-2 mb-3 overflow-x-auto">
          {JSON.stringify(approval.arguments, null, 2)}
        </pre>
      )}

      {showRejectInput && (
        <div className="mb-3">
          <input
            className="form-input text-sm"
            placeholder="Reason for rejection (optional)"
            value={rejectReason}
            onChange={e => onRejectReasonChange(e.target.value)}
          />
        </div>
      )}

      <div className="flex gap-2">
        <button
          className="btn-primary text-xs py-1 px-3"
          onClick={onApprove}
          disabled={isLoading}
        >
          {isLoading ? 'Processing...' : 'Approve'}
        </button>
        {!showRejectInput ? (
          <button
            className="btn-danger text-xs py-1 px-3"
            onClick={() => setShowRejectInput(true)}
            disabled={isLoading}
          >
            Reject
          </button>
        ) : (
          <button
            className="btn-danger text-xs py-1 px-3"
            onClick={onReject}
            disabled={isLoading}
          >
            Confirm Reject
          </button>
        )}
      </div>
    </div>
  )
}

function EventCard({ event }: { event: ExecutionEvent }) {
  const [expanded, setExpanded] = useState(false)
  const label = EVENT_LABELS[event.type] ?? event.type
  const isError = event.type === 'error' || event.type === 'execution_failed' || event.type === 'tool_failed' || event.type === 'plugin_tool_failed' || event.type === 'mcp_tool_failed'
  const isSuccess = event.type === 'execution_completed' || event.type === 'agent_completed' || event.type === 'tool_executed' || event.type === 'plugin_tool_completed' || event.type === 'mcp_tool_completed'
  const isDenied = event.type === 'tool_call_denied' || event.type === 'approval_rejected' || event.type === 'plugin_disabled_tool_blocked' || event.type === 'mcp_server_disabled_tool_blocked' || event.type === 'mcp_server_not_associated'
  const isApproval = APPROVAL_EVENT_TYPES.has(event.type)
  const isTool = TOOL_EVENT_TYPES.has(event.type)
  const isPluginTool = event.type.startsWith('plugin_')
  const isMcpTool = event.type.startsWith('mcp_')
  const isTeamEvent = TEAM_EVENT_TYPES.has(event.type)
  const isSkillEvent = SKILL_EVENT_TYPES.has(event.type)
  const isAutoApproved = event.type === 'approval_auto_granted'
  const isWaiting = event.type === 'execution_waiting_approval'

  const hasContent = Object.keys(event.content).length > 0

  const borderClass = isError ? 'border-red-500/30 bg-red-500/5'
    : isDenied ? 'border-red-500/30 bg-red-500/5'
    : isWaiting ? 'border-amber-500/40 bg-amber-500/10'
    : isAutoApproved ? 'border-amber-500/20 bg-amber-500/5'
    : isApproval ? 'border-amber-500/20 bg-amber-500/5'
    : isSuccess ? 'border-green-500/30 bg-green-500/5'
    : isSkillEvent ? 'border-blue-500/20 bg-blue-500/5'
    : isMcpTool ? 'border-cyan-500/20 bg-cyan-500/5'
    : isTeamEvent ? 'border-cyan-500/20 bg-cyan-500/5'
    : isPluginTool ? 'border-fuchsia-500/20 bg-fuchsia-500/5'
    : isTool ? 'border-purple-500/20 bg-purple-500/5'
    : 'border-slate-700 bg-slate-800/50'

  const labelClass = isError ? 'text-red-300'
    : isDenied ? 'text-red-300'
    : isWaiting ? 'text-amber-300 font-semibold'
    : isAutoApproved ? 'text-amber-300'
    : isApproval ? 'text-amber-300'
    : isSuccess ? 'text-green-300'
    : isSkillEvent ? 'text-blue-300'
    : isMcpTool ? 'text-cyan-300'
    : isTeamEvent ? 'text-cyan-300'
    : isPluginTool ? 'text-fuchsia-300'
    : isTool ? 'text-purple-300'
    : 'text-slate-300'

  const toolName = (event.content.tool as string | undefined)

  return (
    <div className={`rounded-md border px-3 py-2 text-xs ${borderClass}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          {isWaiting && <span>⏸</span>}
          {isAutoApproved && <span>⚡</span>}
          {event.type === 'approval_approved' && <span>✓</span>}
          {isDenied && <span>✗</span>}
          {isTeamEvent && <span className="text-cyan-400">Team</span>}
          {isPluginTool && <span className="text-fuchsia-400">Plugin</span>}
          {isMcpTool && <span className="text-cyan-400">MCP</span>}
          <span className={`font-medium ${labelClass}`}>{label}</span>
          {toolName && (
            <span className="font-mono text-purple-400/70 text-xs">{toolName}</span>
          )}
          {(event.content.risk_level as string | undefined) && (
            <span className={`text-xs px-1 rounded border ${RISK_COLORS[(event.content.risk_level as string)] ?? ''}`}>
              {event.content.risk_level as string}
            </span>
          )}
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
