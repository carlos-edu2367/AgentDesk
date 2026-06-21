import type { ExecutionEvent } from '../types/domain'

export type ToolCallStatus = 'requested' | 'validated' | 'success' | 'failed' | 'denied'

export interface ToolCallView {
  /** Stable key for rendering. */
  key: string
  tool: string
  args?: Record<string, unknown>
  resultPreview?: string
  error?: string
  status: ToolCallStatus
}

export type TeamMemberStatus = 'assigned' | 'running' | 'completed' | 'failed'

export interface TeamMemberView {
  agentId: string
  task?: string
  result?: string
  error?: string
  status: TeamMemberStatus
}

export interface TurnView {
  /** Streamed/finalized assistant answer (markdown). */
  answer: string
  /** Concatenated model reasoning tokens, when the model emits them. */
  thinking: string
  /** Ordered chain of tool calls made during the turn. */
  toolCalls: ToolCallView[]
  /** Error message if the turn failed. */
  error?: string
}

const TOOL_REQUEST_TYPES = new Set([
  'tool_call_requested',
  'plugin_tool_call_requested',
  'mcp_tool_call_requested',
])

function toolName(ev: ExecutionEvent): string {
  return (ev.content?.tool as string | undefined) ?? 'tool'
}

/**
 * Folds the raw event stream of a single turn into a chat-friendly view:
 * the assistant answer, the thinking trace, and the ordered tool-call chain.
 * Pure function — safe to unit test and call on every render.
 */
export function groupTurnEvents(events: ExecutionEvent[]): TurnView {
  let streamed = ''
  let finalAnswer = ''
  let thinking = ''
  let error: string | undefined
  const toolCalls: ToolCallView[] = []

  const openCallFor = (name: string): ToolCallView | undefined => {
    for (let i = toolCalls.length - 1; i >= 0; i--) {
      if (toolCalls[i].tool === name && toolCalls[i].status !== 'success' && toolCalls[i].status !== 'failed' && toolCalls[i].status !== 'denied') {
        return toolCalls[i]
      }
    }
    return undefined
  }

  events.forEach((ev, idx) => {
    const c = ev.content ?? {}
    const type = ev.type

    if (type === 'model_chunk') {
      streamed += (c.delta as string) ?? ''
      return
    }
    if (type === 'model_reasoning_chunk') {
      thinking += (c.delta as string) ?? ''
      return
    }
    if (type === 'agent_completed') {
      finalAnswer = (c.result as string) ?? finalAnswer
      return
    }
    if (type === 'execution_failed' || type === 'error' || type === 'team_failed') {
      error = (c.error as string) ?? error
      return
    }

    if (TOOL_REQUEST_TYPES.has(type)) {
      toolCalls.push({
        key: `${ev.id || idx}`,
        tool: toolName(ev),
        args: (c.arguments as Record<string, unknown>) ?? undefined,
        status: 'requested',
      })
      return
    }
    if (type === 'tool_call_validated') {
      const call = openCallFor(toolName(ev))
      if (call) call.status = 'validated'
      return
    }
    if (type === 'tool_executed' || type === 'plugin_tool_completed' || type === 'mcp_tool_completed') {
      const call = openCallFor(toolName(ev))
      if (call) call.status = 'success'
      return
    }
    if (type === 'tool_result') {
      const call = openCallFor(toolName(ev)) ?? toolCalls[toolCalls.length - 1]
      if (call) call.resultPreview = (c.result_preview as string) ?? call.resultPreview
      return
    }
    if (type === 'tool_failed' || type === 'plugin_tool_failed' || type === 'mcp_tool_failed') {
      const call = openCallFor(toolName(ev))
      if (call) {
        call.status = 'failed'
        call.error = (c.error as string) ?? call.error
      }
      return
    }
    if (type === 'tool_call_denied') {
      const call = openCallFor(toolName(ev))
      if (call) {
        call.status = 'denied'
        call.error = (c.error as string) ?? call.error
      }
      return
    }
  })

  return {
    answer: finalAnswer || (toolCalls.length > 0 ? '' : streamed),
    thinking,
    toolCalls,
    error,
  }
}

/**
 * Extracts per-member contributions from a team turn's events, keyed by the
 * member agent id and ordered by first appearance. Powers the leader's nested
 * sub-thread (design decision A).
 */
export function groupTeamEvents(events: ExecutionEvent[]): TeamMemberView[] {
  const byId = new Map<string, TeamMemberView>()

  const ensure = (agentId: string): TeamMemberView => {
    let m = byId.get(agentId)
    if (!m) {
      m = { agentId, status: 'assigned' }
      byId.set(agentId, m)
    }
    return m
  }

  for (const ev of events) {
    const c = ev.content ?? {}
    switch (ev.type) {
      case 'subagent_call_requested': {
        const id = (c.target_agent_id as string) ?? ''
        if (id) ensure(id).task = (c.task as string) ?? undefined
        break
      }
      case 'member_assigned': {
        const id = (c.member_agent_id as string) ?? ''
        if (id) ensure(id).task = (c.task as string) ?? ensure(id).task
        break
      }
      case 'subagent_started':
      case 'member_started':
        if (ev.source_id) ensure(ev.source_id).status = 'running'
        break
      case 'subagent_completed':
      case 'member_completed':
        if (ev.source_id) {
          const m = ensure(ev.source_id)
          m.status = 'completed'
          m.result = (c.result as string) ?? m.result
        }
        break
      case 'subagent_failed':
      case 'member_failed':
        if (ev.source_id) {
          const m = ensure(ev.source_id)
          m.status = 'failed'
          m.error = (c.error as string) ?? m.error
        }
        break
    }
  }

  return Array.from(byId.values())
}
