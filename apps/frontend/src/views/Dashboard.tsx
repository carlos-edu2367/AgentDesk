import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { healthApi, storageApi } from '../api/storage'
import { agentsApi } from '../api/agents'
import { providersApi } from '../api/providers'
import { workspacesApi } from '../api/workspaces'
import { executionsApi } from '../api/executions'
import type { Execution, StorageInfo } from '../types/domain'

interface DashboardData {
  backendStatus: string
  storage: StorageInfo | null
  agentCount: number
  providerCount: number
  workspaceCount: number
  recentExecutions: Execution[]
}

export function Dashboard() {
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [health, storage, agents, providers, workspaces, executions] = await Promise.allSettled([
          healthApi.check(),
          storageApi.info(),
          agentsApi.list(),
          providersApi.list(),
          workspacesApi.list(),
          executionsApi.list(),
        ])

        if (cancelled) return

        setData({
          backendStatus: health.status === 'fulfilled' ? health.value.status : 'offline',
          storage: storage.status === 'fulfilled' ? storage.value : null,
          agentCount: agents.status === 'fulfilled' ? agents.value.length : 0,
          providerCount: providers.status === 'fulfilled' ? providers.value.length : 0,
          workspaceCount: workspaces.status === 'fulfilled' ? workspaces.value.length : 0,
          recentExecutions: executions.status === 'fulfilled'
            ? executions.value.slice(-5).reverse()
            : [],
        })
      } catch (e) {
        if (!cancelled) setError(String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  if (loading) return <LoadingState message="Loading dashboard..." />

  if (error) return (
    <div className="text-red-400 text-sm p-4 bg-red-500/10 rounded-lg">{error}</div>
  )

  return (
    <div>
      <TopBar
        title="Dashboard"
        description="System overview and quick actions"
        actions={
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => navigate('/agents/new')}>
              New Agent
            </button>
            <button className="btn-primary" onClick={() => navigate('/executions/run')}>
              Run Agent
            </button>
          </div>
        }
      />

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        <StatCard label="Backend" value={<StatusBadge status={data?.backendStatus ?? 'offline'} />} />
        <StatCard label="Agents" value={String(data?.agentCount ?? 0)} onClick={() => navigate('/agents')} />
        <StatCard label="Providers" value={String(data?.providerCount ?? 0)} onClick={() => navigate('/providers')} />
        <StatCard label="Workspaces" value={String(data?.workspaceCount ?? 0)} onClick={() => navigate('/workspaces')} />
        <StatCard label="Executions" value={String(data?.recentExecutions?.length ?? 0)} onClick={() => navigate('/executions')} />
        {data?.storage && (
          <StatCard
            label="AppData"
            value={<span className="text-xs text-slate-400 truncate">{data.storage.appdata_path}</span>}
          />
        )}
      </div>

      {/* Recent executions */}
      <div className="card">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Recent Executions</h2>
        {data?.recentExecutions?.length === 0 ? (
          <p className="text-slate-500 text-sm">No executions yet.</p>
        ) : (
          <div className="space-y-2">
            {data?.recentExecutions?.map(ex => (
              <div
                key={ex.id}
                className="flex items-center justify-between p-2 rounded-md hover:bg-slate-800 cursor-pointer transition-colors"
                onClick={() => navigate(`/executions/${ex.id}`)}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-200 truncate">{ex.user_input}</p>
                  <p className="text-xs text-slate-500">{new Date(ex.created_at).toLocaleString()}</p>
                </div>
                <StatusBadge status={ex.status} className="ml-3 shrink-0" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, onClick }: { label: string; value: React.ReactNode; onClick?: () => void }) {
  return (
    <div
      className={`card flex flex-col gap-1 ${onClick ? 'cursor-pointer hover:bg-slate-800 transition-colors' : ''}`}
      onClick={onClick}
    >
      <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
      <span className="text-lg font-semibold text-slate-100">{value}</span>
    </div>
  )
}
