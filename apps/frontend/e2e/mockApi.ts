import type { Page, Route } from '@playwright/test'

const now = new Date('2026-06-18T12:00:00.000Z').toISOString()

const provider = {
  id: 'provider_ollama',
  type: 'ollama',
  name: 'Local Ollama',
  base_url: 'http://localhost:11434',
  enabled: true,
  config: {},
  created_at: now,
  updated_at: now,
}

const agent = {
  id: 'agent_demo',
  name: 'Demo Agent',
  description: 'Mocked local agent',
  system_prompt: 'You are a useful local assistant.',
  model_config: {
    provider_id: provider.id,
    model: 'llama3.1',
    temperature: 0.4,
    top_p: 0.9,
    context_window: 8192,
    max_tokens: 2048,
    stream: true,
  },
  tools_config: { capabilities: [], explicit_tools: [], blocked_tools: [] },
  memory_config: {},
  subagent_config: {},
  is_active: true,
  created_at: now,
  updated_at: now,
}

const execution = {
  id: 'execution_demo',
  type: 'agent',
  target_id: agent.id,
  user_input: 'Say hello',
  status: 'completed',
  approval_mode: 'manual',
  result: 'Hello from the mocked E2E runtime.',
  error: null,
  workspace_ids: [],
  created_at: now,
  completed_at: now,
}

export async function installMockApi(page: Page) {
  await page.route(/https?:\/\/(127\.0\.0\.1|localhost):8000\/api\/.*/, async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const method = route.request().method()

    if (path === '/api/health') return json(route, { status: 'ok', version: '0.1.0', storage_ready: true, database_ready: true })
    if (path === '/api/storage/info') return json(route, { appdata_path: 'C:\\Users\\E2E\\AppData\\Roaming\\AgentDesk', database_path: 'C:\\Users\\E2E\\AppData\\Roaming\\AgentDesk\\database\\agentdesk.sqlite', directories: {}, configs: {} })
    if (path === '/api/providers' && method === 'GET') return json(route, [provider])
    if (path === '/api/providers' && method === 'POST') return json(route, { ...provider, id: 'provider_created', name: 'E2E Ollama' })
    if (path === `/api/providers/${provider.id}/models`) return json(route, [{ id: 'llama3.1', name: 'llama3.1', context_window: 8192 }])
    if (path === '/api/agents' && method === 'GET') return json(route, [agent])
    if (path === '/api/agents' && method === 'POST') return json(route, { ...agent, id: 'agent_created', name: 'E2E Agent' })
    if (path.endsWith('/tools') || path.endsWith('/skills') || path.endsWith('/plugins') || path.endsWith('/mcp')) return json(route, [])
    if (path === '/api/workspaces') return json(route, [])
    if (path === '/api/executions' && method === 'GET') return json(route, [execution])
    if (path === '/api/executions/agent' && method === 'POST') return json(route, { execution_id: execution.id, status: 'running' })
    if (path === `/api/executions/${execution.id}`) return json(route, execution)
    if (path === `/api/executions/${execution.id}/events`) {
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
    }
    if (path === `/api/executions/${execution.id}/approvals`) return json(route, [])
    if (path === `/api/executions/${execution.id}/detail`) return json(route, {
      execution,
      events: [],
      audit_logs: [],
      approvals: [],
      artifacts: [],
      summary: {
        total_events: 0,
        total_audit_logs: 0,
        tools_used: [],
        agents_involved: [agent.id],
        mcp_servers_used: [],
        plugins_used: [],
        skills_used: [],
        memories_used: [],
        approval_mode: 'manual',
        critical_actions_count: 0,
        auto_approved_count: 0,
        manual_approved_count: 0,
        manual_rejected_count: 0,
      },
    })
    if (path === '/api/audit') return json(route, { items: [], total: 0, limit: 50, offset: 0 })
    if (path === '/api/memories') return json(route, [])
    if (path === '/api/skills') return json(route, [])
    if (path === '/api/plugins') return json(route, [])
    if (path === '/api/mcp') return json(route, [])
    if (path === '/api/teams') return json(route, [])
    if (path === '/api/tools') return json(route, [])
    if (path === '/api/tools/capabilities') return json(route, [])
    if (method === 'PUT' || method === 'POST') return json(route, {})

    return json(route, {}, 200)
  })
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}
