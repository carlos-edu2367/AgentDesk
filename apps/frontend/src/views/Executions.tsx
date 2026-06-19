import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { StatusBadge } from '../components/StatusBadge'
import { executionsApi } from '../api/executions'
import type { ApprovalMode, Execution, ExecutionFilters, ExecutionStatus } from '../types/domain'

const FILTER_OPTIONS: Array<ExecutionStatus | 'all'> = [
  'all', 'pending', 'running', 'completed', 'failed', 'cancelled',
]

export function Executions() {
  const navigate = useNavigate()
  const [executions, setExecutions] = useState<Execution[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<ExecutionStatus | 'all'>('all')
  const [draftFilters, setDraftFilters] = useState<ExecutionFilters>({ limit: 100 })
  const [exportingId, setExportingId] = useState<string | null>(null)

  const load = async (filters?: ExecutionFilters) => {
    setLoading(true)
    setError(null)
    try {
      const data = await executionsApi.list(filters)
      setExecutions(data)
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

  const applyFilters = async () => {
    const next = {
      ...draftFilters,
      status: draftFilters.status || undefined,
      type: draftFilters.type || undefined,
      approval_mode: draftFilters.approval_mode || undefined,
      query: draftFilters.query || undefined,
      limit: draftFilters.limit ?? 100,
    }
    await load(next)
  }

  const handleExport = async (event: React.MouseEvent, execution: Execution, format: 'json' | 'markdown') => {
    event.stopPropagation()
    setExportingId(`${execution.id}:${format}`)
    try {
      await executionsApi.export(execution.id, format)
    } finally {
      setExportingId(null)
    }
  }

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
      <div className="card mb-4">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <label className="form-label" htmlFor="execution-query">Search executions</label>
            <input
              id="execution-query"
              className="form-input"
              value={draftFilters.query ?? ''}
              onChange={e => setDraftFilters(prev => ({ ...prev, query: e.target.value }))}
            />
          </div>
          <div>
            <label className="form-label" htmlFor="execution-status">Status</label>
            <select
              id="execution-status"
              className="form-select"
              value={draftFilters.status ?? ''}
              onChange={e => setDraftFilters(prev => ({ ...prev, status: e.target.value as ExecutionStatus | '' }))}
            >
              <option value="">All</option>
              {FILTER_OPTIONS.filter(f => f !== 'all').map(status => <option key={status} value={status}>{status}</option>)}
            </select>
          </div>
          <div>
            <label className="form-label" htmlFor="execution-type">Type</label>
            <select
              id="execution-type"
              className="form-select"
              value={draftFilters.type ?? ''}
              onChange={e => setDraftFilters(prev => ({ ...prev, type: e.target.value as 'agent' | 'team' | '' }))}
            >
              <option value="">All</option>
              <option value="agent">agent</option>
              <option value="team">team</option>
            </select>
          </div>
          <div>
            <label className="form-label" htmlFor="execution-approval-mode">Approval mode</label>
            <select
              id="execution-approval-mode"
              className="form-select"
              value={draftFilters.approval_mode ?? ''}
              onChange={e => setDraftFilters(prev => ({ ...prev, approval_mode: e.target.value as ApprovalMode | '' }))}
            >
              <option value="">All</option>
              <option value="manual">manual</option>
              <option value="auto">auto</option>
            </select>
          </div>
          <div className="flex items-end">
            <button className="btn-primary w-full" onClick={applyFilters}>Apply Filters</button>
          </div>
        </div>
      </div>

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
              <div className="flex flex-col gap-2 shrink-0" onClick={event => event.stopPropagation()}>
                <button
                  className="btn-secondary text-xs"
                  disabled={exportingId === `${ex.id}:json`}
                  onClick={event => handleExport(event, ex, 'json')}
                >
                  Export JSON
                </button>
                <button
                  className="btn-secondary text-xs"
                  disabled={exportingId === `${ex.id}:markdown`}
                  onClick={event => handleExport(event, ex, 'markdown')}
                >
                  Export Markdown
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
