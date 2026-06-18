import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { agentsApi } from '../api/agents'
import { workspacesApi } from '../api/workspaces'
import { executionsApi } from '../api/executions'
import type { Agent, Workspace, ApprovalMode } from '../types/domain'

export function RunAgent() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const preselectedAgentId = searchParams.get('agent') ?? ''

  const [agents, setAgents] = useState<Agent[]>([])
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loadingData, setLoadingData] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [agentId, setAgentId] = useState(preselectedAgentId)
  const [message, setMessage] = useState('')
  const [approvalMode, setApprovalMode] = useState<ApprovalMode>('manual')
  const [selectedWorkspaces, setSelectedWorkspaces] = useState<string[]>([])
  const [stream, setStream] = useState(true)

  useEffect(() => {
    Promise.allSettled([agentsApi.list(), workspacesApi.list()])
      .then(([a, w]) => {
        if (a.status === 'fulfilled') setAgents(a.value)
        if (w.status === 'fulfilled') setWorkspaces(w.value)
      })
      .finally(() => setLoadingData(false))
  }, [])

  const toggleWorkspace = (id: string) => {
    setSelectedWorkspaces(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!agentId || !message.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await executionsApi.runAgent({
        agent_id: agentId,
        message: message.trim(),
        approval_mode: approvalMode,
        workspace_ids: selectedWorkspaces,
        stream,
      })
      navigate(`/executions/${result.execution_id}`)
    } catch (e) {
      setError(String(e))
      setSubmitting(false)
    }
  }

  if (loadingData) return <LoadingState message="Loading agents..." />

  return (
    <div>
      <TopBar
        title="Run Agent"
        actions={<button className="btn-ghost" onClick={() => navigate('/executions')}>Cancel</button>}
      />

      <form onSubmit={handleSubmit} className="space-y-5 max-w-2xl">
        {error && (
          <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md p-3">
            {error}
          </div>
        )}

        <div>
          <label className="form-label">Agent *</label>
          <select
            className="form-select"
            value={agentId}
            onChange={e => setAgentId(e.target.value)}
            required
          >
            <option value="">Select an agent...</option>
            {agents.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {agents.length === 0 && (
            <p className="text-xs text-amber-400 mt-1">
              No agents available.{' '}
              <button type="button" className="underline" onClick={() => navigate('/agents/new')}>
                Create one first.
              </button>
            </p>
          )}
        </div>

        <div>
          <label className="form-label">Message *</label>
          <textarea
            className="form-textarea min-h-[100px]"
            value={message}
            onChange={e => setMessage(e.target.value)}
            placeholder="What should the agent do?"
            required
          />
        </div>

        <div>
          <label className="form-label">Approval Mode</label>
          <div className="flex gap-3">
            {(['manual', 'auto'] as ApprovalMode[]).map(m => (
              <label key={m} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="approval_mode"
                  value={m}
                  checked={approvalMode === m}
                  onChange={() => setApprovalMode(m)}
                  className="text-blue-500"
                />
                <span className="text-sm text-slate-300 capitalize">{m}</span>
              </label>
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Manual: critical actions pause for approval. Auto: all actions execute automatically.
          </p>
        </div>

        {workspaces.length > 0 && (
          <div>
            <label className="form-label">Workspaces (optional)</label>
            <div className="space-y-2">
              {workspaces.map(w => (
                <label key={w.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedWorkspaces.includes(w.id)}
                    onChange={() => toggleWorkspace(w.id)}
                    className="rounded border-slate-600 bg-slate-800 text-blue-500"
                  />
                  <span className="text-sm text-slate-300">{w.name}</span>
                  <span className="text-xs text-slate-500">{w.paths[0]}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={stream}
            onChange={e => setStream(e.target.checked)}
            className="rounded border-slate-600 bg-slate-800 text-blue-500"
          />
          <span className="text-sm text-slate-300">Enable streaming</span>
        </label>

        <div className="flex gap-3">
          <button type="submit" className="btn-primary" disabled={submitting || !agentId || !message.trim()}>
            {submitting ? 'Starting...' : 'Run Agent'}
          </button>
          <button type="button" className="btn-ghost" onClick={() => navigate('/executions')}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
