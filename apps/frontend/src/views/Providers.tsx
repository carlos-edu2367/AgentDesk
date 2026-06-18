import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { StatusBadge } from '../components/StatusBadge'
import { providersApi } from '../api/providers'
import type { Provider, ProviderHealth } from '../types/domain'

export function Providers() {
  const navigate = useNavigate()
  const [providers, setProviders] = useState<Provider[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [healthResults, setHealthResults] = useState<Record<string, ProviderHealth>>({})
  const [checking, setChecking] = useState<Record<string, boolean>>({})

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setProviders(await providersApi.list())
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const checkHealth = async (id: string) => {
    setChecking(prev => ({ ...prev, [id]: true }))
    try {
      const h = await providersApi.health(id)
      setHealthResults(prev => ({ ...prev, [id]: h }))
    } catch {
      setHealthResults(prev => ({ ...prev, [id]: { healthy: false, error: 'Request failed' } }))
    } finally {
      setChecking(prev => ({ ...prev, [id]: false }))
    }
  }

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete provider "${name}"?`)) return
    try {
      await providersApi.delete(id)
      setProviders(prev => prev.filter(p => p.id !== id))
    } catch (e) {
      alert(`Failed to delete: ${e}`)
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <TopBar
        title="Providers"
        description="Model providers (Ollama, OpenRouter)"
        actions={
          <button className="btn-primary" onClick={() => navigate('/providers/new')}>
            Add Provider
          </button>
        }
      />

      {providers.length === 0 ? (
        <EmptyState
          title="No providers configured"
          description="Add Ollama or OpenRouter to start running agents."
          action={
            <button className="btn-primary" onClick={() => navigate('/providers/new')}>
              Add Provider
            </button>
          }
        />
      ) : (
        <div className="space-y-2">
          {providers.map(p => {
            const health = healthResults[p.id]
            return (
              <div key={p.id} className="card flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-slate-100">{p.name}</p>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">{p.type}</span>
                    {!p.enabled && <StatusBadge status="cancelled" />}
                  </div>
                  {p.base_url && (
                    <p className="text-xs text-slate-500 mt-0.5">{p.base_url}</p>
                  )}
                  {p.type === 'openrouter' && p.config?.api_key != null && (
                    <p className="text-xs text-slate-500">Key: {String(p.config.api_key)}</p>
                  )}
                  {health && (
                    <div className="flex items-center gap-2 mt-1">
                      <StatusBadge status={health.healthy ? 'online' : 'offline'} />
                      {health.latency_ms != null && (
                        <span className="text-xs text-slate-500">{health.latency_ms}ms</span>
                      )}
                      {health.error && (
                        <span className="text-xs text-red-400">{health.error}</span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 shrink-0 flex-wrap justify-end">
                  <button
                    className="btn-secondary text-xs"
                    onClick={() => checkHealth(p.id)}
                    disabled={checking[p.id]}
                  >
                    {checking[p.id] ? 'Checking...' : 'Health Check'}
                  </button>
                  <button className="btn-ghost text-xs" onClick={() => navigate(`/providers/${p.id}/edit`)}>
                    Edit
                  </button>
                  <button className="btn-danger text-xs" onClick={() => handleDelete(p.id, p.name)}>
                    Delete
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
