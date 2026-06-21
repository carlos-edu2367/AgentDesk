import { useState } from 'react'
import type { TeamMemberView, TeamMemberStatus } from '../../lib/groupEvents'

const AVATAR_COLORS = ['#059669', '#db2777', '#7c3aed', '#0891b2', '#d97706', '#dc2626']

/** Stable color per member id so the same agent keeps its color across turns. */
function colorFor(id: string): string {
  let hash = 0
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

const STATUS_LABEL: Record<TeamMemberStatus, string> = {
  assigned: 'assigned',
  running: 'working…',
  completed: 'done',
  failed: 'failed',
}

function MemberCard({ member }: { member: TeamMemberView }) {
  const [open, setOpen] = useState(false)
  const color = colorFor(member.agentId)
  const hasDetail = !!member.task || !!member.result || !!member.error

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/60 px-2.5 py-1.5 text-xs">
      <button
        className="flex items-center justify-between w-full gap-2"
        onClick={() => setOpen(v => !v)}
        disabled={!hasDetail}
      >
        <span className="flex items-center gap-2 min-w-0">
          <span
            className="w-4 h-4 rounded-full inline-flex items-center justify-center text-[8px] text-white shrink-0"
            style={{ background: color }}
          >
            {member.agentId.replace(/^agent_/, '').charAt(0).toUpperCase()}
          </span>
          <span className="font-mono text-slate-300 truncate">{member.agentId}</span>
          <span className="text-slate-500">{STATUS_LABEL[member.status]}</span>
        </span>
        {hasDetail && <span className="text-slate-600 shrink-0">{open ? '▲' : '▼'}</span>}
      </button>
      {open && hasDetail && (
        <div className="mt-2 space-y-1.5">
          {member.task && (
            <p className="text-slate-400"><span className="text-slate-500">Task: </span>{member.task}</p>
          )}
          {member.result && (
            <pre className="bg-slate-950 rounded p-2 overflow-x-auto whitespace-pre-wrap text-slate-300">{member.result}</pre>
          )}
          {member.error && <p className="text-red-300">{member.error}</p>}
        </div>
      )}
    </div>
  )
}

/** Nested, collapsible thread of member contributions under the leader's turn. */
export function TeamSubThread({ members }: { members: TeamMemberView[] }) {
  const [open, setOpen] = useState(false)
  if (members.length === 0) return null

  return (
    <div className="mt-1 border-l-2 border-cyan-500/40 pl-2.5">
      <button
        className="text-xs text-cyan-300 hover:text-cyan-200 transition-colors flex items-center gap-1"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
      >
        <span>{open ? '▾' : '▸'}</span>
        <span>Team worked on this ({members.length} {members.length === 1 ? 'agent' : 'agents'})</span>
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          {members.map(m => (
            <MemberCard key={m.agentId} member={m} />
          ))}
        </div>
      )}
    </div>
  )
}
