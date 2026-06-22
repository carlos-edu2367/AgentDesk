import { Navigate, NavLink, useParams } from 'react-router-dom'
import { Providers } from './Providers'
import { Workspaces } from './Workspaces'
import { Tools } from './Tools'
import { McpServers } from './McpServers'
import { Skills } from './Skills'
import { Plugins } from './Plugins'
import { Memory } from './Memory'
import { Executions } from './Executions'
import { AuditLogs } from './AuditLogs'
import { Settings } from './Settings'

type Item = { slug: string; label: string; el: JSX.Element }
type Group = { group: string; items: Item[] }

const GROUPS: Group[] = [
  { group: 'Modelos & Acesso', items: [
    { slug: 'providers', label: 'Providers', el: <Providers /> },
    { slug: 'workspaces', label: 'Workspaces', el: <Workspaces /> },
  ]},
  { group: 'Capacidades', items: [
    { slug: 'tools', label: 'Tools', el: <Tools /> },
    { slug: 'mcp', label: 'MCP Servers', el: <McpServers /> },
    { slug: 'skills', label: 'Skills', el: <Skills /> },
    { slug: 'plugins', label: 'Plugins', el: <Plugins /> },
    { slug: 'memory', label: 'Memory', el: <Memory /> },
  ]},
  { group: 'Atividade', items: [
    { slug: 'executions', label: 'Executions', el: <Executions /> },
    { slug: 'audit', label: 'Audit Logs', el: <AuditLogs /> },
  ]},
  { group: 'Sistema', items: [
    { slug: 'system', label: 'Geral', el: <Settings /> },
  ]},
]

const ALL = GROUPS.flatMap(g => g.items)

export function Config() {
  const { section } = useParams<{ section: string }>()
  const active = ALL.find(i => i.slug === section)
  if (!active) return <Navigate to="/config/providers" replace />

  return (
    <div className="flex gap-6">
      <nav className="w-48 shrink-0 space-y-4">
        {GROUPS.map(g => (
          <div key={g.group}>
            <p className="px-2 mb-1 text-xs uppercase tracking-wider text-slate-600">{g.group}</p>
            <div className="space-y-0.5">
              {g.items.map(item => (
                <NavLink
                  key={item.slug}
                  to={`/config/${item.slug}`}
                  className={({ isActive }) =>
                    `block px-3 py-1.5 rounded-md text-sm transition-colors ${
                      isActive ? 'bg-blue-600/20 text-blue-300 font-medium' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="flex-1 min-w-0">{active.el}</div>
    </div>
  )
}
