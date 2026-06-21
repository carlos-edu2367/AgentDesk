import type { ExecutionEvent } from '../../types/domain'
import { groupTurnEvents } from '../../lib/groupEvents'
import { Markdown } from './Markdown'
import { ThinkingBlock } from './ThinkingBlock'
import { ToolCallChain } from './ToolCallChain'

/**
 * Renders one assistant turn: the tool-call chain and thinking trace (the
 * "how"), followed by the formatted markdown answer (the "what"). Falls back to
 * an explicit result string when events haven't streamed yet (loaded history).
 */
export function AssistantTurn({
  events,
  fallbackResult,
  pending,
}: {
  events: ExecutionEvent[]
  fallbackResult?: string | null
  pending?: boolean
}) {
  const view = groupTurnEvents(events)
  const answer = view.answer || fallbackResult || ''

  return (
    <div className="self-start max-w-[85%] rounded-lg rounded-bl-sm border border-slate-700 bg-slate-800/60 px-3 py-2">
      <ToolCallChain toolCalls={view.toolCalls} />
      <ThinkingBlock thinking={view.thinking} />

      {view.error ? (
        <p className="text-sm text-red-300 whitespace-pre-wrap mt-2">{view.error}</p>
      ) : answer ? (
        <div className="mt-2">
          <Markdown>{answer}</Markdown>
        </div>
      ) : pending ? (
        <p className="text-xs text-slate-500 mt-2 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
          Thinking…
        </p>
      ) : null}
    </div>
  )
}
