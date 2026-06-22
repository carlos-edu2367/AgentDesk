import type { ExecutionEvent } from '../types/domain'

export type ToolCallStatus = 'requested' | 'validated' | 'success' | 'failed' | 'denied'

export interface ToolCallView {
  /** Stable key for rendering. */
  key: string
  id?: string
  tool: string
  args?: Record<string, unknown>
  resultPreview?: string
  error?: string
  status: ToolCallStatus
}

export interface ApprovalView {
  approvalId: string
  tool: string
  args?: Record<string, unknown>
  riskLevel?: string
  summary?: string
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
  /** Pending approval requested by the backend, if this turn is paused. */
  pendingApproval?: ApprovalView
  /** Non-fatal notices to surface inline (e.g. an output-truncation retry). */
  notices: string[]
  /** Error message if the turn failed. */
  error?: string
}

const TOOL_REQUEST_TYPES = new Set([
  'tool_call_requested',
  'plugin_tool_call_requested',
  'mcp_tool_call_requested',
])

// Matches the canonical protocol openers plus the deviations smaller models
// emit: the tool name collapsed into `type` ({"type":"filesystem.write",…}) or a
// bare {"tool":"filesystem.write",…} with no type. Dotted names are our
// tool-naming convention, mirroring the backend parser's leniency.
const PROTOCOL_OPENER = /\{\s*"type"\s*:\s*"(tool_call|tool_calls|final_answer|subagent_call|[a-z_]+\.[a-z_.]+)"|\{\s*"tool"\s*:\s*"[a-z_]+\.[a-z_.]+"/

/**
 * Removes AgentDesk protocol JSON objects from streamed model text, leaving the
 * model's natural-language narration (e.g. "Vou explorar o ambiente…"). The model
 * is told to answer in JSON only, but in practice it often prefixes prose before
 * the tool-call JSON. Without this we'd render raw `{"type":"tool_calls",…}` in
 * the chat bubble (and a truncated trailing object too).
 */
export function stripProtocolJson(text: string): string {
  if (!text) return ''
  let out = ''
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (ch === '{') {
      // Walk a balanced JSON object, respecting strings/escapes.
      let depth = 0
      let inString = false
      let escape = false
      let j = i
      for (; j < text.length; j++) {
        const c = text[j]
        if (inString) {
          if (escape) escape = false
          else if (c === '\\') escape = true
          else if (c === '"') inString = false
          continue
        }
        if (c === '"') inString = true
        else if (c === '{') depth++
        else if (c === '}') {
          depth--
          if (depth === 0) break
        }
      }
      const block = text.slice(i, j < text.length ? j + 1 : j)
      const unterminated = depth > 0 // ran off the end (truncated object)
      if (PROTOCOL_OPENER.test(block)) {
        // Drop protocol JSON (complete or truncated) from the narration.
        i = j < text.length ? j + 1 : text.length
        continue
      }
      if (unterminated) {
        // Non-protocol unterminated brace — keep as-is and stop scanning.
        out += text.slice(i)
        break
      }
      out += block
      i = j + 1
      continue
    }
    out += ch
    i++
  }
  return out.trim()
}

function toolName(ev: ExecutionEvent): string {
  return (ev.content?.tool as string | undefined) ?? 'tool'
}

function eventCallId(ev: ExecutionEvent): string | undefined {
  return (ev.content?.id as string | undefined) ?? (ev.content?.call_id as string | undefined)
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
  const notices: string[] = []
  const approvals = new Map<string, ApprovalView>()

  const openCallFor = (ev: ExecutionEvent): ToolCallView | undefined => {
    const id = eventCallId(ev)
    const name = toolName(ev)
    for (let i = toolCalls.length - 1; i >= 0; i--) {
      if (
        (id ? toolCalls[i].id === id : toolCalls[i].tool === name) &&
        toolCalls[i].status !== 'success' &&
        toolCalls[i].status !== 'failed' &&
        toolCalls[i].status !== 'denied'
      ) {
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
    if (type === 'model_output_truncated') {
      const attempt = (c.attempt as number | undefined) ?? notices.length + 1
      const max = (c.max_retries as number | undefined) ?? 0
      notices.push(
        `A resposta passou do limite de tokens (max_tokens) antes de fechar a chamada — ` +
        `tentando de novo (${attempt}/${max}), pedindo para dividir em partes menores.`,
      )
      return
    }

    if (TOOL_REQUEST_TYPES.has(type)) {
      toolCalls.push({
        key: `${ev.id || idx}`,
        id: eventCallId(ev),
        tool: toolName(ev),
        args: (c.arguments as Record<string, unknown>) ?? undefined,
        status: 'requested',
      })
      return
    }
    if (type === 'tool_call_validated') {
      const call = openCallFor(ev)
      if (call) call.status = 'validated'
      return
    }
    if (type === 'tool_executed' || type === 'plugin_tool_completed' || type === 'mcp_tool_completed') {
      const call = openCallFor(ev)
      if (call) call.status = 'success'
      return
    }
    if (type === 'tool_result') {
      const call = openCallFor(ev) ?? toolCalls[toolCalls.length - 1]
      if (call) call.resultPreview = (c.result_preview as string) ?? call.resultPreview
      return
    }
    if (type === 'tool_failed' || type === 'plugin_tool_failed' || type === 'mcp_tool_failed') {
      const call = openCallFor(ev)
      if (call) {
        call.status = 'failed'
        call.error = (c.error as string) ?? call.error
      }
      return
    }
    if (type === 'tool_call_denied') {
      const call = openCallFor(ev)
      if (call) {
        call.status = 'denied'
        call.error = (c.error as string) ?? call.error
      }
      return
    }
    if (type === 'approval_requested' || type === 'execution_waiting_approval') {
      const approvalId = (c.approval_id as string | undefined) ?? ''
      if (!approvalId) return
      const current = approvals.get(approvalId)
      approvals.set(approvalId, {
        approvalId,
        tool: (c.tool as string | undefined) ?? current?.tool ?? 'tool',
        args: (c.arguments as Record<string, unknown> | undefined) ?? current?.args,
        riskLevel: (c.risk_level as string | undefined) ?? current?.riskLevel,
        summary: (c.summary as string | undefined) ?? current?.summary,
      })
      return
    }
    if (type === 'approval_approved' || type === 'approval_rejected') {
      const approvalId = (c.approval_id as string | undefined) ?? ''
      if (approvalId) approvals.delete(approvalId)
      return
    }
  })

  return {
    // Prefer the clean parsed answer (from agent_completed). While the turn is
    // still streaming, show the model's narration with protocol JSON stripped so
    // tool-using turns surface progress text live instead of staying blank until
    // completion (and never render raw `{"type":...}` JSON).
    answer: finalAnswer || stripProtocolJson(streamed),
    thinking,
    toolCalls,
    notices,
    pendingApproval: Array.from(approvals.values())[0],
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
