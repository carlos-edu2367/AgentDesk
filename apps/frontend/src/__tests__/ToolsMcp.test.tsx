import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Tools } from '../views/Tools'

vi.mock('../api/tools', () => ({
  toolsApi: {
    list: vi.fn().mockResolvedValue([
      {
        name: 'filesystem.read',
        description: 'Read file',
        source: 'core',
        capability: 'filesystem_read',
        critical: false,
        input_schema: {},
      },
      {
        name: 'sample.echo',
        description: 'Plugin echo',
        source: 'plugin',
        capability: 'sample',
        critical: false,
        input_schema: {},
        plugin_id: 'plugin_sample',
      },
      {
        name: 'mcp.filesystem.echo',
        description: 'MCP echo',
        source: 'mcp',
        capability: 'mcp.filesystem',
        critical: true,
        input_schema: {},
        server_id: 'filesystem',
      },
    ]),
    listCapabilities: vi.fn().mockResolvedValue([
      { name: 'filesystem_read', tools: ['filesystem.read'] },
      { name: 'mcp', tools: ['mcp.filesystem.echo'] },
      { name: 'mcp.filesystem', tools: ['mcp.filesystem.echo'] },
    ]),
  },
}))

describe('Tools page MCP tools', () => {
  it('shows MCP tools separately with server id and critical badge', async () => {
    render(<MemoryRouter><Tools /></MemoryRouter>)

    await waitFor(() => {
      expect(screen.getByText('MCP Tools')).toBeInTheDocument()
      expect(screen.getAllByText('mcp.filesystem.echo').length).toBeGreaterThan(0)
      expect(screen.getByText('filesystem')).toBeInTheDocument()
      expect(screen.getAllByText('critical').length).toBeGreaterThan(0)
    })
  })
})
