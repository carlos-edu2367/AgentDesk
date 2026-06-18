import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { StatusBadge } from '../components/StatusBadge'
import { executionsApi } from '../api/executions'
import type { Execution, ExecutionStatus } from '../types/domain'

const FILTER_OPTIONS: Array<ExecutionStatus | 'all'> = [
  'all', 'pending', 'running', 'completed', 'failed', 'cancelled',
]

export function Executions() {
  const navigate = useNavigate()
  const [executions, setExecutions] = useState<Execution[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<ExecutionStatus | 'all'>('all')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await executionsApi.list()
      setExecutions(data.slice().reverse())
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = filter === 'all'
    ? executions
    : executions.filter(e => e.status === filter)

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <TopBar
        title="Executions"
        description="History of agent runs"
        actions={
          <button className="btn-primary" onClick={() => navigate('/executions/run')}>
            Run Agent
          </button>
        }
      />

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 flex-wrap">
        {FILTER_OPTIONS.map(f => (
          <button
            key={f}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-slate-100'
            }`}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'All' : f.replace('_', ' ')}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title={filter === 'all' ? 'No executions yet' : `No ${filter} executions`}
          description={filter === 'all' ? 'Run an agent to see executions here.' : undefined}
          action={
            filter === 'all' ? (
              <button className="btn-primary" onClick={() => navigate('/executions/run')}>
                Run Agent
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-2">
          {filtered.map(ex => (
            <div
              key={ex.id}
              className="card flex items-start justify-between gap-4 cursor-pointer hover:bg-slate-800 transition-colors"
              onClick={() => navigate(`/executions/${ex.id}`)}
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-200 truncate">{ex.user_input}</p>
                <div className="flex gap-3 mt-1 text-xs text-slate-500">
                  <span>{new Date(ex.created_at).toLocaleString()}</span>
                  <span>{ex.type}</span>
                  {ex.completed_at && (
                    <span>
                      {Math.round(
                        (new Date(ex.completed_at).getTime() - new Date(ex.created_at).getTime()) / 1000,
                      )}s
                    </span>
                  )}
                </div>
              </div>
              <StatusBadge status={ex.status} className="shrink-0" />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
