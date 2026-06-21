import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { agentsApi } from '../api/agents'
import { conversationsApi } from '../api/conversations'
import { executionsApi } from '../api/executions'
import { skillsApi } from '../api/skills'
import { teamsApi } from '../api/teams'
import { mcpApi } from '../api/mcp'
import { workspacesApi } from '../api/workspaces'
import type { Agent, ApprovalMode, MCPServer, Skill, Team, TeamCreate, Workspace } from '../types/domain'

const DEFAULT_TOOLS_POLICY = {
  inherit_from_agents: true,
  additional_capabilities: [],
  blocked_tools: [],
}

export function Teams() {
  const navigate = useNavigate()
  const [teams, setTeams] = useState<Team[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([])
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [selectedTeamId, setSelectedTeamId] = useState('')
  const [message, setMessage] = useState('')
  const [approvalMode, setApprovalMode] = useState<ApprovalMode>('manual')
  const [selectedWorkspaces, setSelectedWorkspaces] = useState<string[]>([])
  const [stream, setStream] = useState(true)
  const [submittingExecution, setSubmittingExecution] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [teamList, agentList, workspaceList, skillList, mcpList] = await Promise.all([
        teamsApi.list(),
        agentsApi.list(),
        workspacesApi.list(),
        skillsApi.list().catch(() => []),
        mcpApi.list().catch(() => []),
      ])
      setTeams(teamList)
      setAgents(agentList)
      setWorkspaces(workspaceList)
      setSkills(skillList)
      setMcpServers(mcpList)
      setSelectedTeamId(prev => prev || teamList[0]?.id || '')
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
    if (selectedTeamId === team.id) setSelectedTeamId('')
  }

  const toggleWorkspace = (id: string) => {
    setSelectedWorkspaces(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    )
  }

  const handleRunTeam = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedTeamId || !message.trim()) return
    setSubmittingExecution(true)
    setError(null)
    try {
      const result = await executionsApi.runTeam({
        team_id: selectedTeamId,
        message: message.trim(),
        approval_mode: approvalMode,
        workspace_ids: selectedWorkspaces,
        stream,
      })
      navigate(`/executions/${result.execution_id}`)
    } catch (e) {
      setError(String(e))
      setSubmittingExecution(false)
    }
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

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-5">
        <section>
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
                  <div className="flex gap-2 shrink-0">
                    <button className="btn-primary text-xs" onClick={() => handleChatTeam(team)}>
                      Chat
                    </button>
                    <button className="btn-secondary text-xs" onClick={() => setSelectedTeamId(team.id)}>
                      Select
                    </button>
                    <button className="btn-danger text-xs" onClick={() => handleDelete(team)}>
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <aside className="card h-fit">
          <p className="text-sm font-semibold text-slate-200 mb-3">Run Team</p>
          <form onSubmit={handleRunTeam} className="space-y-4">
            <div>
              <label className="form-label" htmlFor="team-select">Team</label>
              <select
                id="team-select"
                className="form-select"
                value={selectedTeamId}
                onChange={e => setSelectedTeamId(e.target.value)}
                required
              >
                <option value="">Select a team...</option>
                {teams.map(team => (
                  <option key={team.id} value={team.id}>{team.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="form-label" htmlFor="team-message">Team message</label>
              <textarea
                id="team-message"
                className="form-textarea min-h-[110px]"
                value={message}
                onChange={e => setMessage(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="form-label">Approval mode</label>
              <div className="flex gap-3">
                {(['manual', 'auto'] as ApprovalMode[]).map(mode => (
                  <label key={mode} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="team_approval_mode"
                      checked={approvalMode === mode}
                      onChange={() => setApprovalMode(mode)}
                    />
                    <span className="text-sm text-slate-300 capitalize">{mode}</span>
                  </label>
                ))}
              </div>
            </div>

            {workspaces.length > 0 && (
              <div>
                <label className="form-label">Workspaces</label>
                <div className="space-y-2">
                  {workspaces.map(workspace => (
                    <label key={workspace.id} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedWorkspaces.includes(workspace.id)}
                        onChange={() => toggleWorkspace(workspace.id)}
                      />
                      <span className="text-sm text-slate-300">{workspace.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={stream} onChange={e => setStream(e.target.checked)} />
              <span className="text-sm text-slate-300">Stream timeline</span>
            </label>

            <button
              type="submit"
              className="btn-primary w-full"
              disabled={submittingExecution || !selectedTeamId || !message.trim()}
            >
              {submittingExecution ? 'Starting...' : 'Run Team'}
            </button>
          </form>
        </aside>
      </div>
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
