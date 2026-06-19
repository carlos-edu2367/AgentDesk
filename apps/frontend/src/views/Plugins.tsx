import { useEffect, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { pluginsApi } from '../api/plugins'
import type { Plugin } from '../types/domain'

export function Plugins() {
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [path, setPath] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    pluginsApi.list()
      .then(setPlugins)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const importPlugin = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await pluginsApi.importPlugin(path)
      setPath('')
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const mutate = async (action: () => Promise<unknown>) => {
    setSaving(true)
    setError(null)
    try {
      await action()
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState />
  if (error && plugins.length === 0) return <ErrorState message={error} />

  return (
    <div>
      <TopBar title="Plugins" />

      <section className="mb-5 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">
        <p className="text-sm text-amber-300">
          Plugins podem executar codigo local. Instale apenas plugins confiaveis.
        </p>
      </section>

      <form onSubmit={importPlugin} className="card mb-6 space-y-3">
        <div>
          <label className="form-label" htmlFor="plugin-path">Plugin folder path</label>
          <input
            id="plugin-path"
            className="form-input font-mono text-sm"
            value={path}
            onChange={e => setPath(e.target.value)}
            placeholder="C:/Users/Carlos/Desktop/my-plugin"
            required
          />
        </div>
        {error && (
          <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md p-3">
            {error}
          </div>
        )}
        <button className="btn-primary" disabled={saving || !path.trim()}>
          {saving ? 'Working...' : 'Import Plugin'}
        </button>
      </form>

      <section className="space-y-3">
        {plugins.length === 0 ? (
          <div className="card">
            <p className="text-sm text-slate-500">No plugins installed.</p>
          </div>
        ) : (
          plugins.map(plugin => (
            <PluginCard
              key={plugin.id}
              plugin={plugin}
              disabled={saving}
              onEnable={() => mutate(() => pluginsApi.enable(plugin.id))}
              onDisable={() => mutate(() => pluginsApi.disable(plugin.id))}
              onDelete={() => mutate(() => pluginsApi.delete(plugin.id))}
            />
          ))
        )}
      </section>
    </div>
  )
}

function PluginCard({
  plugin, disabled, onEnable, onDisable, onDelete,
}: {
  plugin: Plugin
  disabled: boolean
  onEnable: () => void
  onDisable: () => void
  onDelete: () => void
}) {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-semibold text-slate-100">{plugin.name}</h2>
            <span className="font-mono text-xs text-slate-500">{plugin.id}</span>
            <span className={`rounded px-2 py-0.5 text-xs ${plugin.enabled ? 'bg-green-500/15 text-green-300' : 'bg-slate-700 text-slate-400'}`}>
              {plugin.enabled ? 'enabled' : 'disabled'}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-400">{plugin.description}</p>
          <p className="mt-1 font-mono text-xs text-slate-600">{plugin.manifest_path}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          {plugin.enabled ? (
            <button className="btn-ghost text-xs" disabled={disabled} onClick={onDisable}>Disable</button>
          ) : (
            <button className="btn-primary text-xs" disabled={disabled} onClick={onEnable}>Enable</button>
          )}
          <button className="btn-danger text-xs" disabled={disabled} onClick={onDelete}>Remove</button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <ManifestSection title="Permissions" items={plugin.permissions} />
        <ManifestSection title="Tools" items={(plugin.tools_json ?? []).map(tool => tool.name)} />
        <ManifestSection title="Skills" items={(plugin.skills_json ?? []).map(skill => skill.id)} />
      </div>

      {(plugin.tools_json ?? []).length > 0 && (
        <div className="mt-4 space-y-2">
          {(plugin.tools_json ?? []).map(tool => (
            <div key={tool.name} className="rounded border border-slate-800 bg-slate-900/40 p-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs text-slate-200">{tool.name}</span>
                <span className="rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-400">{tool.capability}</span>
                {tool.critical && <span className="rounded bg-red-500/15 px-1.5 py-0.5 text-xs text-red-300">critical</span>}
              </div>
              {tool.description && <p className="mt-1 text-xs text-slate-500">{tool.description}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ManifestSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase text-slate-500">{title}</p>
      {items.length === 0 ? (
        <p className="text-xs text-slate-600">None</p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {items.map(item => (
            <span key={item} className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
              {item}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
