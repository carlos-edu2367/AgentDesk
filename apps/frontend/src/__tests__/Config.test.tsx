import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Config } from '../views/Config'

// Stub every panel view so this test stays isolated from their data fetching.
vi.mock('../views/Providers', () => ({ Providers: () => <div>Providers Panel</div> }))
vi.mock('../views/Workspaces', () => ({ Workspaces: () => <div>Workspaces Panel</div> }))
vi.mock('../views/Tools', () => ({ Tools: () => <div>Tools Panel</div> }))
vi.mock('../views/McpServers', () => ({ McpServers: () => <div>Mcp Panel</div> }))
vi.mock('../views/Skills', () => ({ Skills: () => <div>Skills Panel</div> }))
vi.mock('../views/Plugins', () => ({ Plugins: () => <div>Plugins Panel</div> }))
vi.mock('../views/Memory', () => ({ Memory: () => <div>Memory Panel</div> }))
vi.mock('../views/Executions', () => ({ Executions: () => <div>Executions Panel</div> }))
vi.mock('../views/AuditLogs', () => ({ AuditLogs: () => <div>Audit Panel</div> }))
vi.mock('../views/Settings', () => ({ Settings: () => <div>System Panel</div> }))

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/config/:section" element={<Config />} /></Routes>
    </MemoryRouter>,
  )
}

describe('Config', () => {
  it('renders the providers panel for /config/providers', () => {
    renderAt('/config/providers')
    expect(screen.getByText('Providers Panel')).toBeInTheDocument()
  })

  it('renders the executions panel for /config/executions', () => {
    renderAt('/config/executions')
    expect(screen.getByText('Executions Panel')).toBeInTheDocument()
  })

  it('shows the four group headers', () => {
    renderAt('/config/tools')
    expect(screen.getByText('Modelos & Acesso')).toBeInTheDocument()
    expect(screen.getByText('Capacidades')).toBeInTheDocument()
    expect(screen.getByText('Atividade')).toBeInTheDocument()
    expect(screen.getByText('Sistema')).toBeInTheDocument()
  })
})
