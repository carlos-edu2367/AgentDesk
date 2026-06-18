import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { agentsApi } from '../api/agents'
import { providersApi } from '../api/providers'
import type { ModelConfig, Provider, ModelInfo } from '../types/domain'

const DEFAULT_MODEL_CONFIG: ModelConfig = {
  provider_id: '',
  model: '',
  temperature: 0.4,
  top_p: 0.9,
  context_window: 8192,
  max_tokens: 2048,
  stream: true,
}

export function AgentForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = Boolean(id)

  const [providers, setProviders] = useState<Provider[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [modelConfig, setModelConfig] = useState<ModelConfig>(DEFAULT_MODEL_CONFIG)

  useEffect(() => {
    providersApi.list().then(setProviders).catch(() => {})
  }, [])

  useEffect(() => {
    if (!isEdit || !id) return
    setLoading(true)
    agentsApi.get(id)
      .then(agent => {
        setName(agent.name)
        setDescription(agent.description)
        setSystemPrompt(agent.system_prompt)
        setModelConfig(agent.model_config)
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
      if (isEdit && id) {
        await agentsApi.update(id, payload)
      } else {
        await agentsApi.create(payload)
      }
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
              <label className="form-label">Provider *</label>
              <select
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
              <label className="form-label">Model *</label>
              {loadingModels ? (
                <p className="text-slate-500 text-sm">Loading models...</p>
              ) : models.length > 0 ? (
                <select
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
