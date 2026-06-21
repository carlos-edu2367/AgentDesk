import { describe, it, expect } from 'vitest'
import { groupTurnEvents, groupTeamEvents } from '../lib/groupEvents'
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

  it('marks failed tool calls', () => {
    const view = groupTurnEvents([
      ev({ type: 'tool_call_requested', content: { tool: 'write_file' } }),
      ev({ type: 'tool_failed', content: { tool: 'write_file', error: 'denied path' } }),
    ])
    expect(view.toolCalls[0].status).toBe('failed')
    expect(view.toolCalls[0].error).toBe('denied path')
  })

  it('captures turn-level errors', () => {
    const view = groupTurnEvents([
      ev({ type: 'execution_failed', content: { error: 'boom' } }),
    ])
    expect(view.error).toBe('boom')
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
