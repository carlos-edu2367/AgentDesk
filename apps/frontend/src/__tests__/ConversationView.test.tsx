import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ConversationView } from '../views/ConversationView'

const sendMessage = vi.fn()
const get = vi.fn()

vi.mock('../api/conversations', () => ({
  conversationsApi: {
    get: (...args: unknown[]) => get(...args),
    sendMessage: (...args: unknown[]) => sendMessage(...args),
  },
}))

// Avoid opening real EventSource connections in jsdom.
vi.mock('../hooks/useExecutionEvents', () => ({
  useExecutionEvents: () => ({ events: [], connectionStatus: 'closed' }),
}))

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
  conversation: { id: 'conv_1', type: 'agent', target_id: 'agent_1', title: 'Researcher', created_at: '', updated_at: '' },
  turns: [],
}

describe('ConversationView', () => {
  beforeEach(() => {
    get.mockReset()
    sendMessage.mockReset()
    get.mockResolvedValue(baseDetail)
    sendMessage.mockResolvedValue({ execution_id: 'exec_new', conversation_id: 'conv_1', status: 'running' })
  })

  it('renders the conversation title', async () => {
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByText('Researcher')).toBeInTheDocument())
  })

  it('sends a message and renders the user bubble', async () => {
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByPlaceholderText('Send a message…')).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText('Send a message…'), { target: { value: 'Hello agent' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(sendMessage).toHaveBeenCalledWith('conv_1', { message: 'Hello agent', stream: true }))
  })
})
