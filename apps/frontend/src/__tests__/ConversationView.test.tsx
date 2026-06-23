import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ConversationView } from '../views/ConversationView'

const sendMessage = vi.fn()
const get = vi.fn()
const list = vi.fn()
const create = vi.fn()
const update = vi.fn()
const resolveApproval = vi.fn()
const workspacesList = vi.fn()
const cancelExecution = vi.fn()

vi.mock('../api/conversations', () => ({
  conversationsApi: {
    get: (...args: unknown[]) => get(...args),
    sendMessage: (...args: unknown[]) => sendMessage(...args),
    list: (...args: unknown[]) => list(...args),
    create: (...args: unknown[]) => create(...args),
    update: (...args: unknown[]) => update(...args),
  },
}))

vi.mock('../api/workspaces', () => ({
  workspacesApi: {
    list: (...args: unknown[]) => workspacesList(...args),
  },
}))

vi.mock('../api/approvals', () => ({
  approvalsApi: {
    resolve: (...args: unknown[]) => resolveApproval(...args),
  },
}))

vi.mock('../api/executions', () => ({
  executionsApi: {
    cancel: (...args: unknown[]) => cancelExecution(...args),
  },
}))

// Avoid opening real EventSource connections in jsdom; let tests drive the
// hook's return value to simulate streaming.
let hookReturn: { events: unknown[]; connectionStatus: string } = { events: [], connectionStatus: 'closed' }
vi.mock('../hooks/useExecutionEvents', () => ({
  useExecutionEvents: () => hookReturn,
}))

function ev(execution_id: string, type: string, content: Record<string, unknown> = {}) {
  return {
    id: Math.random().toString(36).slice(2),
    execution_id,
    type,
    source: 'runtime',
    source_id: 'agent_1',
    content,
    created_at: '2026-06-21T00:00:00',
  }
}

function renderAt(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/conversations/${id}`]}>
      <Routes>
        <Route path="/conversations/:id" element={<ConversationView />} />
      </Routes>
    </MemoryRouter>,
  )
}

const baseDetail = {
  conversation: { id: 'conv_1', type: 'agent', target_id: 'agent_1', title: 'Researcher', workspace_ids: [], created_at: '', updated_at: '' },
  turns: [],
}

describe('ConversationView', () => {
  beforeEach(() => {
    get.mockReset()
    sendMessage.mockReset()
    resolveApproval.mockReset()
    list.mockReset()
    create.mockReset()
    update.mockReset()
    workspacesList.mockReset()
    cancelExecution.mockReset()
    cancelExecution.mockResolvedValue({ status: 'cancelled' })
    hookReturn = { events: [], connectionStatus: 'closed' }
    get.mockResolvedValue(baseDetail)
    sendMessage.mockResolvedValue({ execution_id: 'exec_new', conversation_id: 'conv_1', status: 'running' })
    resolveApproval.mockResolvedValue({ status: 'approved' })
    list.mockResolvedValue([])
    create.mockResolvedValue({ id: 'conv_new' })
    update.mockResolvedValue({})
    workspacesList.mockResolvedValue([])
  })

  it('renders the conversation title', async () => {
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByText('Researcher')).toBeInTheDocument())
  })

  it('does not render a conversation history rail inside the chat view', async () => {
    list.mockResolvedValue([
      {
        id: 'conv_2',
        type: 'agent',
        target_id: 'agent_1',
        title: 'Older chat',
        workspace_ids: [],
        created_at: '',
        updated_at: '',
      },
    ])

    renderAt('conv_1')

    await waitFor(() => expect(screen.getByText('Researcher')).toBeInTheDocument())
    expect(list).not.toHaveBeenCalled()
    expect(screen.queryByText('Older chat')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '+ New chat' })).not.toBeInTheDocument()
  })

  it('sends chat messages with manual approval by default', async () => {
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Hello agent' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(sendMessage).toHaveBeenCalledWith('conv_1', {
      message: 'Hello agent',
      stream: true,
      approval_mode: 'manual',
      workspace_ids: [],
      max_steps: null,
    }))
  })

  it('can switch to auto-approval via the checkbox', async () => {
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-approval' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Research with tools' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(sendMessage).toHaveBeenCalledWith('conv_1', {
      message: 'Research with tools',
      stream: true,
      approval_mode: 'auto',
      workspace_ids: [],
      max_steps: null,
    }))
  })

  it('resolves approvals inline from the active chat turn', async () => {
    hookReturn = {
      connectionStatus: 'open',
      events: [
        ev('exec_new', 'approval_requested', { approval_id: 'approval_1', tool: 'http.request' }),
        ev('exec_new', 'execution_waiting_approval', { approval_id: 'approval_1' }),
      ],
    }
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByText('Approval required')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Approve tool call' }))

    await waitFor(() => expect(resolveApproval).toHaveBeenCalledWith('exec_new', 'approval_1', true, undefined, 'manual'))
  })

  it('streams the live answer and does not fold on a stale terminal event from a previous turn', async () => {
    // liveEvents briefly carries a previous turn's terminal event plus the new
    // turn's streaming chunk. The fold must not trigger and kill the stream.
    hookReturn = {
      connectionStatus: 'open',
      events: [
        ev('exec_OLD', 'execution_completed'),
        ev('exec_new', 'model_chunk', { delta: 'streaming answer' }),
      ],
    }
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByText('streaming answer')).toBeInTheDocument())
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('folds the turn (refetches) when the current execution emits a terminal event', async () => {
    hookReturn = {
      connectionStatus: 'open',
      events: [ev('exec_new', 'execution_completed')],
    }
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))
  })

  // A turn whose execution is still in flight when the chat is (re)opened.
  function runningDetail(execId = 'exec_run') {
    return {
      conversation: { ...baseDetail.conversation },
      turns: [
        {
          execution: {
            id: execId,
            type: 'agent',
            target_id: 'agent_1',
            conversation_id: 'conv_1',
            user_input: 'Do work',
            status: 'running',
            approval_mode: 'manual',
            workspace_ids: [],
            created_at: '',
            updated_at: '',
            completed_at: null,
            result: null,
            error: null,
          },
          events: [],
        },
      ],
    }
  }

  it('reconnects the live stream when reopening a chat whose last turn is still running', async () => {
    get.mockResolvedValue(runningDetail())
    hookReturn = {
      connectionStatus: 'open',
      events: [ev('exec_run', 'model_chunk', { delta: 'live progress' })],
    }

    renderAt('conv_1')

    // Without an explicit send, the persisted running turn streams live again
    // and the Stop control becomes available.
    await waitFor(() => expect(screen.getByText('live progress')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Stop the agent' })).toBeInTheDocument()
  })

  it('stops the agent by cancelling the active execution', async () => {
    get.mockResolvedValue(runningDetail())
    hookReturn = {
      connectionStatus: 'open',
      events: [ev('exec_run', 'model_chunk', { delta: 'working' })],
    }

    renderAt('conv_1')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Stop the agent' })).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Stop the agent' }))

    await waitFor(() => expect(cancelExecution).toHaveBeenCalledWith('exec_run'))
  })

  it('hides Stop while the active turn is waiting for approval', async () => {
    get.mockResolvedValue(runningDetail())
    hookReturn = {
      connectionStatus: 'open',
      events: [
        ev('exec_run', 'approval_requested', { approval_id: 'approval_1', tool: 'http.request' }),
        ev('exec_run', 'execution_waiting_approval', { approval_id: 'approval_1' }),
      ],
    }

    renderAt('conv_1')
    await waitFor(() => expect(screen.getByText('Approval required')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Stop the agent' })).not.toBeInTheDocument()
  })
})
