import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AgentForm } from '../views/AgentForm'
import { agentsApi } from '../api/agents'
import { providersApi } from '../api/providers'
import { pluginsApi } from '../api/plugins'
import { mcpApi } from '../api/mcp'

vi.mock('../api/agents', () => ({
  agentsApi: {
    create: vi.fn().mockResolvedValue({ id: 'agent_new', name: 'New Agent' }),
    get: vi.fn(),
    update: vi.fn(),
    getSkills: vi.fn().mockResolvedValue([]),
    updateSkills: vi.fn().mockResolvedValue([]),
    getPlugins: vi.fn().mockResolvedValue([]),
    updatePlugins: vi.fn().mockResolvedValue([]),
    getMcpServers: vi.fn().mockResolvedValue([]),
    updateMcpServers: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../api/plugins', () => ({
  pluginsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'plugin_sample',
        name: 'Sample Plugin',
        version: '0.1.0',
        description: 'Adds sample tools.',
        enabled: true,
        permissions: ['sample'],
        tools_json: [{ name: 'sample.echo', capability: 'sample', critical: false }],
        skills_json: [{ id: 'skill_plugin_sample', name: 'Plugin Sample' }],
      },
    ]),
  },
}))

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
  },
}))

vi.mock('../api/skills', () => ({
  skillsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'skill_report_writer', name: 'Report Writer', version: '0.1.0', description: 'Writes reports', tags: ['writing'], prompt: 'Write reports.', examples: [] },
    ]),
  },
}))

vi.mock('../api/providers', () => ({
  providersApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'p1', name: 'Ollama', type: 'ollama', base_url: 'http://localhost:11434', enabled: true, config: {} },
    ]),
    models: vi.fn().mockResolvedValue([{ id: 'llama3', name: 'LLaMA 3' }]),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({}) }
})

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))

describe('AgentForm (create)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the form title', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('New Agent')).toBeInTheDocument()
    })
  })

  it('renders name input', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g. Research Assistant')).toBeInTheDocument()
    })
  })

  it('renders system prompt textarea', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('You are a helpful assistant...')).toBeInTheDocument()
    })
  })

  it('shows provider selector after loading', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Ollama (ollama)')).toBeInTheDocument()
    })
  })

  it('shows skills and saves selected skill ids', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Report Writer')).toBeInTheDocument())

    await userEvent.type(screen.getByPlaceholderText('e.g. Research Assistant'), 'New Agent')
    await userEvent.selectOptions(screen.getByLabelText('Provider *'), 'p1')
    await waitFor(() => expect(screen.getByText('LLaMA 3')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('option', { name: /LLaMA 3/ }))
    await userEvent.click(screen.getByLabelText('Report Writer'))
    await userEvent.click(screen.getByRole('button', { name: 'Create Agent' }))

    await waitFor(() => {
      expect(agentsApi.updateSkills).toHaveBeenCalledWith('agent_new', ['skill_report_writer'])
    })
  })

  it('shows plugins and saves selected plugin ids', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Sample Plugin')).toBeInTheDocument())

    await userEvent.type(screen.getByPlaceholderText('e.g. Research Assistant'), 'New Agent')
    await userEvent.selectOptions(screen.getByLabelText('Provider *'), 'p1')
    await waitFor(() => expect(screen.getByText('LLaMA 3')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('option', { name: /LLaMA 3/ }))
    await userEvent.click(screen.getByLabelText('Sample Plugin'))
    await userEvent.click(screen.getByRole('button', { name: 'Create Agent' }))

    await waitFor(() => {
      expect(agentsApi.updatePlugins).toHaveBeenCalledWith('agent_new', ['plugin_sample'])
      expect(pluginsApi.list).toHaveBeenCalled()
    })
  })

  it('shows MCP servers and saves selected server ids', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Filesystem MCP')).toBeInTheDocument())

    await userEvent.type(screen.getByPlaceholderText('e.g. Research Assistant'), 'New Agent')
    await userEvent.selectOptions(screen.getByLabelText('Provider *'), 'p1')
    await waitFor(() => expect(screen.getByText('LLaMA 3')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('option', { name: /LLaMA 3/ }))
    await userEvent.click(screen.getByLabelText('Filesystem MCP'))
    await userEvent.click(screen.getByRole('button', { name: 'Create Agent' }))

    await waitFor(() => {
      expect(agentsApi.updateMcpServers).toHaveBeenCalledWith('agent_new', ['filesystem'])
      expect(mcpApi.list).toHaveBeenCalled()
    })
  })

  it('lets users search and select OpenRouter models from the loaded model list', async () => {
    vi.mocked(providersApi.list).mockResolvedValue([
      { id: 'or1', name: 'OpenRouter', type: 'openrouter', base_url: 'https://openrouter.ai/api/v1', enabled: true, config: { api_key: 'sk-...1234' } },
    ])
    vi.mocked(providersApi.models).mockResolvedValue([
      { id: 'openai/gpt-4o-mini', name: 'GPT-4o mini' },
      { id: 'poolside/laguna-m1:free', name: 'Poolside Laguna M1 Free' },
      { id: 'anthropic/claude-sonnet-4', name: 'Claude Sonnet 4' },
    ])

    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('OpenRouter (openrouter)')).toBeInTheDocument())

    await userEvent.selectOptions(screen.getByLabelText('Provider *'), 'or1')
    await waitFor(() => expect(screen.getByRole('option', { name: /GPT-4o mini/ })).toBeInTheDocument())

    const modelInput = screen.getByLabelText('Model *')
    await userEvent.type(modelInput, 'laguna')

    expect(screen.getByRole('option', { name: /Poolside Laguna M1 Free/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /GPT-4o mini/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('option', { name: /Poolside Laguna M1 Free/ }))

    expect(modelInput).toHaveValue('poolside/laguna-m1:free')
  })
})
