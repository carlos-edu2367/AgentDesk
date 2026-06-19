import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { agentsApi } from '../api/agents'
import { providersApi } from '../api/providers'
import { toolsApi } from '../api/tools'
import { skillsApi } from '../api/skills'
import { pluginsApi } from '../api/plugins'
import { mcpApi } from '../api/mcp'
import type { ModelConfig, Provider, ModelInfo, AgentToolsConfig, Skill, Plugin, MCPServer } from '../types/domain'

const DEFAULT_MODEL_CONFIG: ModelConfig = {
  provider_id: '',
  model: '',
  temperature: 0.4,
  top_p: 0.9,
  context_window: 8192,
  max_tokens: 2048,
  stream: true,
}

const ALL_CAPABILITIES = [
  'filesystem_read',
  'filesystem_write',
  'filesystem_delete',
  'terminal',
  'http',
  'workspace',
  'logs',
] as const

const CAPABILITY_LABELS: Record<string, string> = {
  filesystem_read: 'Filesystem Read',
  filesystem_write: 'Filesystem Write (write, move, copy)',
  filesystem_delete: 'Filesystem Delete',
  terminal: 'Terminal (exec commands)',
  http: 'HTTP Requests',
  workspace: 'Workspace Info',
  logs: 'Execution Logs',
}

const CRITICAL_CAPABILITIES = new Set(['filesystem_write', 'filesystem_delete', 'terminal', 'http'])

const DEFAULT_TOOLS_CONFIG: AgentToolsConfig = {
  capabilities: [],
  explicit_tools: [],
  blocked_tools: [],
}

export function AgentForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = Boolean(id)

  const [providers, setProviders] = useState<Provider[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [modelConfig, setModelConfig] = useState<ModelConfig>(DEFAULT_MODEL_CONFIG)
  const [toolsConfig, setToolsConfig] = useState<AgentToolsConfig>(DEFAULT_TOOLS_CONFIG)
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([])
  const [selectedPluginIds, setSelectedPluginIds] = useState<string[]>([])
  const [selectedMcpServerIds, setSelectedMcpServerIds] = useState<string[]>([])
  const [explicitToolsInput, setExplicitToolsInput] = useState('')
  const [blockedToolsInput, setBlockedToolsInput] = useState('')

  useEffect(() => {
    providersApi.list().then(setProviders).catch(() => {})
    skillsApi.list().then(setSkills).catch(() => setSkills([]))
    pluginsApi.list().then(setPlugins).catch(() => setPlugins([]))
    mcpApi.list().then(setMcpServers).catch(() => setMcpServers([]))
  }, [])

  useEffect(() => {
    if (!isEdit || !id) return
    setLoading(true)
    Promise.all([
      agentsApi.get(id),
      toolsApi.getAgentTools(id).catch(() => DEFAULT_TOOLS_CONFIG),
      agentsApi.getSkills(id).catch(() => []),
      agentsApi.getPlugins(id).catch(() => []),
      agentsApi.getMcpServers(id).catch(() => []),
    ])
      .then(([agent, tc, agentSkills, agentPlugins, agentMcpServers]) => {
        setName(agent.name)
        setDescription(agent.description)
        setSystemPrompt(agent.system_prompt)
        setModelConfig(agent.model_config)
        setToolsConfig(tc)
        setSelectedSkillIds(agentSkills.map(skill => skill.id))
        setSelectedPluginIds(agentPlugins.map(plugin => plugin.id))
        setSelectedMcpServerIds(agentMcpServers.map(server => server.id))
        setExplicitToolsInput(tc.explicit_tools.join(', '))
        setBlockedToolsInput(tc.blocked_tools.join(', '))
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  useEffect(() => {
    if (!modelConfig.provider_id) return
    setLoadingModels(true)
    providersApi.models(modelConfig.provider_id)
      .then(setModels)
      .catch(() => setModels([]))
      .finally(() => setLoadingModels(false))
  }, [modelConfig.provider_id])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = { name, description, system_prompt: systemPrompt, model_config: modelConfig }
      const splitInput = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean)
      const tc: AgentToolsConfig = {
        capabilities: toolsConfig.capabilities,
        explicit_tools: splitInput(explicitToolsInput),
        blocked_tools: splitInput(blockedToolsInput),
      }
      if (isEdit && id) {
        await agentsApi.update(id, payload)
        await toolsApi.updateAgentTools(id, tc).catch(() => {})
        await agentsApi.updateSkills(id, selectedSkillIds).catch(() => {})
        await agentsApi.updatePlugins(id, selectedPluginIds).catch(() => {})
        await agentsApi.updateMcpServers(id, selectedMcpServerIds).catch(() => {})
      } else {
        const created = await agentsApi.create(payload)
        await toolsApi.updateAgentTools(created.id, tc).catch(() => {})
        await agentsApi.updateSkills(created.id, selectedSkillIds).catch(() => {})
        await agentsApi.updatePlugins(created.id, selectedPluginIds).catch(() => {})
        await agentsApi.updateMcpServers(created.id, selectedMcpServerIds).catch(() => {})
      }
      navigate('/agents')
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const toggleSkill = (skillId: string) => {
    setSelectedSkillIds(prev =>
      prev.includes(skillId) ? prev.filter(id => id !== skillId) : [...prev, skillId],
    )
  }

  const togglePlugin = (pluginId: string) => {
    setSelectedPluginIds(prev =>
      prev.includes(pluginId) ? prev.filter(id => id !== pluginId) : [...prev, pluginId],
    )
  }

  const toggleMcpServer = (serverId: string) => {
    setSelectedMcpServerIds(prev =>
      prev.includes(serverId) ? prev.filter(id => id !== serverId) : [...prev, serverId],
    )
  }

  const toggleCapability = (cap: string) => {
    setToolsConfig(prev => ({
      ...prev,
      capabilities: prev.capabilities.includes(cap)
        ? prev.capabilities.filter(c => c !== cap)
        : [...prev.capabilities, cap],
    }))
  }

  const capabilityOptions = Array.from(new Set([
    ...ALL_CAPABILITIES,
    ...plugins.flatMap(plugin => plugin.permissions ?? []),
    ...(mcpServers.length > 0 ? ['mcp'] : []),
    ...mcpServers.map(server => `mcp.${server.id}`),
  ]))

  if (loading) return <LoadingState />
  if (error && loading) return <ErrorState message={error} />

  return (
    <div>
      <TopBar
        title={isEdit ? 'Edit Agent' : 'New Agent'}
        actions={
          <button className="btn-ghost" onClick={() => navigate('/agents')}>
            Cancel
          </button>
        }
      />

      <form onSubmit={handleSubmit} className="space-y-5 max-w-2xl">
        {error && (
          <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md p-3">
            {error}
          </div>
        )}

        <div>
          <label className="form-label">Name *</label>
          <input
            className="form-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. Research Assistant"
            required
          />
        </div>

        <div>
          <label className="form-label">Description</label>
          <input
            className="form-input"
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Brief description of what this agent does"
          />
        </div>

        <div>
          <label className="form-label">System Prompt</label>
          <textarea
            className="form-textarea min-h-[120px]"
            value={systemPrompt}
            onChange={e => setSystemPrompt(e.target.value)}
            placeholder="You are a helpful assistant..."
          />
        </div>

        <fieldset className="border border-slate-700 rounded-lg p-4">
          <legend className="text-sm font-medium text-slate-300 px-1">Model Configuration</legend>
          <div className="space-y-4 mt-2">

            <div>
              <label className="form-label" htmlFor="agent-provider">Provider *</label>
              <select
                id="agent-provider"
                className="form-select"
                value={modelConfig.provider_id}
                onChange={e => setModelConfig(prev => ({ ...prev, provider_id: e.target.value, model: '' }))}
                required
              >
                <option value="">Select a provider...</option>
                {providers.map(p => (
                  <option key={p.id} value={p.id}>{p.name} ({p.type})</option>
                ))}
              </select>
            </div>

            <div>
              <label className="form-label" htmlFor="agent-model">Model *</label>
              {loadingModels ? (
                <p className="text-slate-500 text-sm">Loading models...</p>
              ) : models.length > 0 ? (
                <select
                  id="agent-model"
                  className="form-select"
                  value={modelConfig.model}
                  onChange={e => setModelConfig(prev => ({ ...prev, model: e.target.value }))}
                  required
                >
                  <option value="">Select a model...</option>
                  {models.map(m => (
                    <option key={m.id} value={m.id}>{m.name || m.id}</option>
                  ))}
                </select>
              ) : (
                <input
                  id="agent-model"
                  className="form-input"
                  value={modelConfig.model}
                  onChange={e => setModelConfig(prev => ({ ...prev, model: e.target.value }))}
                  placeholder="e.g. llama3:8b or openai/gpt-4o"
                  required
                />
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="form-label">Temperature</label>
                <input
                  type="number" min="0" max="2" step="0.1"
                  className="form-input"
                  value={modelConfig.temperature}
                  onChange={e => setModelConfig(prev => ({ ...prev, temperature: Number(e.target.value) }))}
                />
              </div>
              <div>
                <label className="form-label">Top P</label>
                <input
                  type="number" min="0" max="1" step="0.05"
                  className="form-input"
                  value={modelConfig.top_p}
                  onChange={e => setModelConfig(prev => ({ ...prev, top_p: Number(e.target.value) }))}
                />
              </div>
              <div>
                <label className="form-label">Context Window</label>
                <input
                  type="number" min="512" step="512"
                  className="form-input"
                  value={modelConfig.context_window}
                  onChange={e => setModelConfig(prev => ({ ...prev, context_window: Number(e.target.value) }))}
                />
              </div>
              <div>
                <label className="form-label">Max Tokens</label>
                <input
                  type="number" min="64" step="64"
                  className="form-input"
                  value={modelConfig.max_tokens}
                  onChange={e => setModelConfig(prev => ({ ...prev, max_tokens: Number(e.target.value) }))}
                />
              </div>
            </div>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={modelConfig.stream}
                onChange={e => setModelConfig(prev => ({ ...prev, stream: e.target.checked }))}
                className="rounded border-slate-600 bg-slate-800 text-blue-500"
              />
              <span className="text-sm text-slate-300">Enable streaming</span>
            </label>
          </div>
        </fieldset>

        <fieldset className="border border-slate-700 rounded-lg p-4">
          <legend className="text-sm font-medium text-slate-300 px-1">Skills</legend>
          <div className="space-y-3 mt-2">
            <p className="text-xs text-slate-500">
              Skills alteram o comportamento do agente, mas não executam código.
            </p>
            {skills.length === 0 ? (
              <p className="text-sm text-slate-500">No skills available.</p>
            ) : (
              <div className="grid grid-cols-1 gap-2">
                {skills.map(skill => (
                  <label key={skill.id} className="flex items-start gap-2 cursor-pointer rounded border border-slate-800 p-2">
                    <input
                      aria-label={skill.name}
                      type="checkbox"
                      checked={selectedSkillIds.includes(skill.id)}
                      onChange={() => toggleSkill(skill.id)}
                      className="mt-0.5 rounded border-slate-600 bg-slate-800 text-blue-500"
                    />
                    <span className="min-w-0">
                      <span className="block text-sm text-slate-200">{skill.name}</span>
                      <span className="block font-mono text-xs text-slate-500">{skill.id}</span>
                    </span>
                  </label>
                ))}
              </div>
            )}
            {selectedSkillIds.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {selectedSkillIds.map(skillId => {
                  const skill = skills.find(item => item.id === skillId)
                  return (
                    <span key={skillId} className="rounded bg-blue-500/20 px-2 py-0.5 text-xs text-blue-300">
                      {skill?.name ?? skillId}
                    </span>
                  )
                })}
              </div>
            )}
          </div>
        </fieldset>

        <fieldset className="border border-slate-700 rounded-lg p-4">
          <legend className="text-sm font-medium text-slate-300 px-1">Plugins</legend>
          <div className="space-y-3 mt-2">
            <p className="text-xs text-slate-500">
              Plugins adicionam tools e skills locais. Tools ainda respeitam capabilities, explicit tools e blocked tools.
            </p>
            {plugins.length === 0 ? (
              <p className="text-sm text-slate-500">No plugins installed.</p>
            ) : (
              <div className="grid grid-cols-1 gap-2">
                {plugins.map(plugin => (
                  <label key={plugin.id} className="flex items-start gap-2 cursor-pointer rounded border border-slate-800 p-2">
                    <input
                      aria-label={plugin.name}
                      type="checkbox"
                      checked={selectedPluginIds.includes(plugin.id)}
                      onChange={() => togglePlugin(plugin.id)}
                      className="mt-0.5 rounded border-slate-600 bg-slate-800 text-blue-500"
                    />
                    <span className="min-w-0">
                      <span className="flex items-center gap-2 text-sm text-slate-200">
                        {plugin.name}
                        <span className={`rounded px-1.5 py-0.5 text-xs ${plugin.enabled ? 'bg-green-500/15 text-green-300' : 'bg-slate-700 text-slate-400'}`}>
                          {plugin.enabled ? 'enabled' : 'disabled'}
                        </span>
                      </span>
                      <span className="block font-mono text-xs text-slate-500">{plugin.id}</span>
                      <span className="block text-xs text-slate-500">
                        {(plugin.tools_json ?? []).map(tool => tool.name).join(', ') || 'No tools'}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </fieldset>

        <fieldset className="border border-slate-700 rounded-lg p-4">
          <legend className="text-sm font-medium text-slate-300 px-1">MCP Servers</legend>
          <div className="space-y-3 mt-2">
            <p className="text-xs text-slate-500">
              MCP servers adicionam tools via processos locais stdio. O servidor precisa estar associado ao agente e a tool ainda precisa de capability ou explicit tool.
            </p>
            {mcpServers.length === 0 ? (
              <p className="text-sm text-slate-500">No MCP servers configured.</p>
            ) : (
              <div className="grid grid-cols-1 gap-2">
                {mcpServers.map(server => (
                  <label key={server.id} className="flex items-start gap-2 cursor-pointer rounded border border-slate-800 p-2">
                    <input
                      aria-label={server.name}
                      type="checkbox"
                      checked={selectedMcpServerIds.includes(server.id)}
                      onChange={() => toggleMcpServer(server.id)}
                      className="mt-0.5 rounded border-slate-600 bg-slate-800 text-blue-500"
                    />
                    <span className="min-w-0">
                      <span className="flex items-center gap-2 text-sm text-slate-200">
                        {server.name}
                        <span className={`rounded px-1.5 py-0.5 text-xs ${server.enabled ? 'bg-green-500/15 text-green-300' : 'bg-slate-700 text-slate-400'}`}>
                          {server.enabled ? 'enabled' : 'disabled'}
                        </span>
                      </span>
                      <span className="block font-mono text-xs text-slate-500">{server.id}</span>
                      <span className="block text-xs text-slate-500">
                        {(server.tools_cache_json ?? []).map(tool => tool.name).join(', ') || 'No tools detected'}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </fieldset>

        <fieldset className="border border-slate-700 rounded-lg p-4">
          <legend className="text-sm font-medium text-slate-300 px-1">Tool Permissions</legend>
          <div className="space-y-4 mt-2">

            <div>
              <p className="form-label mb-2">Capabilities</p>
              <div className="space-y-2">
                {capabilityOptions.map(cap => {
                  const isCritical = CRITICAL_CAPABILITIES.has(cap)
                  const isChecked = toolsConfig.capabilities.includes(cap)
                  return (
                    <label key={cap} className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleCapability(cap)}
                        className="mt-0.5 rounded border-slate-600 bg-slate-800 text-blue-500"
                      />
                      <span className="text-sm">
                        <span className={`font-mono ${isCritical ? 'text-amber-300' : 'text-slate-300'}`}>
                          {cap}
                        </span>
                        {isCritical && (
                          <span className="ml-2 text-xs text-amber-500/80 bg-amber-500/10 border border-amber-500/20 rounded px-1 py-0.5">
                            critical
                          </span>
                        )}
                        <span className="block text-xs text-slate-500 mt-0.5">
                          {CAPABILITY_LABELS[cap] ?? cap}
                        </span>
                      </span>
                    </label>
                  )
                })}
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Critical capabilities require approval in manual mode and generate audit logs.
              </p>
            </div>

            <div>
              <label className="form-label">Explicit Tools</label>
              <input
                className="form-input font-mono text-xs"
                value={explicitToolsInput}
                onChange={e => setExplicitToolsInput(e.target.value)}
                placeholder="e.g. filesystem.read, logs.search"
              />
              <p className="text-xs text-slate-500 mt-1">Comma-separated. Grant specific tools without enabling the full capability.</p>
            </div>

            <div>
              <label className="form-label">Blocked Tools</label>
              <input
                className="form-input font-mono text-xs"
                value={blockedToolsInput}
                onChange={e => setBlockedToolsInput(e.target.value)}
                placeholder="e.g. filesystem.search"
              />
              <p className="text-xs text-slate-500 mt-1">Comma-separated. Always blocked, even if granted by capability.</p>
            </div>
          </div>
        </fieldset>

        <div className="flex gap-3">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Agent'}
          </button>
          <button type="button" className="btn-ghost" onClick={() => navigate('/agents')}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
