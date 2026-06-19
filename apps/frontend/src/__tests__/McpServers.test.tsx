import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { McpServers } from '../views/McpServers'
import { mcpApi } from '../api/mcp'

vi.mock('../api/mcp', () => ({
  mcpApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'filesystem',
        name: 'Filesystem MCP',
        enabled: true,
        transport: 'stdio',
        command: 'python',
        args: ['mock_mcp_server.py'],
        env: {},
        tools_cache_json: [
          {
            name: 'mcp.filesystem.echo',
            original_name: 'echo',
            description: 'Echoes arguments.',
            input_schema: {},
            server_id: 'filesystem',
            critical: true,
          },
        ],
        last_connected_at: '2026-06-18T00:00:00',
        last_error: '',
        created_at: '2026-06-18T00:00:00',
        updated_at: '2026-06-18T00:00:00',
      },
    ]),
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({ status: 'deleted' }),
    enable: vi.fn().mockResolvedValue({}),
    disable: vi.fn().mockResolvedValue({}),
    test: vi.fn().mockResolvedValue({
      server_id: 'filesystem',
      status: 'ok',
      tools: [{ name: 'mcp.filesystem.echo', original_name: 'echo', description: 'Echoes arguments.', input_schema: {}, server_id: 'filesystem', critical: true }],
      error: null,
    }),
  },
}))

describe('MCP Servers page', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders configured MCP servers and detected tools', async () => {
    render(<MemoryRouter><McpServers /></MemoryRouter>)

    await waitFor(() => {
      expect(screen.getByText('Filesystem MCP')).toBeInTheDocument()
      expect(screen.getByText('mcp.filesystem.echo')).toBeInTheDocument()
      expect(screen.getByText('MCP servers executam processos locais. Cadastre apenas servidores confiaveis.')).toBeInTheDocument()
    })
  })

  it('creates an MCP server from the form', async () => {
    render(<MemoryRouter><McpServers /></MemoryRouter>)

    await userEvent.type(await screen.findByLabelText('ID'), 'memory')
    await userEvent.type(screen.getByLabelText('Name'), 'Memory MCP')
    await userEvent.type(screen.getByLabelText('Command'), 'python')
    await userEvent.type(screen.getByLabelText('Args'), 'mock_mcp_server.py')
    await userEvent.click(screen.getByRole('button', { name: 'Create Server' }))

    await waitFor(() => {
      expect(mcpApi.create).toHaveBeenCalledWith({
        id: 'memory',
        name: 'Memory MCP',
        enabled: true,
        transport: 'stdio',
        command: 'python',
        args: ['mock_mcp_server.py'],
        env: {},
      })
    })
  })

  it('tests an MCP server connection', async () => {
    render(<MemoryRouter><McpServers /></MemoryRouter>)

    await userEvent.click(await screen.findByRole('button', { name: 'Test' }))

    await waitFor(() => {
      expect(mcpApi.test).toHaveBeenCalledWith('filesystem')
      expect(screen.getByText('Connection OK. 1 tools detected.')).toBeInTheDocument()
    })
  })
})
