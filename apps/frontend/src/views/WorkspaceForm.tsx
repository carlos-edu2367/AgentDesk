import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { workspacesApi } from '../api/workspaces'
import type { WorkspacePermissions } from '../types/domain'

const DEFAULT_PERMISSIONS: WorkspacePermissions = {
  read: true,
  write: true,
  delete: false,
  execute: false,
}

export function WorkspaceForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = Boolean(id)

  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [pathInput, setPathInput] = useState('')
  const [paths, setPaths] = useState<string[]>([])
  const [permissions, setPermissions] = useState<WorkspacePermissions>(DEFAULT_PERMISSIONS)

  useEffect(() => {
    if (!isEdit || !id) return
    workspacesApi.get(id)
      .then(w => {
        setName(w.name)
        setPaths(w.paths)
        setPermissions(w.permissions)
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  const addPath = () => {
    const p = pathInput.trim()
    if (p && !paths.includes(p)) {
      setPaths(prev => [...prev, p])
      setPathInput('')
    }
  }

  const removePath = (p: string) => setPaths(prev => prev.filter(x => x !== p))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = { name, paths, permissions }
      if (isEdit && id) {
        await workspacesApi.update(id, payload)
      } else {
        await workspacesApi.create(payload)
      }
      navigate('/config/workspaces')
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
        title={isEdit ? 'Edit Workspace' : 'New Workspace'}
        actions={<button className="btn-ghost" onClick={() => navigate('/config/workspaces')}>Cancel</button>}
      />

      <form onSubmit={handleSubmit} className="space-y-5 max-w-xl">
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
            placeholder="e.g. Projects"
            required
          />
        </div>

        <div>
          <label className="form-label">Paths</label>
          <div className="flex gap-2">
            <input
              className="form-input flex-1"
              value={pathInput}
              onChange={e => setPathInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addPath() } }}
              placeholder="C:\Users\Carlos\Projects"
            />
            <button type="button" className="btn-secondary" onClick={addPath}>Add</button>
          </div>
          {paths.length > 0 && (
            <ul className="mt-2 space-y-1">
              {paths.map(p => (
                <li key={p} className="flex items-center justify-between bg-slate-800 rounded px-3 py-1.5">
                  <span className="text-xs text-slate-300 font-mono truncate">{p}</span>
                  <button type="button" className="text-slate-500 hover:text-red-400 ml-2 text-xs" onClick={() => removePath(p)}>
                    remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <fieldset className="border border-slate-700 rounded-lg p-4">
          <legend className="text-sm font-medium text-slate-300 px-1">Permissions</legend>
          <div className="grid grid-cols-2 gap-3 mt-2">
            {(Object.keys(DEFAULT_PERMISSIONS) as (keyof WorkspacePermissions)[]).map(perm => (
              <label key={perm} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={permissions[perm]}
                  onChange={e => setPermissions(prev => ({ ...prev, [perm]: e.target.checked }))}
                  className="rounded border-slate-600 bg-slate-800 text-blue-500"
                />
                <span className="text-sm text-slate-300 capitalize">{perm}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex gap-3">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Workspace'}
          </button>
          <button type="button" className="btn-ghost" onClick={() => navigate('/config/workspaces')}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
