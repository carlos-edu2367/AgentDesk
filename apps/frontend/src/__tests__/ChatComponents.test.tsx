import { describe, it, expect } from 'vitest'
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
