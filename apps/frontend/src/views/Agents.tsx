import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { agentsApi } from '../api/agents'
import { conversationsApi } from '../api/conversations'
import type { Agent } from '../types/domain'

export function Agents() {
  const navigate = useNavigate()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setAgents(await agentsApi.list())
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete agent "${name}"?`)) return
    try {
      await agentsApi.delete(id)
      setAgents(prev => prev.filter(a => a.id !== id))
    } catch (e) {
      alert(`Failed to delete: ${e}`)
    }
  }

  const handleChat = async (agent: Agent) => {
    try {
      const conv = await conversationsApi.create({ type: 'agent', target_id: agent.id, title: agent.name })
      navigate(`/conversations/${conv.id}`)
    } catch (e) {
      alert(`Failed to start chat: ${e}`)
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <TopBar
        title="Agents"
        description="Configure and manage your AI agents"
        actions={
          <button className="btn-primary" onClick={() => navigate('/agents/new')}>
            New Agent
          </button>
        }
      />

      {agents.length === 0 ? (
        <EmptyState
          title="No agents yet"
          description="Create your first agent to get started."
          action={
            <button className="btn-primary" onClick={() => navigate('/agents/new')}>
              Create Agent
            </button>
          }
        />
      ) : (
        <div className="space-y-2">
          {agents.map(agent => (
            <div key={agent.id} className="card flex items-start justify-between gap-4 hover:bg-slate-800 transition-colors">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-100">{agent.name}</p>
                {agent.description && (
                  <p className="text-sm text-slate-400 mt-0.5 truncate">{agent.description}</p>
                )}
                <div className="flex gap-3 mt-1 text-xs text-slate-500">
                  <span>Model: {agent.model_config.model}</span>
                  <span>Temp: {agent.model_config.temperature}</span>
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  className="btn-primary text-xs"
                  onClick={() => handleChat(agent)}
                >
                  Chat
                </button>
                <button
                  className="btn-secondary text-xs"
                  onClick={() => navigate(`/executions/run?agent=${agent.id}`)}
                >
                  Run
                </button>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => navigate(`/agents/${agent.id}/edit`)}
                >
                  Edit
                </button>
                <button
                  className="btn-danger text-xs"
                  onClick={() => handleDelete(agent.id, agent.name)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
