import { describe, it, expect } from 'vitest'
import { groupTurnEvents, groupTeamEvents, stripProtocolJson } from '../lib/groupEvents'
import type { ExecutionEvent } from '../types/domain'

function ev(partial: Partial<ExecutionEvent> & { type: string; content?: Record<string, unknown> }): ExecutionEvent {
  return {
    id: partial.id ?? Math.random().toString(36).slice(2),
    execution_id: 'exec_1',
    type: partial.type as ExecutionEvent['type'],
    source: partial.source ?? 'runtime',
    source_id: partial.source_id ?? 'agent_1',
    content: partial.content ?? {},
    created_at: '2026-06-21T00:00:00',
  }
}

describe('groupTurnEvents', () => {
  it('joins model_chunk deltas into the answer', () => {
    const view = groupTurnEvents([
      ev({ type: 'model_chunk', content: { delta: 'Hello ' } }),
      ev({ type: 'model_chunk', content: { delta: 'world' } }),
    ])
    expect(view.answer).toBe('Hello world')
  })

  it('prefers the final agent_completed result over streamed text', () => {
    const view = groupTurnEvents([
      ev({ type: 'model_chunk', content: { delta: 'partial' } }),
      ev({ type: 'agent_completed', content: { result: 'final answer' } }),
    ])
    expect(view.answer).toBe('final answer')
  })

  it('collects reasoning into thinking', () => {
    const view = groupTurnEvents([
      ev({ type: 'model_reasoning_chunk', content: { delta: 'let me ' } }),
      ev({ type: 'model_reasoning_chunk', content: { delta: 'think' } }),
    ])
    expect(view.thinking).toBe('let me think')
  })

  it('groups a tool call lifecycle into one tool card', () => {
    const view = groupTurnEvents([
      ev({ id: 't1', type: 'tool_call_requested', content: { tool: 'read_file', arguments: { path: 'a.txt' } } }),
      ev({ type: 'tool_call_validated', content: { tool: 'read_file' } }),
      ev({ type: 'tool_executed', content: { tool: 'read_file', status: 'success' } }),
      ev({ type: 'tool_result', content: { tool: 'read_file', result_preview: 'file contents' } }),
    ])
    expect(view.toolCalls).toHaveLength(1)
    expect(view.toolCalls[0]).toMatchObject({
      tool: 'read_file',
      status: 'success',
      resultPreview: 'file contents',
      args: { path: 'a.txt' },
    })
  })

  it('does not show streamed tool-call JSON as the assistant answer', () => {
    const view = groupTurnEvents([
      ev({ type: 'model_chunk', content: { delta: '{"type": "tool_call", "tool": "http.request"}' } }),
      ev({ id: 't1', type: 'tool_call_requested', content: { tool: 'http.request', arguments: { url: 'https://example.com' } } }),
      ev({ type: 'tool_call_validated', content: { tool: 'http.request' } }),
    ])

    expect(view.answer).toBe('')
    expect(view.toolCalls).toHaveLength(1)
  })

  it('surfaces narration prose around tool-call JSON while the turn streams', () => {
    const view = groupTurnEvents([
      ev({ type: 'model_chunk', content: { delta: 'Vou explorar o ambiente. 🚀' } }),
      ev({ type: 'model_chunk', content: { delta: '{"type": "tool_calls", "calls": [{"id":"c1","tool":"workspace.list","arguments":{}}]}' } }),
      ev({ id: 't1', type: 'tool_call_requested', content: { id: 'c1', tool: 'workspace.list' } }),
    ])
    expect(view.answer).toBe('Vou explorar o ambiente. 🚀')
    expect(view.toolCalls).toHaveLength(1)
  })

  it('marks failed tool calls', () => {
    const view = groupTurnEvents([
      ev({ type: 'tool_call_requested', content: { tool: 'write_file' } }),
      ev({ type: 'tool_failed', content: { tool: 'write_file', error: 'denied path' } }),
    ])
    expect(view.toolCalls[0].status).toBe('failed')
    expect(view.toolCalls[0].error).toBe('denied path')
  })

  it('exposes pending approvals and clears them after resolution', () => {
    const pending = groupTurnEvents([
      ev({
        type: 'approval_requested',
        content: {
          approval_id: 'approval_1',
          tool: 'http.request',
          arguments: { url: 'https://example.com' },
          risk_level: 'medium',
          summary: 'Make an HTTP request',
        },
      }),
      ev({ type: 'execution_waiting_approval', content: { approval_id: 'approval_1' } }),
    ])

    expect(pending.pendingApproval).toMatchObject({
      approvalId: 'approval_1',
      tool: 'http.request',
      args: { url: 'https://example.com' },
      riskLevel: 'medium',
      summary: 'Make an HTTP request',
    })

    const resolved = groupTurnEvents([
      ev({ type: 'approval_requested', content: { approval_id: 'approval_1', tool: 'http.request' } }),
      ev({ type: 'approval_approved', content: { approval_id: 'approval_1' } }),
    ])

    expect(resolved.pendingApproval).toBeUndefined()
  })

  it('matches duplicate tool lifecycle events by call id', () => {
    const view = groupTurnEvents([
      ev({ type: 'tool_call_requested', content: { id: 'call_1', tool: 'http.request' } }),
      ev({ type: 'tool_call_requested', content: { id: 'call_2', tool: 'http.request' } }),
      ev({ type: 'tool_executed', content: { id: 'call_1', tool: 'http.request' } }),
      ev({ type: 'tool_failed', content: { id: 'call_2', tool: 'http.request', error: 'boom' } }),
    ])

    expect(view.toolCalls).toHaveLength(2)
    expect(view.toolCalls[0]).toMatchObject({ id: 'call_1', status: 'success' })
    expect(view.toolCalls[1]).toMatchObject({ id: 'call_2', status: 'failed', error: 'boom' })
  })

  it('captures turn-level errors', () => {
    const view = groupTurnEvents([
      ev({ type: 'execution_failed', content: { error: 'boom' } }),
    ])
    expect(view.error).toBe('boom')
  })
})

describe('stripProtocolJson', () => {
  it('keeps plain prose untouched', () => {
    expect(stripProtocolJson('Hello world')).toBe('Hello world')
  })

  it('drops complete protocol JSON objects, keeping prose', () => {
    expect(
      stripProtocolJson('Vou criar.{"type":"tool_call","tool":"filesystem.write","arguments":{}}'),
    ).toBe('Vou criar.')
  })

  it('drops a truncated trailing protocol object', () => {
    expect(
      stripProtocolJson('Já mapeei.{"type":"tool_calls","calls":[{"tool":"filesystem.write","arguments":{"content":"<html'),
    ).toBe('Já mapeei.')
  })

  it('preserves braces inside JSON string values', () => {
    expect(
      stripProtocolJson('{"type":"final_answer","content":"use {x} here"}after'),
    ).toBe('after')
  })
})

describe('groupTeamEvents', () => {
  it('groups member contributions by agent id', () => {
    const members = groupTeamEvents([
      ev({ type: 'subagent_call_requested', content: { target_agent_id: 'agent_analyst', task: 'collect data' } }),
      ev({ type: 'subagent_started', source_id: 'agent_analyst' }),
      ev({ type: 'subagent_completed', source_id: 'agent_analyst', content: { result: 'data ready' } }),
    ])
    expect(members).toHaveLength(1)
    expect(members[0]).toMatchObject({
      agentId: 'agent_analyst',
      task: 'collect data',
      result: 'data ready',
      status: 'completed',
    })
  })

  it('tracks multiple members and a failure', () => {
    const members = groupTeamEvents([
      ev({ type: 'subagent_call_requested', content: { target_agent_id: 'a1', task: 't1' } }),
      ev({ type: 'subagent_call_requested', content: { target_agent_id: 'a2', task: 't2' } }),
      ev({ type: 'subagent_failed', source_id: 'a2', content: { error: 'nope' } }),
    ])
    expect(members.map(m => m.agentId)).toEqual(['a1', 'a2'])
    expect(members[1].status).toBe('failed')
    expect(members[1].error).toBe('nope')
  })

  it('returns nothing for a non-team turn', () => {
    expect(groupTeamEvents([ev({ type: 'agent_completed', content: { result: 'x' } })])).toEqual([])
  })
})
