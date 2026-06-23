import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { MultiSelectSection, type SelectableItem } from '../components/MultiSelectSection'
import { agentsApi } from '../api/agents'
import { providersApi } from '../api/providers'
import { toolsApi } from '../api/tools'
import { skillsApi } from '../api/skills'
import { pluginsApi } from '../api/plugins'
import { mcpApi } from '../api/mcp'
import type {
  ModelConfig, Provider, ModelInfo, AgentToolsConfig, Skill, Plugin, MCPServer, CapabilityInfo,
} from '../types/domain'

const DEFAULT_MODEL_CONFIG: ModelConfig = {
  provider_id: '',
  model: '',
  temperature: 0.4,
  top_p: 0.9,
  context_window: 32768,
  max_tokens: 16384,
  stream: true,
}

// Fallback when the backend capability list can't be fetched. Kept in sync with
// backend app/tools/capabilities.py.
const FALLBACK_CAPABILITIES = [
  'filesystem_read', 'filesystem_write', 'filesystem_delete',
  'terminal', 'http', 'web', 'workspace', 'logs',
]

const CAPABILITY_LABELS: Record<string, string> = {
  filesystem_read: 'Read files, list, stat, grep, search',
  filesystem_write: 'Write, edit, multi-edit, move, copy',
  filesystem_delete: 'Delete files and directories',
  terminal: 'Run shell commands (exec, background poll)',
  http: 'Make HTTP requests',
  web: 'Search the web',
  workspace: 'Read workspace info',
  logs: 'Read execution logs',
}

const CRITICAL_CAPABILITIES = new Set(['filesystem_write', 'filesystem_delete', 'terminal', 'http', 'web'])

const DEFAULT_TOOLS_CONFIG: AgentToolsConfig = {
  capabilities: [],
  explicit_tools: [],
  blocked_tools: [],
}

type ModelPickerProps = {
  id: string
  models: ModelInfo[]
  value: string
  onChange: (value: string) => void
  placeholder: string
}

function ModelPicker({ id, models, value, onChange, placeholder }: ModelPickerProps) {
  const [query, setQuery] = useState(value)

  useEffect(() => {
    setQuery(value)
  }, [value])

  const filteredModels = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return models
    return models.filter(model => {
      const label = model.name || model.id
      return model.id.toLowerCase().includes(q) || label.toLowerCase().includes(q)
    })
  }, [models, query])

  const handleInput = (nextValue: string) => {
    setQuery(nextValue)
    onChange(nextValue)
  }

  if (models.length === 0) {
    return (
      <input
        id={id}
        className="form-input"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        required
      />
    )
  }

  return (
    <div className="space-y-2">
      <input
        id={id}
        className="form-input"
        value={query}
        onChange={e => handleInput(e.target.value)}
        placeholder="Search models..."
        autoComplete="off"
        role="combobox"
        aria-expanded="true"
        aria-controls={`${id}-options`}
        required
      />
      <div className="text-xs text-slate-500">
        Showing {filteredModels.length} of {models.length} models
      </div>
      <div
        id={`${id}-options`}
        role="listbox"
        className="max-h-64 overflow-y-auto rounded-md border border-slate-800 bg-slate-950"
      >
        {filteredModels.length > 0 ? (
          filteredModels.map(model => {
            const label = model.name || model.id
            return (
              <button
                key={model.id}
                type="button"
                role="option"
                aria-selected={value === model.id}
                className={`block w-full border-b border-slate-900 px-3 py-2 text-left text-sm last:border-b-0 hover:bg-slate-800 ${
                  value === model.id ? 'bg-blue-500/15 text-blue-200' : 'text-slate-200'
                }`}
                onClick={() => {
                  setQuery(model.id)
                  onChange(model.id)
                }}
              >
                <span className="block font-medium">{label}</span>
                {label !== model.id && <span className="block font-mono text-xs text-slate-500">{model.id}</span>}
              </button>
            )
          })
        ) : (
          <div className="px-3 py-2 text-sm text-slate-500">No models match this search.</div>
        )}
      </div>
    </div>
  )
}

export function AgentForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = Boolean(id)

  const [providers, setProviders] = useState<Provider[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([])
  const [capabilityInfos, setCapabilityInfos] = useState<CapabilityInfo[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [visionModels, setVisionModels] = useState<ModelInfo[]>([])
  const [loadingVisionModels, setLoadingVisionModels] = useState(false)
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

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
    toolsApi.listCapabilities().then(setCapabilityInfos).catch(() => setCapabilityInfos([]))
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
        if (tc.explicit_tools.length || tc.blocked_tools.length) setShowAdvanced(true)
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

  useEffect(() => {
    if (!modelConfig.vision_provider_id) { setVisionModels([]); return }
    setLoadingVisionModels(true)
    providersApi.models(modelConfig.vision_provider_id)
      .then(setVisionModels)
      .catch(() => setVisionModels([]))
      .finally(() => setLoadingVisionModels(false))
  }, [modelConfig.vision_provider_id])

  // Capability options: backend list (authoritative) merged with plugin/MCP-derived ones.
  const capabilityOptions = useMemo(() => {
    const fromBackend = capabilityInfos.map(c => c.name)
    return Array.from(new Set([
      ...(fromBackend.length ? fromBackend : FALLBACK_CAPABILITIES),
      ...plugins.flatMap(plugin => plugin.permissions ?? []),
      ...(mcpServers.length > 0 ? ['mcp'] : []),
      ...mcpServers.map(server => `mcp.${server.id}`),
    ]))
  }, [capabilityInfos, plugins, mcpServers])

  const capabilityToolsMap = useMemo(() => {
    const map: Record<string, string[]> = {}
    for (const c of capabilityInfos) map[c.name] = c.tools
    return map
  }, [capabilityInfos])

  const capabilityItems: SelectableItem[] = useMemo(() =>
    capabilityOptions.map(cap => ({
      id: cap,
      name: cap,
      critical: CRITICAL_CAPABILITIES.has(cap),
      meta: CAPABILITY_LABELS[cap]
        ?? (capabilityToolsMap[cap]?.join(', '))
        ?? cap,
      search: (capabilityToolsMap[cap] ?? []).join(' '),
    })),
  [capabilityOptions, capabilityToolsMap])

  const skillItems: SelectableItem[] = useMemo(() =>
    skills.map(s => ({ id: s.id, name: s.name, mono: s.id, meta: s.description, search: (s.tags ?? []).join(' ') })),
  [skills])

  const pluginItems: SelectableItem[] = useMemo(() =>
    plugins.map(p => ({
      id: p.id, name: p.name, mono: p.id,
      status: { text: p.enabled ? 'enabled' : 'disabled', ok: p.enabled },
      meta: (p.tools_json ?? []).map(t => t.name).join(', ') || 'No tools',
    })),
  [plugins])

  const mcpItems: SelectableItem[] = useMemo(() =>
    mcpServers.map(s => ({
      id: s.id, name: s.name, mono: s.id,
      status: { text: s.enabled ? 'enabled' : 'disabled', ok: s.enabled },
      meta: (s.tools_cache_json ?? []).map(t => t.name).join(', ') || 'No tools detected',
    })),
  [mcpServers])

  const grantEverything = () => {
    setToolsConfig(prev => ({ ...prev, capabilities: capabilityOptions }))
    setSelectedSkillIds(skills.map(s => s.id))
    setSelectedPluginIds(plugins.map(p => p.id))
    setSelectedMcpServerIds(mcpServers.map(s => s.id))
  }

  const revokeEverything = () => {
    setToolsConfig(prev => ({ ...prev, capabilities: [] }))
    setSelectedSkillIds([])
    setSelectedPluginIds([])
    setSelectedMcpServerIds([])
  }

  const totalGranted =
    toolsConfig.capabilities.length + selectedSkillIds.length +
    selectedPluginIds.length + selectedMcpServerIds.length

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
      const targetId = isEdit && id ? id : (await agentsApi.create(payload)).id
      if (isEdit && id) await agentsApi.update(id, payload)
      await toolsApi.updateAgentTools(targetId, tc).catch(() => {})
      await agentsApi.updateSkills(targetId, selectedSkillIds).catch(() => {})
      await agentsApi.updatePlugins(targetId, selectedPluginIds).catch(() => {})
      await agentsApi.updateMcpServers(targetId, selectedMcpServerIds).catch(() => {})
      navigate('/agents')
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState />
  if (error && loading) return <ErrorState message={error} />

  return (
    <div className="pb-24">
      <TopBar
        title={isEdit ? 'Edit Agent' : 'New Agent'}
        description="Configure the agent's identity, model, and what it's allowed to do."
        actions={
          <button className="btn-ghost" onClick={() => navigate('/agents')}>Cancel</button>
        }
      />

      <form id="agent-form" onSubmit={handleSubmit} className="mx-auto max-w-3xl space-y-6">
        {error && (
          <div className="rounded-md border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Identity */}
        <section className="card space-y-4">
          <div className="flex items-center gap-2">
            <span aria-hidden>🪪</span>
            <h3 className="text-sm font-semibold text-slate-100">Identity</h3>
          </div>
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
        </section>

        {/* Model */}
        <section className="card space-y-4">
          <div className="flex items-center gap-2">
            <span aria-hidden>⚙️</span>
            <h3 className="text-sm font-semibold text-slate-100">Model</h3>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
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
                <p className="text-slate-500 text-sm py-2">Loading models...</p>
              ) : models.length > 0 ? (
                <ModelPicker
                  id="agent-model"
                  models={models}
                  value={modelConfig.model}
                  onChange={model => setModelConfig(prev => ({ ...prev, model }))}
                  placeholder="e.g. llama3:8b or openai/gpt-4o"
                />
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
          </div>

          <button
            type="button"
            onClick={() => setShowAdvanced(s => !s)}
            className="text-xs font-medium text-slate-400 hover:text-slate-200"
          >
            {showAdvanced ? '▾' : '▸'} Advanced parameters
          </button>

          {showAdvanced && (
            <div className="space-y-4 border-t border-slate-800 pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="form-label">Temperature</label>
                  <input
                    type="number" min="0" max="2" step="0.1" className="form-input"
                    value={modelConfig.temperature}
                    onChange={e => setModelConfig(prev => ({ ...prev, temperature: Number(e.target.value) }))}
                  />
                </div>
                <div>
                  <label className="form-label">Top P</label>
                  <input
                    type="number" min="0" max="1" step="0.05" className="form-input"
                    value={modelConfig.top_p}
                    onChange={e => setModelConfig(prev => ({ ...prev, top_p: Number(e.target.value) }))}
                  />
                </div>
                <div>
                  <label className="form-label">Context Window</label>
                  <input
                    type="number" min="512" step="512" className="form-input"
                    value={modelConfig.context_window}
                    onChange={e => setModelConfig(prev => ({ ...prev, context_window: Number(e.target.value) }))}
                  />
                </div>
                <div>
                  <label className="form-label">Max Tokens</label>
                  <input
                    type="number" min="64" step="64" className="form-input"
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

              {/* Vision model — optional dedicated model for computer-use screenshot turns */}
              <div className="border-t border-slate-800 pt-4 space-y-3">
                <p className="text-xs text-slate-400">
                  Vision model (optional) — used for computer-use screenshot turns when the main model doesn't support images.
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="form-label" htmlFor="vision-provider">Vision Provider</label>
                    <select
                      id="vision-provider"
                      className="form-select"
                      value={modelConfig.vision_provider_id ?? ''}
                      onChange={e => setModelConfig(prev => ({
                        ...prev,
                        vision_provider_id: e.target.value || undefined,
                        vision_model: undefined,
                      }))}
                    >
                      <option value="">— same as main model —</option>
                      {providers.map(p => (
                        <option key={p.id} value={p.id}>{p.name} ({p.type})</option>
                      ))}
                    </select>
                  </div>
                  {modelConfig.vision_provider_id && (
                    <div>
                      <label className="form-label" htmlFor="vision-model">Vision Model</label>
                      {loadingVisionModels ? (
                        <p className="text-slate-500 text-sm py-2">Loading models…</p>
                      ) : visionModels.length > 0 ? (
                        <ModelPicker
                          id="vision-model"
                          models={visionModels}
                          value={modelConfig.vision_model ?? ''}
                          onChange={model => setModelConfig(prev => ({ ...prev, vision_model: model || undefined }))}
                          placeholder="e.g. gemma3:4b or qwen2.5vl:7b"
                        />
                      ) : (
                        <input
                          id="vision-model"
                          className="form-input"
                          value={modelConfig.vision_model ?? ''}
                          onChange={e => setModelConfig(prev => ({ ...prev, vision_model: e.target.value || undefined }))}
                          placeholder="e.g. gemma3:4b or qwen2.5vl:7b"
                        />
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Permissions master bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-slate-100">Capabilities &amp; access</p>
            <p className="text-xs text-slate-500">
              {totalGranted === 0 ? 'Nothing granted yet' : `${totalGranted} item${totalGranted === 1 ? '' : 's'} granted`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={grantEverything}
              className="btn-primary text-xs"
            >
              ⚡ Grant everything
            </button>
            <button
              type="button"
              onClick={revokeEverything}
              disabled={totalGranted === 0}
              className="btn-ghost text-xs disabled:opacity-40"
            >
              Revoke all
            </button>
          </div>
        </div>

        <MultiSelectSection
          title="Capabilities"
          icon="🛡️"
          hint="Capabilities grant groups of tools. Critical ones (amber) require approval in manual mode and are audit-logged."
          items={capabilityItems}
          selected={toolsConfig.capabilities}
          onChange={caps => setToolsConfig(prev => ({ ...prev, capabilities: caps }))}
          emptyText="No capabilities available."
        />

        <MultiSelectSection
          title="Skills"
          icon="🧩"
          hint="Skills shape the agent's behavior via the prompt — they don't execute code."
          items={skillItems}
          selected={selectedSkillIds}
          onChange={setSelectedSkillIds}
          emptyText="No skills available."
          showChips
        />

        <MultiSelectSection
          title="Plugins"
          icon="🔌"
          hint="Plugins add local tools and skills. Their tools still respect capabilities, explicit and blocked tools."
          items={pluginItems}
          selected={selectedPluginIds}
          onChange={setSelectedPluginIds}
          emptyText="No plugins installed."
        />

        <MultiSelectSection
          title="MCP Servers"
          icon="🛰️"
          hint="MCP servers add tools via local stdio processes. The server must be linked to the agent, and the tool still needs a capability or explicit grant."
          items={mcpItems}
          selected={selectedMcpServerIds}
          onChange={setSelectedMcpServerIds}
          emptyText="No MCP servers configured."
        />

        {/* Fine-grained overrides */}
        <section className="card space-y-4">
          <div className="flex items-center gap-2">
            <span aria-hidden>🎯</span>
            <h3 className="text-sm font-semibold text-slate-100">Fine-grained tool overrides</h3>
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
            <p className="text-xs text-slate-500 mt-1">Comma-separated. Always blocked, even if granted by a capability.</p>
          </div>
        </section>
      </form>

      {/* Sticky action bar */}
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <p className="text-xs text-slate-500">
            <span className="text-slate-300">{toolsConfig.capabilities.length}</span> caps ·{' '}
            <span className="text-slate-300">{selectedSkillIds.length}</span> skills ·{' '}
            <span className="text-slate-300">{selectedPluginIds.length}</span> plugins ·{' '}
            <span className="text-slate-300">{selectedMcpServerIds.length}</span> mcp
          </p>
          <div className="flex gap-2">
            <button type="button" className="btn-ghost" onClick={() => navigate('/agents')}>Cancel</button>
            <button type="submit" form="agent-form" className="btn-primary" disabled={saving}>
              {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Agent'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
