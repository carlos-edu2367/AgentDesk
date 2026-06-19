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
    setForm(EMPTY_FORM)
    setArgsText('')
    setEnvText('{}')
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
      <TopBar title="MCP Servers" />

      <section className="mb-5 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">
        <p className="text-sm text-amber-300">
          MCP servers executam processos locais. Cadastre apenas servidores confiaveis.
        </p>
      </section>

      <form onSubmit={submit} className="card mb-6 space-y-3">
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
              placeholder="npx"
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
            placeholder={"-y\n@modelcontextprotocol/server-filesystem\nC:/Projetos"}
          />
        </div>

        <div>
          <label className="form-label" htmlFor="mcp-env">Env JSON</label>
          <textarea
            id="mcp-env"
            className="form-textarea font-mono text-sm"
            value={envText}
            onChange={e => setEnvText(e.target.value)}
            aria-invalid={!parsedEnv}
          />
          {!parsedEnv && <p className="mt-1 text-xs text-red-400">Env must be a JSON object.</p>}
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={e => setForm(prev => ({ ...prev, enabled: e.target.checked }))}
            className="rounded border-slate-600 bg-slate-800 text-blue-500"
          />
          Enabled
        </label>

        {error && (
          <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md p-3">
            {error}
          </div>
        )}

        <div className="flex gap-2">
          <button className="btn-primary" disabled={saving || !parsedEnv}>
            {saving ? 'Working...' : editingId ? 'Save Server' : 'Create Server'}
          </button>
          {editingId && (
            <button type="button" className="btn-ghost" onClick={resetForm}>
              Cancel Edit
            </button>
          )}
        </div>
      </form>

      <section className="space-y-3">
        {servers.length === 0 ? (
          <div className="card text-sm text-slate-500">No MCP servers configured.</div>
        ) : servers.map(server => (
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
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-semibold text-slate-100">{server.name}</h2>
            <span className="font-mono text-xs text-slate-500">{server.id}</span>
            <span className={`rounded px-2 py-0.5 text-xs ${server.enabled ? 'bg-green-500/15 text-green-300' : 'bg-slate-700 text-slate-400'}`}>
              {server.enabled ? 'enabled' : 'disabled'}
            </span>
            <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-400">{server.transport}</span>
          </div>
          <p className="mt-1 font-mono text-xs text-slate-500">{server.command} {(server.args ?? []).join(' ')}</p>
          {server.last_connected_at && (
            <p className="mt-1 text-xs text-slate-500">Last connected: {new Date(server.last_connected_at).toLocaleString()}</p>
          )}
          {server.last_error && <p className="mt-1 text-xs text-red-400">{server.last_error}</p>}
          {status === 'ok' && <p className="mt-1 text-xs text-green-400">Connection OK. {testResult?.tools.length ?? 0} tools detected.</p>}
          {status === 'error' && <p className="mt-1 text-xs text-red-400">{testResult?.error?.message}</p>}
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
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

      <div className="mt-4">
        <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Detected tools</p>
        {tools.length === 0 ? (
          <p className="text-xs text-slate-600">Run Test to populate tools.</p>
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
