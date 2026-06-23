import { useState, useEffect, useCallback } from 'react'
import { executionsApi } from '../api/executions'
import type { Execution, ExecutionStatus } from '../types/domain'

// Statuses where a turn is still in flight: the engine keeps working (or is
// paused waiting on the user) even with the chat closed. Used to surface a live
// indicator across the app so the user knows an agent is busy while they're off
// tweaking config, adding models, etc.
const ACTIVE_STATUSES: ReadonlySet<ExecutionStatus> = new Set([
  'pending',
  'running',
  'waiting_approval',
])

export interface ActiveExecutions {
  /** Conversation ids that currently have an in-flight execution. */
  conversationIds: Set<string>
  /** `${type}:${target_id}` keys with an in-flight execution. */
  targetKeys: Set<string>
  refresh: () => void
}

/**
 * Polls the backend for in-flight executions. Backend runs turns in background
 * tasks (independent of any open SSE stream), so this reflects work that
 * continues after a chat is closed.
 */
export function useActiveExecutions(intervalMs = 4000): ActiveExecutions {
  const [conversationIds, setConversationIds] = useState<Set<string>>(new Set())
  const [targetKeys, setTargetKeys] = useState<Set<string>>(new Set())

  const refresh = useCallback(async () => {
    try {
      const rows = await executionsApi.list({ limit: 100 })
      const convs = new Set<string>()
      const targets = new Set<string>()
      for (const ex of rows as Execution[]) {
        if (!ACTIVE_STATUSES.has(ex.status)) continue
        if (ex.conversation_id) convs.add(ex.conversation_id)
        targets.add(`${ex.type}:${ex.target_id}`)
      }
      setConversationIds(prev => (setsEqual(prev, convs) ? prev : convs))
      setTargetKeys(prev => (setsEqual(prev, targets) ? prev : targets))
    } catch {
      // Transient backend hiccup: keep the previous snapshot rather than
      // clearing indicators and flickering.
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, intervalMs)
    return () => clearInterval(id)
  }, [refresh, intervalMs])

  return { conversationIds, targetKeys, refresh }
}

function setsEqual(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false
  for (const v of a) if (!b.has(v)) return false
  return true
}
