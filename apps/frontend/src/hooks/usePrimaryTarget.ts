import { useCallback, useEffect, useState } from 'react'

export type PrimaryTarget = { type: 'agent' | 'team'; id: string }

const KEY = 'agentdesk.primaryTarget'
const EVENT = 'agentdesk:primary-changed'

function read(): PrimaryTarget | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && (parsed.type === 'agent' || parsed.type === 'team') && typeof parsed.id === 'string') {
      return { type: parsed.type, id: parsed.id }
    }
    return null
  } catch {
    return null
  }
}

export function usePrimaryTarget() {
  const [primary, setPrimaryState] = useState<PrimaryTarget | null>(() => read())

  useEffect(() => {
    const sync = () => setPrimaryState(read())
    window.addEventListener(EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  const setPrimary = useCallback((target: PrimaryTarget) => {
    localStorage.setItem(KEY, JSON.stringify(target))
    window.dispatchEvent(new Event(EVENT))
  }, [])

  const clearPrimary = useCallback(() => {
    localStorage.removeItem(KEY)
    window.dispatchEvent(new Event(EVENT))
  }, [])

  const isPrimary = useCallback(
    (type: PrimaryTarget['type'], id: string) => primary?.type === type && primary?.id === id,
    [primary],
  )

  return { primary, setPrimary, clearPrimary, isPrimary }
}
