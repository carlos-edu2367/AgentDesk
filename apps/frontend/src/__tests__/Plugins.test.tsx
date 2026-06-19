import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Plugins } from '../views/Plugins'
import { pluginsApi } from '../api/plugins'

vi.mock('../api/plugins', () => ({
  pluginsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'plugin_sample',
        name: 'Sample Plugin',
        version: '0.1.0',
        description: 'Adds sample tools.',
        enabled: false,
        manifest_path: 'C:/AgentDesk/plugins/installed/plugin_sample/plugin.json',
        install_path: 'C:/AgentDesk/plugins/installed/plugin_sample',
        permissions: ['sample'],
        tools_json: [{ name: 'sample.echo', capability: 'sample', critical: false }],
        skills_json: [{ id: 'skill_plugin_sample', name: 'Plugin Sample' }],
      },
    ]),
    importPlugin: vi.fn().mockResolvedValue({ id: 'plugin_sample', name: 'Sample Plugin', version: '0.1.0', enabled: false, tools: ['sample.echo'], skills: ['skill_plugin_sample'] }),
    enable: vi.fn().mockResolvedValue({}),
    disable: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({ status: 'deleted' }),
  },
}))

describe('Plugins page', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders installed plugins, tools, skills and permissions', async () => {
    render(<MemoryRouter><Plugins /></MemoryRouter>)

    await waitFor(() => {
      expect(screen.getByText('Sample Plugin')).toBeInTheDocument()
      expect(screen.getAllByText('sample.echo').length).toBeGreaterThan(0)
      expect(screen.getByText('skill_plugin_sample')).toBeInTheDocument()
      expect(screen.getAllByText('sample').length).toBeGreaterThan(0)
    })
  })

  it('imports a plugin by local path', async () => {
    render(<MemoryRouter><Plugins /></MemoryRouter>)
    const input = await screen.findByLabelText('Plugin folder path')
    await userEvent.type(input, 'C:/tmp/sample-plugin')
    await userEvent.click(screen.getByRole('button', { name: 'Import Plugin' }))

    await waitFor(() => {
      expect(pluginsApi.importPlugin).toHaveBeenCalledWith('C:/tmp/sample-plugin')
    })
  })
})
