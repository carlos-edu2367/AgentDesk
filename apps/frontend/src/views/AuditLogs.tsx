import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { auditApi } from '../api/audit'
import type { AuditLog, AuditLogFilters } from '../types/domain'

const RISK_LEVELS = ['', 'low', 'medium', 'high', 'critical']

const RISK_CLASSES: Record<string, string> = {
  low: 'bg-green-500/10 text-green-300 border-green-500/30',
  medium: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  high: 'bg-red-500/10 text-red-300 border-red-500/30',
  critical: 'bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/30',
}

export function AuditLogs() {
  const navigate = useNavigate()
  const [items, setItems] = useState<AuditLog[]>([])
  const [selected, setSelected] = useState<AuditLog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<AuditLogFilters>({ limit: 50, offset: 0 })
  const [draft, setDraft] = useState<AuditLogFilters>({ limit: 50, offset: 0 })

  const load = async (nextFilters = filters) => {
    setLoading(true)
    setError(null)
    try {
      const response = await auditApi.list(nextFilters)
      setItems(response.items)
      setTotal(response.total)
      setSelected(response.items[0] ?? null)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const applyFilters = async () => {
    const next = { ...draft, offset: 0, limit: draft.limit ?? 50 }
    setFilters(next)
    await load(next)
  }

  if (loading) return <LoadingState message="Loading audit logs..." />
  if (error) return <ErrorState message={error} onRetry={() => load()} />

  return (
    <div>
      <TopBar title="Audit Logs" description="Inspect sensitive actions, tools, approvals, plugins and MCP activity" />

      <div className="card mb-4">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <label className="form-label" htmlFor="audit-query">Search audit logs</label>
            <input
              id="audit-query"
              className="form-input"
              value={draft.query ?? ''}
              onChange={e => setDraft(prev => ({ ...prev, query: e.target.value }))}
            />
          </div>
          <div>
            <label className="form-label" htmlFor="audit-risk">Risk level</label>
            <select
              id="audit-risk"
              className="form-select"
              value={draft.risk_level ?? ''}
              onChange={e => setDraft(prev => ({ ...prev, risk_level: e.target.value }))}
            >
              {RISK_LEVELS.map(level => (
                <option key={level || 'all'} value={level}>{level || 'All'}</option>
              ))}
            </select>
          </div>
          <FilterInput id="audit-event-type" label="Event type" value={draft.event_type} onChange={event_type => setDraft(prev => ({ ...prev, event_type }))} />
          <FilterInput id="audit-agent" label="Agent" value={draft.agent_id} onChange={agent_id => setDraft(prev => ({ ...prev, agent_id }))} />
          <FilterInput id="audit-team" label="Team" value={draft.team_id} onChange={team_id => setDraft(prev => ({ ...prev, team_id }))} />
          <FilterInput id="audit-tool" label="Tool" value={draft.tool} onChange={tool => setDraft(prev => ({ ...prev, tool }))} />
          <FilterInput id="audit-date-from" label="Date from" type="date" value={draft.date_from} onChange={date_from => setDraft(prev => ({ ...prev, date_from }))} />
          <FilterInput id="audit-date-to" label="Date to" type="date" value={draft.date_to} onChange={date_to => setDraft(prev => ({ ...prev, date_to }))} />
          <div className="flex items-end">
            <button className="btn-primary w-full" onClick={applyFilters}>Apply Filters</button>
          </div>
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState title="No audit logs found" description="Try changing filters or run an agent/tool first." />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_420px] gap-4">
          <section className="space-y-2">
            <p className="text-xs text-slate-500">{total} audit logs</p>
            {items.map(item => (
              <button
                key={item.id}
                className="card w-full text-left hover:bg-slate-800 transition-colors"
                onClick={() => setSelected(item)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm text-slate-100 truncate">{item.summary}</p>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>{new Date(item.created_at).toLocaleString()}</span>
                      <span>{item.event_type}</span>
                      {item.source && <span>{item.source}</span>}
                      {item.tool && <span className="font-mono">{item.tool}</span>}
                      {item.execution_id && <span>{item.execution_id}</span>}
                    </div>
                  </div>
                  <RiskBadge risk={item.risk_level} />
                </div>
              </button>
            ))}
          </section>

          <aside className="card h-fit">
            {!selected ? (
              <p className="text-sm text-slate-500">Select an audit log.</p>
            ) : (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-100">{selected.event_type}</p>
                    <p className="text-xs text-slate-500">{selected.id}</p>
                  </div>
                  <RiskBadge risk={selected.risk_level} />
                </div>
                <p className="text-sm text-slate-300">{selected.summary}</p>
                <dl className="grid grid-cols-2 gap-2 text-xs">
                  <Meta label="Execution" value={selected.execution_id} />
                  <Meta label="Agent" value={selected.agent_id} />
                  <Meta label="Team" value={selected.team_id ?? ''} />
                  <Meta label="Tool" value={selected.tool ?? ''} />
                  <Meta label="Source" value={selected.source ?? ''} />
                  <Meta label="Status" value={selected.status ?? ''} />
                </dl>
                <pre className="text-xs text-slate-400 bg-slate-950 rounded p-3 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(selected.data, null, 2)}
                </pre>
                <button className="btn-secondary w-full" onClick={() => navigate(`/executions/${selected.execution_id}`)}>
                  Open Execution
                </button>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}

function FilterInput({
  id, label, value, onChange, type = 'text',
}: {
  id: string
  label: string
  value?: string
  type?: string
  onChange: (value: string) => void
}) {
  return (
    <div>
      <label className="form-label" htmlFor={id}>{label}</label>
      <input id={id} type={type} className="form-input" value={value ?? ''} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function RiskBadge({ risk }: { risk: string }) {
  return (
    <span className={`text-xs px-2 py-1 rounded border ${RISK_CLASSES[risk] ?? RISK_CLASSES.low}`}>
      {risk}
    </span>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-300 break-all">{value || '-'}</dd>
    </div>
  )
}
