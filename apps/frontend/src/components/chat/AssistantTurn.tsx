import type { ExecutionEvent } from '../../types/domain'
import { groupTurnEvents, groupTeamEvents } from '../../lib/groupEvents'
import { Markdown } from './Markdown'
import { ThinkingBlock } from './ThinkingBlock'
import { ToolCallChain } from './ToolCallChain'
import { TeamSubThread } from './TeamSubThread'

/**
 * Renders one assistant turn: the tool-call chain and thinking trace (the
 * "how"), followed by the formatted markdown answer (the "what"). Falls back to
 * an explicit result string when events haven't streamed yet (loaded history).
 */
export function AssistantTurn({
  events,
  fallbackResult,
  pending,
  onResolveApproval,
  resolvingApprovalId,
}: {
  events: ExecutionEvent[]
  fallbackResult?: string | null
  pending?: boolean
  onResolveApproval?: (approvalId: string, approved: boolean) => void
  resolvingApprovalId?: string | null
}) {
  const view = groupTurnEvents(events)
  const teamMembers = groupTeamEvents(events)
  const answer = view.answer || fallbackResult || ''
  const approval = view.pendingApproval
  const approvalBusy = approval ? resolvingApprovalId === approval.approvalId : false

  return (
    <div className="self-start max-w-[85%] rounded-lg rounded-bl-sm border border-slate-700 bg-slate-800/60 px-3 py-2">
      <TeamSubThread members={teamMembers} />
      <ToolCallChain toolCalls={view.toolCalls} />
      <ThinkingBlock thinking={view.thinking} />

      {approval && onResolveApproval && (
        <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-amber-200">Approval required</p>
              <p className="mt-1 break-all font-mono text-xs text-slate-300">{approval.tool}</p>
              {approval.summary && (
                <p className="mt-1 text-xs text-slate-400">{approval.summary}</p>
              )}
              {approval.riskLevel && (
                <p className="mt-2 text-[11px] uppercase tracking-wide text-amber-300/80">
                  Risk: {approval.riskLevel}
                </p>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                className="btn-ghost text-xs"
                aria-label="Reject tool call"
                disabled={approvalBusy}
                onClick={() => onResolveApproval(approval.approvalId, false)}
              >
                Reject
              </button>
              <button
                type="button"
                className="btn-primary text-xs"
                aria-label="Approve tool call"
                disabled={approvalBusy}
                onClick={() => onResolveApproval(approval.approvalId, true)}
              >
                Approve
              </button>
            </div>
          </div>
        </div>
      )}

      {view.notices.map((notice, i) => (
        <p
          key={i}
          className="text-xs text-amber-300/90 bg-amber-500/10 border border-amber-500/20 rounded-md px-2 py-1.5 mt-2 flex items-start gap-2"
        >
          <span aria-hidden>⚠️</span>
          <span>{notice}</span>
        </p>
      ))}
      {view.error && (
        <p className="text-sm text-red-300 whitespace-pre-wrap mt-2">{view.error}</p>
      )}
      {!view.error && answer && (
        <div className="mt-2">
          <Markdown>{answer}</Markdown>
        </div>
      )}
      {!view.error && pending && (
        // Keep a live "working" indicator visible for the whole turn so long
        // gaps (e.g. the model generating a big file inline) don't look frozen.
        <p className="text-xs text-slate-500 mt-2 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
          {answer || view.toolCalls.length > 0 ? 'Working…' : 'Thinking…'}
        </p>
      )}
    </div>
  )
}
