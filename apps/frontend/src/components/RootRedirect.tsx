import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingState } from './LoadingState'
import { usePrimaryTarget } from '../hooks/usePrimaryTarget'
import { agentsApi } from '../api/agents'
import { teamsApi } from '../api/teams'
import { conversationsApi } from '../api/conversations'

export function RootRedirect() {
  const navigate = useNavigate()
  const { primary, clearPrimary } = usePrimaryTarget()

  useEffect(() => {
    let cancelled = false
    const goAgents = () => { if (!cancelled) navigate('/agents', { replace: true }) }

    async function run() {
      if (!primary) return goAgents()
      try {
        const name =
          primary.type === 'agent'
            ? (await agentsApi.list()).find(a => a.id === primary.id)?.name
            : (await teamsApi.list()).find(t => t.id === primary.id)?.name
        if (name === undefined) {
          clearPrimary()
          return goAgents()
        }
        const conv = await conversationsApi.create({
          type: primary.type,
          target_id: primary.id,
          title: name,
        })
        if (!cancelled) navigate(`/conversations/${conv.id}`, { replace: true })
      } catch {
        goAgents()
      }
    }

    run()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return <LoadingState message="Abrindo chat..." />
}
