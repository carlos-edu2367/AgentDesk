import { useEffect, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { toolsApi } from '../api/tools'
import type { ToolDefinition, CapabilityInfo } from '../types/domain'

export function Tools() {
  const [tools, setTools] = useState<ToolDefinition[]>([])
  const [capabilities, setCapabilities] = useState<CapabilityInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([toolsApi.list(), toolsApi.listCapabilities()])
      .then(([t, c]) => { setTools(t); setCapabilities(c) })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />
  const coreTools = tools.filter(tool => tool.source === 'core')
  const pluginTools = tools.filter(tool => tool.source === 'plugin')
  const mcpTools = tools.filter(tool => tool.source === 'mcp')
  const otherTools = tools.filter(tool => tool.source !== 'core' && tool.source !== 'plugin' && tool.source !== 'mcp')

  return (
    <div>
      <TopBar title="Tools" />

      {/* Capabilities */}
      <section className="mb-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Capabilities</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {capabilities.map(cap => (
            <div key={cap.name} className="card">
              <p className="text-sm font-medium text-blue-300 mb-1">{cap.name}</p>
              <ul className="space-y-0.5">
                {cap.tools.map(t => (
                  <li key={t} className="text-xs text-slate-400 font-mono">{t}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">
          Core Tools <span className="text-slate-500 font-normal">({coreTools.length})</span>
        </h2>
        <div className="space-y-2">
          {coreTools.map(tool => (
            <ToolRow key={tool.name} tool={tool} />
          ))}
        </div>
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">
          Plugin Tools <span className="text-slate-500 font-normal">({pluginTools.length})</span>
        </h2>
        <div className="space-y-2">
          {pluginTools.length === 0 ? (
            <div className="card text-sm text-slate-500">No plugin tools registered.</div>
          ) : pluginTools.map(tool => (
            <ToolRow key={tool.name} tool={tool} />
          ))}
        </div>
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">
          MCP Tools <span className="text-slate-500 font-normal">({mcpTools.length})</span>
        </h2>
        <div className="space-y-2">
          {mcpTools.length === 0 ? (
            <div className="card text-sm text-slate-500">No MCP tools registered. Test an MCP server to populate tools.</div>
          ) : mcpTools.map(tool => (
            <ToolRow key={tool.name} tool={tool} />
          ))}
        </div>
      </section>

      {otherTools.length > 0 && (
        <section className="mb-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">
            Other Tools <span className="text-slate-500 font-normal">({otherTools.length})</span>
          </h2>
          <div className="space-y-2">
            {otherTools.map(tool => (
              <ToolRow key={tool.name} tool={tool} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function ToolRow({ tool }: { tool: ToolDefinition }) {
  const [expanded, setExpanded] = useState(false)
  const hasSchema = Object.keys(tool.input_schema).length > 0

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-sm text-slate-100">{tool.name}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">
              {tool.capability}
            </span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-500">
              {tool.source}
            </span>
            {tool.plugin_id && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300">
                {tool.plugin_id}
              </span>
            )}
            {tool.server_id && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300">
                {tool.server_id}
              </span>
            )}
            {tool.critical && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">
                critical
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">{tool.description}</p>
        </div>
        {hasSchema && (
          <button
            className="shrink-0 text-slate-500 hover:text-slate-300 text-xs transition-colors"
            onClick={() => setExpanded(v => !v)}
          >
            {expanded ? 'hide args ▲' : 'args ▼'}
          </button>
        )}
      </div>
      {expanded && hasSchema && (
        <pre className="mt-2 text-xs text-slate-400 bg-slate-900/50 rounded p-2 overflow-x-auto">
          {JSON.stringify(tool.input_schema, null, 2)}
        </pre>
      )}
    </div>
  )
}
