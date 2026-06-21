import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { conversationsApi } from '../api/conversations'
import type { Conversation } from '../types/domain'

function formatUpdatedAt(value: string) {
  if (!value) return 'Unknown date'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function Conversations() {
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setConversations(await conversationsApi.list({ limit: 100 }))
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <LoadingState message="Loading chats..." />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <TopBar
        title="Chats"
        description="Reopen previous conversations and continue with their saved context"
      />

      {conversations.length === 0 ? (
        <EmptyState
          title="No chats yet"
          description="Start a chat from an agent or team to build conversation history."
        />
      ) : (
        <div className="space-y-2">
          {conversations.map(conversation => (
            <div
              key={conversation.id}
              className="card flex items-start justify-between gap-4 hover:bg-slate-800 transition-colors"
            >
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-100 truncate">
                  {conversation.title || 'Untitled chat'}
                </p>
                <div className="flex flex-wrap gap-3 mt-1 text-xs text-slate-500">
                  <span className="capitalize">{conversation.type}</span>
                  <span>Target: {conversation.target_id}</span>
                  <span>Updated: {formatUpdatedAt(conversation.updated_at)}</span>
                </div>
              </div>
              <button
                className="btn-primary text-xs shrink-0"
                onClick={() => navigate(`/conversations/${conversation.id}`)}
              >
                Open
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
