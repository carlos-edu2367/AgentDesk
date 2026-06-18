import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { workspacesApi } from '../api/workspaces'
import type { Workspace } from '../types/domain'

export function Workspaces() {
  const navigate = useNavigate()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setWorkspaces(await workspacesApi.list())
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete workspace "${name}"?`)) return
    try {
      await workspacesApi.delete(id)
      setWorkspaces(prev => prev.filter(w => w.id !== id))
    } catch (e) {
      alert(`Failed to delete: ${e}`)
    }
  }

  const permLabel = (perms: Workspace['permissions']) => {
    const active = Object.entries(perms)
      .filter(([, v]) => v)
      .map(([k]) => k)
    return active.length ? active.join(', ') : 'none'
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <TopBar
        title="Workspaces"
        description="File system paths agents are allowed to access"
        actions={
          <button className="btn-primary" onClick={() => navigate('/workspaces/new')}>
            New Workspace
          </button>
        }
      />

      {workspaces.length === 0 ? (
        <EmptyState
          title="No workspaces"
          description="Add a workspace to allow agents to access your files."
          action={
            <button className="btn-primary" onClick={() => navigate('/workspaces/new')}>
              Add Workspace
            </button>
          }
        />
      ) : (
        <div className="space-y-2">
          {workspaces.map(w => (
            <div key={w.id} className="card flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-100">{w.name}</p>
                <div className="mt-1 space-y-0.5">
                  {w.paths.map(p => (
                    <p key={p} className="text-xs text-slate-400 font-mono truncate">{p}</p>
                  ))}
                </div>
                <p className="text-xs text-slate-500 mt-1">Permissions: {permLabel(w.permissions)}</p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button className="btn-ghost text-xs" onClick={() => navigate(`/workspaces/${w.id}/edit`)}>
                  Edit
                </button>
                <button className="btn-danger text-xs" onClick={() => handleDelete(w.id, w.name)}>
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
