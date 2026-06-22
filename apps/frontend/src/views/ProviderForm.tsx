import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { providersApi } from '../api/providers'
import type { ProviderType } from '../types/domain'

export function ProviderForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = Boolean(id)

  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [type, setType] = useState<ProviderType>('ollama')
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('http://localhost:11434')
  const [enabled, setEnabled] = useState(true)
  const [apiKey, setApiKey] = useState('')
  const [existingKeyMasked, setExistingKeyMasked] = useState(false)

  useEffect(() => {
    if (!isEdit || !id) return
    setLoading(true)
    providersApi.get(id)
      .then(p => {
        setType(p.type)
        setName(p.name)
        setBaseUrl(p.base_url ?? '')
        setEnabled(p.enabled)
        const key = p.config?.api_key as string | undefined
        if (key) {
          // Server returns masked key; show placeholder, don't pre-fill
          setExistingKeyMasked(true)
        }
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  useEffect(() => {
    if (!isEdit) {
      setBaseUrl(type === 'ollama' ? 'http://localhost:11434' : 'https://openrouter.ai/api/v1')
    }
  }, [type, isEdit])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const config: Record<string, unknown> = {}
      // Only include api_key if user explicitly typed a new one
      if (type === 'openrouter' && apiKey.trim() && !apiKey.includes('...')) {
        config.api_key = apiKey.trim()
      }

      const payload = { type, name, base_url: baseUrl, enabled, config }

      if (isEdit && id) {
        await providersApi.update(id, payload)
      } else {
        await providersApi.create(payload)
      }
      navigate('/config/providers')
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState />

  return (
    <div>
      <TopBar
        title={isEdit ? 'Edit Provider' : 'Add Provider'}
        actions={
          <button className="btn-ghost" onClick={() => navigate('/config/providers')}>
            Cancel
          </button>
        }
      />

      <form onSubmit={handleSubmit} className="space-y-5 max-w-xl">
        {error && (
          <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md p-3">
            {error}
          </div>
        )}

        <div>
          <label className="form-label">Type *</label>
          <select className="form-select" value={type} onChange={e => setType(e.target.value as ProviderType)} disabled={isEdit}>
            <option value="ollama">Ollama (local)</option>
            <option value="openrouter">OpenRouter (remote)</option>
          </select>
        </div>

        <div>
          <label className="form-label">Name *</label>
          <input
            className="form-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder={type === 'ollama' ? 'Local Ollama' : 'OpenRouter'}
            required
          />
        </div>

        <div>
          <label className="form-label">Base URL</label>
          <input
            className="form-input"
            value={baseUrl}
            onChange={e => setBaseUrl(e.target.value)}
            placeholder={type === 'ollama' ? 'http://localhost:11434' : 'https://openrouter.ai/api/v1'}
          />
        </div>

        {type === 'openrouter' && (
          <div>
            <label className="form-label">
              API Key {existingKeyMasked && <span className="text-slate-500">(leave blank to keep existing)</span>}
            </label>
            <input
              type="password"
              className="form-input"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={existingKeyMasked ? 'Enter new key to replace existing' : 'sk-or-...'}
              autoComplete="off"
            />
            <p className="text-xs text-slate-500 mt-1">Never stored in plaintext in logs or UI.</p>
          </div>
        )}

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={e => setEnabled(e.target.checked)}
            className="rounded border-slate-600 bg-slate-800 text-blue-500"
          />
          <span className="text-sm text-slate-300">Enabled</span>
        </label>

        <div className="flex gap-3">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Add Provider'}
          </button>
          <button type="button" className="btn-ghost" onClick={() => navigate('/config/providers')}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
