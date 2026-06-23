import { useEffect, useState } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import { useBackendHealth } from '../hooks/useBackendHealth'
import { useActiveExecutions } from '../hooks/useActiveExecutions'
import { usePrimaryTarget } from '../hooks/usePrimaryTarget'
import { conversationsApi } from '../api/conversations'
import { agentsApi } from '../api/agents'
import { teamsApi } from '../api/teams'
import type { Conversation } from '../types/domain'

const FOOTER_LINKS = [
  { path: '/agents', label: 'Agents' },
  { path: '/teams', label: 'Teams' },
  { path: '/config', label: 'Configurações' },
]

export function Sidebar() {
  const { status } = useBackendHealth()
  const { conversationIds: activeConversationIds } = useActiveExecutions()
  const { primary } = usePrimaryTarget()
  const navigate = useNavigate()
  const location = useLocation()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [targets, setTargets] = useState<{ type: 'agent' | 'team'; id: string; name: string }[]>([])

  const loadConversations = () =>
    conversationsApi.list({ limit: 50 }).then(setConversations).catch(() => setConversations([]))

  useEffect(() => { loadConversations() }, [])

  const startChat = async (type: 'agent' | 'team', id: string, title: string) => {
    try {
      const conv = await conversationsApi.create({ type, target_id: id, title })
      await loadConversations()
      navigate(`/conversations/${conv.id}`)
    } catch (e) {
      alert(`Failed to start chat: ${e}`)
    }
  }

  const handleNewChat = async () => {
    if (!primary) { navigate('/agents'); return }
    const name =
      primary.type === 'agent'
        ? (await agentsApi.list().catch(() => [])).find(a => a.id === primary.id)?.name
        : (await teamsApi.list().catch(() => [])).find(t => t.id === primary.id)?.name
    if (!name) { navigate('/agents'); return }
    startChat(primary.type, primary.id, name)
  }

  const deleteChat = async (e: React.MouseEvent, c: Conversation) => {
    // The row is a NavLink; don't navigate into the chat we're deleting.
    e.preventDefault()
    e.stopPropagation()
    if (deletingId) return
    if (!window.confirm(`Excluir a conversa "${c.title || 'Untitled chat'}"? Esta ação não pode ser desfeita.`)) {
      return
    }
    setDeletingId(c.id)
    try {
      await conversationsApi.delete(c.id)
      setConversations(prev => prev.filter(x => x.id !== c.id))
      // If we're currently viewing the deleted chat, leave it.
      if (location.pathname === `/conversations/${c.id}`) {
        navigate('/agents')
      }
    } catch (err) {
      alert(`Falha ao excluir a conversa: ${err}`)
    } finally {
      setDeletingId(null)
    }
  }

  const openPicker = async () => {
    const [agents, teams] = await Promise.all([
      agentsApi.list().catch(() => []),
      teamsApi.list().catch(() => []),
    ])
    setTargets([
      ...agents.map(a => ({ type: 'agent' as const, id: a.id, name: a.name })),
      ...teams.map(t => ({ type: 'team' as const, id: t.id, name: t.name })),
    ])
    setPickerOpen(v => !v)
  }

  return (
    <aside className="w-64 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col h-screen">
      <div className="px-4 py-4 border-b border-slate-800">
        <span className="text-base font-bold text-slate-100 tracking-tight">AgentDesk</span>
        <div className="mt-1"><StatusBadge status={status} /></div>
      </div>

      <div className="px-3 py-3 border-b border-slate-800 relative">
        <div className="flex gap-1">
          <button className="btn-primary text-sm flex-1" onClick={handleNewChat}>+ Novo chat</button>
          <button className="btn-secondary text-sm px-2" aria-label="Escolher agente" onClick={openPicker}>▾</button>
        </div>
        {pickerOpen && (
          <div className="absolute left-3 right-3 mt-1 z-10 bg-slate-800 border border-slate-700 rounded-md max-h-64 overflow-y-auto">
            {targets.length === 0 ? (
              <p className="px-3 py-2 text-xs text-slate-500">Nenhum agente ou team.</p>
            ) : targets.map(t => (
              <button
                key={`${t.type}:${t.id}`}
                className="block w-full text-left px-3 py-2 text-sm text-slate-300 hover:bg-slate-700"
                onClick={() => { setPickerOpen(false); startChat(t.type, t.id, t.name) }}
              >
                <span className="text-xs text-slate-500 mr-1">{t.type === 'agent' ? '👤' : '👥'}</span>{t.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        <p className="px-2 mb-1 text-xs uppercase tracking-wider text-slate-600">Conversas</p>
        {conversations.length === 0 ? (
          <p className="px-2 text-xs text-slate-600">Nenhuma conversa ainda.</p>
        ) : conversations.map(c => {
          const running = activeConversationIds.has(c.id)
          return (
            <div key={c.id} className="group relative">
              <NavLink
                to={`/conversations/${c.id}`}
                className={({ isActive }) =>
                  `flex items-center gap-2 pl-3 pr-8 py-2 rounded-md text-sm transition-colors ${
                    isActive ? 'bg-blue-600/20 text-blue-300' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'
                  }`
                }
              >
                {running && (
                  <span
                    className="w-1.5 h-1.5 shrink-0 rounded-full bg-blue-400 animate-pulse"
                    title="Agent working"
                    aria-label="Agent working"
                  />
                )}
                <span className="truncate">{c.title || 'Untitled chat'}</span>
              </NavLink>
              <button
                type="button"
                aria-label={`Excluir conversa ${c.title || 'Untitled chat'}`}
                title="Excluir conversa"
                disabled={deletingId === c.id}
                onClick={e => deleteChat(e, c)}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 opacity-0 transition-opacity hover:bg-slate-700 hover:text-red-300 focus:opacity-100 group-hover:opacity-100 disabled:opacity-50"
              >
                {deletingId === c.id ? '…' : '🗑'}
              </button>
            </div>
          )
        })}
      </nav>

      <nav className="px-2 py-2 border-t border-slate-800 space-y-0.5">
        {FOOTER_LINKS.map(({ path, label }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-md text-sm transition-colors ${
                isActive ? 'bg-blue-600/20 text-blue-300 font-medium' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-2 border-t border-slate-800">
        <p className="text-xs text-slate-600">v0.1.0 - MVP</p>
      </div>
    </aside>
  )
}
