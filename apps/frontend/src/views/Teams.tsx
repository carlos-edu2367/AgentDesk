import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { agentsApi } from '../api/agents'
import { conversationsApi } from '../api/conversations'
import { skillsApi } from '../api/skills'
import { teamsApi } from '../api/teams'
import { mcpApi } from '../api/mcp'
import { usePrimaryTarget } from '../hooks/usePrimaryTarget'
import type { Agent, MCPServer, Skill, Team, TeamCreate } from '../types/domain'

const DEFAULT_TOOLS_POLICY = {
  inherit_from_agents: true,
  additional_capabilities: [],
  blocked_tools: [],
}

export function Teams() {
  const navigate = useNavigate()
  const { isPrimary, setPrimary } = usePrimaryTarget()
  const [teams, setTeams] = useState<Team[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [teamList, agentList, skillList, mcpList] = await Promise.all([
        teamsApi.list(),
        agentsApi.list(),
        skillsApi.list().catch(() => []),
        mcpApi.list().catch(() => []),
      ])
      setTeams(teamList)
      setAgents(agentList)
      setSkills(skillList)
      setMcpServers(mcpList)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const agentNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const agent of agents) map.set(agent.id, agent.name)
    return map
  }, [agents])

  const handleCreate = async (payload: TeamCreate) => {
    const created = await teamsApi.create(payload)
    if (payload.mcp_servers?.length && created?.id) {
      await teamsApi.updateMcp(created.id, payload.mcp_servers)
    }
    setShowForm(false)
    await load()
  }

  const handleChatTeam = async (team: Team) => {
    try {
      const existing = await conversationsApi.list({ type: 'team', target_id: team.id })
      if (existing[0]) {
        navigate(`/conversations/${existing[0].id}`)
        return
      }
      const conv = await conversationsApi.create({ type: 'team', target_id: team.id, title: team.name })
      navigate(`/conversations/${conv.id}`)
    } catch (e) {
      alert(`Failed to start chat: ${e}`)
    }
  }

  const handleDelete = async (team: Team) => {
    if (!confirm(`Delete team "${team.name}"?`)) return
    await teamsApi.delete(team.id)
    setTeams(prev => prev.filter(t => t.id !== team.id))
  }

  if (loading) return <LoadingState message="Loading teams..." />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <TopBar
        title="Teams"
        description="Create leader-managed groups of agents and run collaborative executions"
        actions={
          <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
            {showForm ? 'Close Form' : 'New Team'}
          </button>
        }
      />

      {showForm && (
        <div className="card mb-5">
          <TeamForm agents={agents} skills={skills} mcpServers={mcpServers} onSubmit={handleCreate} />
        </div>
      )}

      {teams.length === 0 ? (
        <EmptyState
          title="No teams yet"
          description="Create a team with a leader and at least one member to run multiagent work."
          action={<button className="btn-primary" onClick={() => setShowForm(true)}>Create Team</button>}
        />
      ) : (
        <div className="space-y-2">
          {teams.map(team => (
            <div key={team.id} className="card flex items-start justify-between gap-4 hover:bg-slate-800 transition-colors">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-100">{team.name}</p>
                {team.description && (
                  <p className="text-sm text-slate-400 mt-0.5 truncate">{team.description}</p>
                )}
                <div className="flex flex-wrap gap-3 mt-2 text-xs text-slate-500">
                  <span>Leader: {agentNameById.get(team.leader_agent_id) ?? team.leader_agent_id}</span>
                  <span>Members: {team.member_agent_ids.length}</span>
                  <span>Strategy: {team.execution_strategy}</span>
                  {(team.skills ?? []).length > 0 && <span>Skills: {(team.skills ?? []).length}</span>}
                  {team.memory_config.use_team_memory && <span>Team memory on</span>}
                </div>
              </div>
              <div className="flex gap-2 shrink-0 items-center">
                <button
                  className={`text-xs px-2 ${isPrimary('team', team.id) ? 'text-amber-400' : 'text-slate-500 hover:text-amber-400'}`}
                  title={isPrimary('team', team.id) ? 'Primary team' : 'Set as primary'}
                  aria-label={isPrimary('team', team.id) ? 'Primary team' : 'Set as primary'}
                  onClick={() => setPrimary({ type: 'team', id: team.id })}
                >
                  {isPrimary('team', team.id) ? '★' : '☆'}
                </button>
                <button className="btn-primary text-xs" onClick={() => handleChatTeam(team)}>
                  Chat
                </button>
                <button className="btn-danger text-xs" onClick={() => handleDelete(team)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TeamForm({
  agents,
  skills,
  mcpServers,
  onSubmit,
}: {
  agents: Agent[]
  skills: Skill[]
  mcpServers: MCPServer[]
  onSubmit: (payload: TeamCreate) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [leaderAgentId, setLeaderAgentId] = useState('')
  const [memberAgentIds, setMemberAgentIds] = useState<string[]>([])
  const [skillIds, setSkillIds] = useState<string[]>([])
  const [mcpServerIds, setMcpServerIds] = useState<string[]>([])
  const [useGlobal, setUseGlobal] = useState(true)
  const [useTeamMemory, setUseTeamMemory] = useState(true)
  const [allowMemberMemories, setAllowMemberMemories] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const toggleMember = (agentId: string) => {
    setMemberAgentIds(prev =>
      prev.includes(agentId) ? prev.filter(id => id !== agentId) : [...prev, agentId],
    )
  }

  const toggleSkill = (skillId: string) => {
    setSkillIds(prev =>
      prev.includes(skillId) ? prev.filter(id => id !== skillId) : [...prev, skillId],
    )
  }

  const toggleMcpServer = (serverId: string) => {
    setMcpServerIds(prev =>
      prev.includes(serverId) ? prev.filter(id => id !== serverId) : [...prev, serverId],
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !leaderAgentId) return
    setSubmitting(true)
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim(),
        leader_agent_id: leaderAgentId,
        member_agent_ids: memberAgentIds,
        skills: skillIds,
        execution_strategy: 'leader_managed',
        memory_config: {
          use_global: useGlobal,
          use_team_memory: useTeamMemory,
          allow_member_memories: allowMemberMemories,
        },
        tools_policy: DEFAULT_TOOLS_POLICY,
        mcp_servers: mcpServerIds,
      })
      setName('')
      setDescription('')
      setLeaderAgentId('')
      setMemberAgentIds([])
      setSkillIds([])
      setMcpServerIds([])
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="form-label" htmlFor="team-name">Name</label>
          <input id="team-name" className="form-input" value={name} onChange={e => setName(e.target.value)} required />
        </div>
        <div>
          <label className="form-label" htmlFor="leader-agent">Leader agent</label>
          <select
            id="leader-agent"
            className="form-select"
            value={leaderAgentId}
            onChange={e => setLeaderAgentId(e.target.value)}
            required
          >
            <option value="">Select leader...</option>
            {agents.map(agent => (
              <option key={agent.id} value={agent.id}>{agent.name}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="form-label" htmlFor="team-description">Description</label>
        <input
          id="team-description"
          className="form-input"
          value={description}
          onChange={e => setDescription(e.target.value)}
        />
      </div>

      <div>
        <p className="form-label">Members</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {agents.map(agent => (
            <label key={agent.id} className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
              <input
                aria-label={agent.name}
                type="checkbox"
                checked={memberAgentIds.includes(agent.id)}
                onChange={() => toggleMember(agent.id)}
              />
              <span>{agent.name}</span>
            </label>
          ))}
        </div>
      </div>

      <div>
        <p className="form-label">Team Skills</p>
        <p className="mb-2 text-xs text-slate-500">
          Team skills are injected alongside the executing agent skills.
        </p>
        {skills.length === 0 ? (
          <p className="text-sm text-slate-500">No skills available.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {skills.map(skill => (
              <label key={skill.id} className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                <input
                  aria-label={skill.name}
                  type="checkbox"
                  checked={skillIds.includes(skill.id)}
                  onChange={() => toggleSkill(skill.id)}
                />
                <span>{skill.name}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
          <input type="checkbox" checked={useGlobal} onChange={e => setUseGlobal(e.target.checked)} />
          <span>Use global memory</span>
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
          <input type="checkbox" checked={useTeamMemory} onChange={e => setUseTeamMemory(e.target.checked)} />
          <span>Use team memory</span>
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
          <input type="checkbox" checked={allowMemberMemories} onChange={e => setAllowMemberMemories(e.target.checked)} />
          <span>Member memories</span>
        </label>
      </div>

      <div>
        <p className="form-label">MCP Servers</p>
        {mcpServers.length === 0 ? (
          <p className="text-sm text-slate-500">No MCP servers available.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {mcpServers.map(server => (
              <label key={server.id} className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                <input
                  aria-label={`${server.name} ${server.enabled ? 'enabled' : 'disabled'}`}
                  type="checkbox"
                  checked={mcpServerIds.includes(server.id)}
                  onChange={() => toggleMcpServer(server.id)}
                />
                <span>{server.name}</span>
                <span className={server.enabled ? 'text-green-400 text-xs' : 'text-slate-500 text-xs'}>
                  {server.enabled ? 'enabled' : 'disabled'}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="flex justify-between items-center gap-3">
        <p className="text-xs text-slate-500">Strategy: leader_managed</p>
        <button type="submit" className="btn-primary" disabled={submitting || !name.trim() || !leaderAgentId}>
          {submitting ? 'Creating...' : 'Create Team'}
        </button>
      </div>
    </form>
  )
}
