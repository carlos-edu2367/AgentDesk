import { useEffect, useMemo, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { mcpApi } from '../api/mcp'
import type { MCPServer, MCPServerCreate, MCPTestResponse } from '../types/domain'

const EMPTY_FORM: MCPServerCreate = {
  id: '',
  name: '',
  enabled: true,
  transport: 'stdio',
  command: '',
  args: [],
  env: {},
}

export function McpServers() {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [form, setForm] = useState<MCPServerCreate>(EMPTY_FORM)
  const [argsText, setArgsText] = useState('')
  const [envText, setEnvText] = useState('{}')
  const [query, setQuery] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, MCPTestResponse>>({})

  const load = () => {
    setLoading(true)
    mcpApi.list()
      .then(setServers)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const parsedEnv = useMemo(() => {
    try {
      const value = JSON.parse(envText || '{}')
      return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, string> : null
    } catch {
      return null
    }
  }, [envText])

  const totalTools = useMemo(
    () => servers.reduce((total, server) => total + (server.tools_cache_json?.length ?? 0), 0),
    [servers],
  )

  const filteredServers = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return servers
    return servers.filter(server => {
      const command = [server.command, ...(server.args ?? [])].join(' ').toLowerCase()
      return server.name.toLowerCase().includes(needle)
        || server.id.toLowerCase().includes(needle)
        || command.includes(needle)
        || (server.tools_cache_json ?? []).some(tool => tool.name.toLowerCase().includes(needle))
    })
  }, [query, servers])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!parsedEnv) {
      setError('Env must be a JSON object.')
      return
    }
    setSaving(true)
    setError(null)
    const payload = {
      ...form,
      args: argsText.split(/\r?\n/).map(item => item.trim()).filter(Boolean),
      env: parsedEnv,
    }
    try {
      if (editingId) {
        await mcpApi.update(editingId, payload)
      } else {
        await mcpApi.create(payload)
      }
      resetForm()
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const edit = (server: MCPServer) => {
    setEditingId(server.id)
    setShowForm(true)
    setForm({
      id: server.id,
      name: server.name,
      enabled: server.enabled,
      transport: server.transport,
      command: server.command,
      args: server.args ?? [],
      env: server.env ?? {},
    })
    setArgsText((server.args ?? []).join('\n'))
    setEnvText(JSON.stringify(server.env ?? {}, null, 2))
  }

  const resetForm = () => {
    setEditingId(null)
    setShowForm(false)
    setForm(EMPTY_FORM)
    setArgsText('')
    setEnvText('{}')
  }

  const startCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setArgsText('')
    setEnvText('{}')
    setShowForm(true)
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

  const testServer = async (id: string) => {
    setSaving(true)
    setError(null)
    try {
      const result = await mcpApi.test(id)
      setTestResults(prev => ({ ...prev, [id]: result }))
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState />
  if (error && servers.length === 0) return <ErrorState message={error} />

  return (
    <div>
      <TopBar
        title="MCP Servers"
        description={`${servers.length} servers, ${totalTools} detected tools`}
        actions={<button className="btn-primary" onClick={startCreate}>Add MCP server</button>}
      />

      <section className="mb-5 grid gap-3 lg:grid-cols-[1fr_320px]">
        <div className="card space-y-3">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-100">MCP servers run local processes. Test before assigning them to agents.</p>
              <p className="mt-1 text-xs text-slate-500">Stdio is the current supported transport. Tool calls still pass through AgentDesk permissions and audit logs.</p>
            </div>
            <div className="flex gap-2 text-xs">
              <Stat value={String(servers.filter(server => server.enabled).length)} label="enabled" />
              <Stat value={String(totalTools)} label="tools" />
            </div>
          </div>
          <input
            className="form-input"
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search servers, commands, IDs, or tools"
          />
        </div>
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-200">
          Only add servers from trusted folders or packages. Environment values are stored in the server config, so avoid secrets unless the backend masking and local storage model are acceptable for this install.
        </div>
      </section>

      {showForm && (
        <form onSubmit={submit} className="card mb-6 space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-slate-100">{editingId ? 'Edit MCP server' : 'Add MCP server'}</h2>
              <p className="mt-1 text-sm text-slate-500">Use one argument per line. Keep env as a JSON object.</p>
            </div>
            <button type="button" className="btn-ghost" onClick={resetForm}>Close</button>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="form-label" htmlFor="mcp-id">ID</label>
              <input
                id="mcp-id"
                className="form-input font-mono text-sm"
                value={form.id}
                onChange={e => setForm(prev => ({ ...prev, id: e.target.value }))}
                placeholder="filesystem"
                disabled={Boolean(editingId)}
                required
              />
            </div>
            <div>
              <label className="form-label" htmlFor="mcp-name">Name</label>
              <input
                id="mcp-name"
                className="form-input"
                value={form.name}
                onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="Filesystem MCP"
                required
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-[160px_1fr]">
            <div>
              <label className="form-label" htmlFor="mcp-transport">Transport</label>
              <select id="mcp-transport" className="form-select" value={form.transport} disabled>
                <option value="stdio">stdio</option>
              </select>
            </div>
            <div>
              <label className="form-label" htmlFor="mcp-command">Command</label>
              <input
                id="mcp-command"
                className="form-input font-mono text-sm"
                value={form.command}
                onChange={e => setForm(prev => ({ ...prev, command: e.target.value }))}
                placeholder="python"
                required
              />
            </div>
          </div>

          <div>
            <label className="form-label" htmlFor="mcp-args">Args</label>
            <textarea
              id="mcp-args"
              className="form-textarea font-mono text-sm"
              value={argsText}
              onChange={e => setArgsText(e.target.value)}
              placeholder="examples/mcp/mock-mcp-server.py"
            />
            <p className="mt-1 text-xs text-slate-500">Example for npx servers: -y on one line, package name on the next, then allowed paths.</p>
          </div>

          <div>
            <label className="form-label" htmlFor="mcp-env">Env JSON</label>
            <textarea
              id="mcp-env"
              className="form-textarea min-h-[68px] font-mono text-sm"
              value={envText}
              onChange={e => setEnvText(e.target.value)}
              placeholder='{"NODE_ENV":"production"}'
              aria-invalid={!parsedEnv}
            />
            {!parsedEnv && <p className="mt-1 text-xs text-red-400">Env must be a JSON object.</p>}
          </div>

          <div className="flex flex-col gap-3 border-t border-slate-800 pt-4 md:flex-row md:items-center md:justify-between">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={e => setForm(prev => ({ ...prev, enabled: e.target.checked }))}
                className="rounded border-slate-600 bg-slate-800 text-blue-500"
              />
              Enabled after save
            </label>
            <div className="flex gap-2">
              <button className="btn-primary" disabled={saving || !parsedEnv}>
                {saving ? 'Working...' : editingId ? 'Save Server' : 'Create Server'}
              </button>
              <button type="button" className="btn-ghost" onClick={resetForm}>
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {error && (
        <div className="mb-4 rounded-md border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <section className="space-y-3">
        {servers.length === 0 ? (
          <div className="card text-sm text-slate-500">No MCP servers configured. Add the mock server first if you want a safe smoke test.</div>
        ) : filteredServers.length === 0 ? (
          <div className="card text-sm text-slate-500">No MCP servers match this search.</div>
        ) : filteredServers.map(server => (
          <ServerCard
            key={server.id}
            server={server}
            disabled={saving}
            testResult={testResults[server.id]}
            onEdit={() => edit(server)}
            onTest={() => testServer(server.id)}
            onEnable={() => mutate(() => mcpApi.enable(server.id))}
            onDisable={() => mutate(() => mcpApi.disable(server.id))}
            onDelete={() => mutate(() => mcpApi.delete(server.id))}
          />
        ))}
      </section>
    </div>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <span className="rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 text-center">
      <span className="block text-sm font-semibold text-slate-100">{value}</span>
      <span className="text-slate-500">{label}</span>
    </span>
  )
}

function ServerCard({
  server, disabled, testResult, onEdit, onTest, onEnable, onDisable, onDelete,
}: {
  server: MCPServer
  disabled: boolean
  testResult?: MCPTestResponse
  onEdit: () => void
  onTest: () => void
  onEnable: () => void
  onDisable: () => void
  onDelete: () => void
}) {
  const tools = server.tools_cache_json ?? []
  const status = testResult?.status

  return (
    <div className="card">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-semibold text-slate-100">{server.name}</h2>
            <span className="font-mono text-xs text-slate-500">{server.id}</span>
            <span className={`rounded px-2 py-0.5 text-xs ${server.enabled ? 'bg-green-500/15 text-green-300' : 'bg-slate-700 text-slate-400'}`}>
              {server.enabled ? 'enabled' : 'disabled'}
            </span>
            <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-400">{server.transport}</span>
          </div>
          <p className="mt-1 break-all font-mono text-xs text-slate-500">{server.command} {(server.args ?? []).join(' ')}</p>
          {server.last_connected_at && (
            <p className="mt-1 text-xs text-slate-500">Last connected: {new Date(server.last_connected_at).toLocaleString()}</p>
          )}
          {server.last_error && <p className="mt-1 text-xs text-red-400">{server.last_error}</p>}
          {status === 'ok' && <p className="mt-1 text-xs text-green-400">Connection OK. {testResult?.tools.length ?? 0} tools detected.</p>}
          {status === 'error' && <p className="mt-1 text-xs text-red-400">{testResult?.error?.message}</p>}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 lg:justify-end">
          <button className="btn-ghost text-xs" disabled={disabled} onClick={onEdit}>Edit</button>
          <button className="btn-ghost text-xs" disabled={disabled} onClick={onTest}>Test</button>
          {server.enabled ? (
            <button className="btn-ghost text-xs" disabled={disabled} onClick={onDisable}>Disable</button>
          ) : (
            <button className="btn-primary text-xs" disabled={disabled} onClick={onEnable}>Enable</button>
          )}
          <button className="btn-danger text-xs" disabled={disabled} onClick={onDelete}>Remove</button>
        </div>
      </div>

      <div className="mt-4 border-t border-slate-800 pt-4">
        <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Detected tools ({tools.length})</p>
        {tools.length === 0 ? (
          <p className="text-xs text-slate-600">Run Test to detect and cache tools.</p>
        ) : (
          <div className="space-y-2">
            {tools.map(tool => (
              <div key={tool.name} className="rounded border border-slate-800 bg-slate-900/40 p-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-slate-200">{tool.name}</span>
                  <span className="rounded bg-red-500/15 px-1.5 py-0.5 text-xs text-red-300">critical</span>
                  <span className="rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-400">mcp.{server.id}</span>
                </div>
                {tool.description && <p className="mt-1 text-xs text-slate-500">{tool.description}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
