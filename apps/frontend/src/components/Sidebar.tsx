import { NavLink } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import { useBackendHealth } from '../hooks/useBackendHealth'

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', exact: true },
  { path: '/agents', label: 'Agents' },
  { path: '/teams', label: 'Teams' },
  { path: '/providers', label: 'Providers' },
  { path: '/workspaces', label: 'Workspaces' },
  { path: '/executions', label: 'Executions' },
  { path: '/conversations', label: 'Chats' },
  { path: '/tools', label: 'Tools' },
  { path: '/mcp', label: 'MCP Servers' },
  { path: '/memory', label: 'Memory' },
  { path: '/skills', label: 'Skills' },
  { path: '/plugins', label: 'Plugins' },
  { path: '/audit', label: 'Audit Logs' },
  { path: '/settings', label: 'Settings' },
]

export function Sidebar() {
  const { status } = useBackendHealth()

  return (
    <aside className="w-52 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col h-screen">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-slate-800">
        <span className="text-base font-bold text-slate-100 tracking-tight">AgentDesk</span>
        <div className="mt-1">
          <StatusBadge status={status} />
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ path, label, exact }) => (
          <NavLink
            key={path}
            to={path}
            end={exact}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600/20 text-blue-300 font-medium'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-800">
        <p className="text-xs text-slate-600">v0.1.0 - MVP</p>
      </div>
    </aside>
  )
}
