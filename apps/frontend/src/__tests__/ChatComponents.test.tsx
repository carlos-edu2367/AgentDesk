import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AssistantTurn } from '../components/chat/AssistantTurn'
import { ChatThread } from '../components/chat/ChatThread'
import { LogsDrawer } from '../components/chat/LogsDrawer'
import type { ExecutionEvent } from '../types/domain'

function ev(type: string, content: Record<string, unknown> = {}, id?: string): ExecutionEvent {
  return {
    id: id ?? Math.random().toString(36).slice(2),
    execution_id: 'e1',
    type: type as ExecutionEvent['type'],
    source: 'runtime',
    source_id: 'agent_1',
    content,
    created_at: '2026-06-21T00:00:00',
  }
}

describe('AssistantTurn', () => {
  it('renders the markdown answer', () => {
    render(<AssistantTurn events={[ev('agent_completed', { result: '# Done' })]} />)
    expect(screen.getByRole('heading', { name: 'Done' })).toBeInTheDocument()
  })

  it('does not render protocol markup from fallback results', () => {
    render(
      <AssistantTurn
        events={[]}
        fallbackResult={
          'Vou ler os arquivos.<tool_calls>{"calls":[{"id":"read","tool":"filesystem.read","arguments":{"path":"a.js"}}]}</code></pre>'
        }
      />,
    )

    expect(screen.getByText('Vou ler os arquivos.')).toBeInTheDocument()
    expect(screen.queryByText(/tool_calls/)).not.toBeInTheDocument()
  })

  it('hides thinking by default and reveals it on click', () => {
    render(<AssistantTurn events={[ev('model_reasoning_chunk', { delta: 'secret reasoning' })]} />)
    expect(screen.queryByText('secret reasoning')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Thinking'))
    expect(screen.getByText('secret reasoning')).toBeInTheDocument()
  })

  it('renders a tool call card', () => {
    render(
      <AssistantTurn
        events={[
          ev('tool_call_requested', { tool: 'read_file', arguments: { p: 1 } }, 't1'),
          ev('tool_executed', { tool: 'read_file' }),
        ]}
      />,
    )
    expect(screen.getByText('read_file')).toBeInTheDocument()
  })

  it('renders narration and tool calls inline, with the final answer below', () => {
    render(
      <AssistantTurn
        events={[
          ev('model_chunk', { delta: 'Vou buscar na web.' }),
          ev('model_chunk', { delta: '{"type":"tool_call","tool":"web.search"}' }),
          ev('tool_call_requested', { tool: 'web.search' }, 't1'),
          ev('tool_executed', { tool: 'web.search' }),
          ev('model_chunk', { delta: 'Encontrei as informações.' }),
          ev('agent_completed', { result: 'Resposta final.' }),
        ]}
      />,
    )
    expect(screen.getByText('Vou buscar na web.')).toBeInTheDocument()
    expect(screen.getByText('web.search')).toBeInTheDocument()
    expect(screen.getByText('Encontrei as informações.')).toBeInTheDocument()
    expect(screen.getByText('Resposta final.')).toBeInTheDocument()
  })

  it('renders inline approval controls when a tool is waiting for approval', () => {
    const onResolveApproval = vi.fn()
    render(
      <AssistantTurn
        events={[
          ev('approval_requested', {
            approval_id: 'approval_1',
            tool: 'http.request',
            arguments: { url: 'https://example.com' },
            risk_level: 'medium',
            summary: 'Make an HTTP request',
          }),
          ev('execution_waiting_approval', { approval_id: 'approval_1' }),
        ]}
        onResolveApproval={onResolveApproval}
      />,
    )

    expect(screen.getByText('Approval required')).toBeInTheDocument()
    expect(screen.getByText('http.request')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Approve tool call' }))
    expect(onResolveApproval).toHaveBeenCalledWith('approval_1', true)
  })

  it('renders a collapsed team sub-thread for team turns', () => {
    render(
      <AssistantTurn
        events={[
          ev('subagent_call_requested', { target_agent_id: 'agent_analyst', task: 'collect' }),
        ]}
      />,
    )
    // The sub-thread toggle is present, collapsed by default.
    expect(screen.getByText(/Team worked on this/)).toBeInTheDocument()
    expect(screen.queryByText('agent_analyst')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText(/Team worked on this/))
    expect(screen.getByText('agent_analyst')).toBeInTheDocument()
  })
})

describe('ChatThread', () => {
  it('renders user input and assistant answer for each turn', () => {
    render(
      <ChatThread
        turns={[
          { id: 'e1', userInput: 'Hi there', events: [ev('agent_completed', { result: 'Hello!' })] },
        ]}
      />,
    )
    expect(screen.getByText('Hi there')).toBeInTheDocument()
    expect(screen.getByText('Hello!')).toBeInTheDocument()
  })

  it('passes inline approval resolution with the turn execution id', () => {
    const onResolveApproval = vi.fn()
    render(
      <ChatThread
        turns={[
          {
            id: 'exec_1',
            userInput: 'Research',
            events: [
              ev('approval_requested', { approval_id: 'approval_1', tool: 'http.request' }),
              ev('execution_waiting_approval', { approval_id: 'approval_1' }),
            ],
          },
        ]}
        onResolveApproval={onResolveApproval}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Approve tool call' }))
    expect(onResolveApproval).toHaveBeenCalledWith('exec_1', 'approval_1', true)
  })

  it('shows an empty prompt when there are no turns', () => {
    render(<ChatThread turns={[]} />)
    expect(screen.getByText(/Send a message to start/)).toBeInTheDocument()
  })
})

describe('LogsDrawer', () => {
  it('renders a toggle button when closed', () => {
    render(<LogsDrawer events={[]} open={false} onToggle={() => {}} />)
    expect(screen.getByLabelText('Open logs')).toBeInTheDocument()
  })

  it('renders event types when open', () => {
    render(<LogsDrawer events={[ev('execution_started')]} open onToggle={() => {}} />)
    expect(screen.getByText('execution_started')).toBeInTheDocument()
  })
})
