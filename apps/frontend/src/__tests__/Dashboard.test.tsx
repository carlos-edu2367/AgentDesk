import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Dashboard } from '../views/Dashboard'

vi.mock('../api/storage', () => ({
  healthApi: { check: vi.fn().mockResolvedValue({ status: 'ok' }) },
  storageApi: { info: vi.fn().mockResolvedValue({ appdata_path: 'C:/AppData', database_path: 'C:/AppData/db.sqlite' }) },
}))

vi.mock('../api/agents', () => ({
  agentsApi: { list: vi.fn().mockResolvedValue([{ id: 'a1', name: 'Agent 1' }]) },
}))

vi.mock('../api/providers', () => ({
  providersApi: { list: vi.fn().mockResolvedValue([]) },
}))

vi.mock('../api/workspaces', () => ({
  workspacesApi: { list: vi.fn().mockResolvedValue([]) },
}))

vi.mock('../api/executions', () => ({
  executionsApi: { list: vi.fn().mockResolvedValue([]) },
}))

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  )
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the dashboard title', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })
  })

  it('shows agent count after loading', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument()
    })
  })

  it('shows backend status badge', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByText('ok')).toBeInTheDocument()
    })
  })

  it('shows quick action buttons', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByText('New Agent')).toBeInTheDocument()
      expect(screen.getByText('Run Agent')).toBeInTheDocument()
    })
  })
})
