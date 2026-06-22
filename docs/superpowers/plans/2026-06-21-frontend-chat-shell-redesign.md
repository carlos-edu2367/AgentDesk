# Frontend Chat-Shell Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn AgentDesk's frontend into a chat-first app — opens straight into a new chat with a "primary" agent/team, with Agents/Teams visible and everything else collapsed into a grouped Configurações area.

**Architecture:** A `localStorage`-backed `usePrimaryTarget` hook stores the pinned agent/team (no backend). A `RootRedirect` controller at `/` creates a fresh conversation with the primary and navigates to it (falling back to `/agents`). The `Sidebar` becomes a chat shell (conversations list + new-chat button + compact Agents/Teams/Config links). A `Config` view renders the former catalog views as grouped panels under `/config/:section`. Dashboard and the one-shot Run flow are deleted.

**Tech Stack:** React 18, react-router-dom 6 (HashRouter), Vitest + @testing-library/react, Tailwind.

---

## File Structure

**Create**
- `apps/frontend/src/hooks/usePrimaryTarget.ts` — localStorage-backed primary agent/team state + sync.
- `apps/frontend/src/components/RootRedirect.tsx` — app-open controller for route `/`.
- `apps/frontend/src/views/Config.tsx` — grouped side-nav container rendering existing catalog views as panels.
- `apps/frontend/src/__tests__/usePrimaryTarget.test.ts`
- `apps/frontend/src/__tests__/RootRedirect.test.tsx`
- `apps/frontend/src/__tests__/Sidebar.test.tsx`
- `apps/frontend/src/__tests__/Config.test.tsx`

**Modify**
- `apps/frontend/src/components/Sidebar.tsx` — rewrite as chat shell.
- `apps/frontend/src/App.tsx` — new route table.
- `apps/frontend/src/views/Agents.tsx` — add pin toggle; remove "Run" button.
- `apps/frontend/src/views/Teams.tsx` — add pin toggle; remove inline one-shot run UI.
- `apps/frontend/src/views/Executions.tsx` — remove "Run Agent" buttons (read-only history).
- `apps/frontend/src/views/ProviderForm.tsx` — back-nav `/providers` → `/config/providers`.
- `apps/frontend/src/views/WorkspaceForm.tsx` — back-nav `/workspaces` → `/config/workspaces`.
- `apps/frontend/src/views/ExecutionDetail.tsx` — back-nav `/executions` → `/config/executions`.
- `apps/frontend/src/views/ConversationView.tsx` — link `/workspaces` → `/config/workspaces`.
- `apps/frontend/src/__tests__/Agents.test.tsx`, `Teams.test.tsx`, `Executions.test.tsx` — adjust for removed buttons / new pin.

**Delete**
- `apps/frontend/src/views/Dashboard.tsx` + `apps/frontend/src/__tests__/Dashboard.test.tsx`
- `apps/frontend/src/views/RunAgent.tsx`
- `apps/frontend/src/views/Conversations.tsx` (standalone list — replaced by sidebar) + `apps/frontend/src/__tests__/Conversations.test.tsx`

**Untouched**
- `components/chat/*`, `ConversationView` (except the one link), all catalog views (Providers, Workspaces, Tools, McpServers, Memory, Skills, Plugins, AuditLogs) other than back-nav fixes, all API clients, the entire backend.

---

## Task 1: `usePrimaryTarget` hook

**Files:**
- Create: `apps/frontend/src/hooks/usePrimaryTarget.ts`
- Test: `apps/frontend/src/__tests__/usePrimaryTarget.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// apps/frontend/src/__tests__/usePrimaryTarget.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePrimaryTarget } from '../hooks/usePrimaryTarget'

describe('usePrimaryTarget', () => {
  beforeEach(() => localStorage.clear())

  it('starts null when nothing stored', () => {
    const { result } = renderHook(() => usePrimaryTarget())
    expect(result.current.primary).toBeNull()
  })

  it('sets and reads a primary target', () => {
    const { result } = renderHook(() => usePrimaryTarget())
    act(() => result.current.setPrimary({ type: 'agent', id: 'a1' }))
    expect(result.current.primary).toEqual({ type: 'agent', id: 'a1' })
    expect(result.current.isPrimary('agent', 'a1')).toBe(true)
    expect(result.current.isPrimary('team', 'a1')).toBe(false)
  })

  it('replacing the primary keeps only one', () => {
    const { result } = renderHook(() => usePrimaryTarget())
    act(() => result.current.setPrimary({ type: 'agent', id: 'a1' }))
    act(() => result.current.setPrimary({ type: 'team', id: 't1' }))
    expect(result.current.primary).toEqual({ type: 'team', id: 't1' })
  })

  it('clears the primary', () => {
    const { result } = renderHook(() => usePrimaryTarget())
    act(() => result.current.setPrimary({ type: 'agent', id: 'a1' }))
    act(() => result.current.clearPrimary())
    expect(result.current.primary).toBeNull()
  })

  it('ignores malformed stored values', () => {
    localStorage.setItem('agentdesk.primaryTarget', '{not json')
    const { result } = renderHook(() => usePrimaryTarget())
    expect(result.current.primary).toBeNull()
  })

  it('syncs across two hook instances via custom event', () => {
    const a = renderHook(() => usePrimaryTarget())
    const b = renderHook(() => usePrimaryTarget())
    act(() => a.result.current.setPrimary({ type: 'agent', id: 'a9' }))
    expect(b.result.current.primary).toEqual({ type: 'agent', id: 'a9' })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && npx vitest run src/__tests__/usePrimaryTarget.test.ts`
Expected: FAIL — cannot resolve `../hooks/usePrimaryTarget`.

- [ ] **Step 3: Write minimal implementation**

```ts
// apps/frontend/src/hooks/usePrimaryTarget.ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/frontend && npx vitest run src/__tests__/usePrimaryTarget.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/hooks/usePrimaryTarget.ts apps/frontend/src/__tests__/usePrimaryTarget.test.ts
git commit -m "feat(frontend): add usePrimaryTarget hook for primary agent/team"
```

---

## Task 2: Pin toggle on Agents list + remove Run button

**Files:**
- Modify: `apps/frontend/src/views/Agents.tsx`
- Modify: `apps/frontend/src/__tests__/Agents.test.tsx`

- [ ] **Step 1: Update the test** (replace the file's top imports + add pin test, remove Run expectations)

Add to the mock block (after the `conversationsApi` mock) — `Agents.tsx` will import `usePrimaryTarget`; the real hook works against jsdom `localStorage`, so no mock needed. Add this test inside `describe('Agents list', ...)`:

```tsx
import { usePrimaryTarget } from '../hooks/usePrimaryTarget'
// ... existing imports ...

it('pins an agent as primary', async () => {
  localStorage.clear()
  render(<MemoryRouter><Agents /></MemoryRouter>)
  await waitFor(() => expect(screen.getByText('Test Agent')).toBeInTheDocument())

  await userEvent.click(screen.getByRole('button', { name: /set as primary/i }))

  const { result } = renderHook(() => usePrimaryTarget())
  expect(result.current.primary).toEqual({ type: 'agent', id: 'agent_001' })
})

it('no longer shows a Run button', async () => {
  render(<MemoryRouter><Agents /></MemoryRouter>)
  await waitFor(() => expect(screen.getByText('Test Agent')).toBeInTheDocument())
  expect(screen.queryByRole('button', { name: 'Run' })).not.toBeInTheDocument()
})
```

Add `renderHook` to the testing-library import: `import { render, screen, waitFor, renderHook } from '@testing-library/react'`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && npx vitest run src/__tests__/Agents.test.tsx`
Expected: FAIL — no "set as primary" button; "Run" still present.

- [ ] **Step 3: Implement** — in `apps/frontend/src/views/Agents.tsx`:

Add import near the top:
```tsx
import { usePrimaryTarget } from '../hooks/usePrimaryTarget'
```

Inside the component, after `const navigate = useNavigate()`:
```tsx
const { isPrimary, setPrimary } = usePrimaryTarget()
```

Replace the action buttons block (the `<div className="flex gap-2 shrink-0">` currently containing Chat / Run / Edit / Delete) with — note the Run button is removed and a pin button is added:
```tsx
<div className="flex gap-2 shrink-0 items-center">
  <button
    className={`text-xs px-2 ${isPrimary('agent', agent.id) ? 'text-amber-400' : 'text-slate-500 hover:text-amber-400'}`}
    title={isPrimary('agent', agent.id) ? 'Primary agent' : 'Set as primary'}
    aria-label={isPrimary('agent', agent.id) ? 'Primary agent' : 'Set as primary'}
    onClick={() => setPrimary({ type: 'agent', id: agent.id })}
  >
    {isPrimary('agent', agent.id) ? '★' : '☆'}
  </button>
  <button className="btn-primary text-xs" onClick={() => handleChat(agent)}>Chat</button>
  <button className="btn-ghost text-xs" onClick={() => navigate(`/agents/${agent.id}/edit`)}>Edit</button>
  <button className="btn-danger text-xs" onClick={() => handleDelete(agent.id, agent.name)}>Delete</button>
</div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/frontend && npx vitest run src/__tests__/Agents.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/views/Agents.tsx apps/frontend/src/__tests__/Agents.test.tsx
git commit -m "feat(frontend): pin primary agent and drop one-shot Run from Agents list"
```

---

## Task 3: Pin toggle on Teams + remove inline one-shot run

**Files:**
- Modify: `apps/frontend/src/views/Teams.tsx`
- Modify: `apps/frontend/src/__tests__/Teams.test.tsx`

The Teams view has (a) a card list with Chat/Run-select/Delete, (b) an inline one-shot run panel driven by `selectedTeamId` that calls an executions run and navigates to `/executions/:id`. Remove the run panel and the "Run" select button; keep Chat/Edit?/Delete + add pin.

- [ ] **Step 1: Update the test** — open `apps/frontend/src/__tests__/Teams.test.tsx`, add:

```tsx
it('pins a team as primary', async () => {
  localStorage.clear()
  render(<MemoryRouter><Teams /></MemoryRouter>)
  await waitFor(() => expect(screen.getByText(/* an existing team name in the mock */ TEAM_NAME)).toBeInTheDocument())
  await userEvent.click(screen.getAllByRole('button', { name: /set as primary/i })[0])
  const { result } = renderHook(() => usePrimaryTarget())
  expect(result.current.primary?.type).toBe('team')
})
```

Replace `TEAM_NAME` with the team name already present in this test file's `teamsApi.list` mock. Add `renderHook` to the `@testing-library/react` import and `import { usePrimaryTarget } from '../hooks/usePrimaryTarget'`. If the existing suite asserts on the one-shot run panel (search the file for `selectedTeamId`, `Run`, or `/executions/`), delete those assertions.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && npx vitest run src/__tests__/Teams.test.tsx`
Expected: FAIL — no "set as primary" button.

- [ ] **Step 3: Implement** — in `apps/frontend/src/views/Teams.tsx`:

Add `import { usePrimaryTarget } from '../hooks/usePrimaryTarget'`. Inside the component after `useNavigate()`: `const { isPrimary, setPrimary } = usePrimaryTarget()`.

In the team card actions (`<div>` around lines 173-181 with the Chat/Run/Delete buttons), remove the `setSelectedTeamId` "Run" button and add a pin button before Chat:
```tsx
<button
  className={`text-xs px-2 ${isPrimary('team', team.id) ? 'text-amber-400' : 'text-slate-500 hover:text-amber-400'}`}
  title={isPrimary('team', team.id) ? 'Primary team' : 'Set as primary'}
  aria-label={isPrimary('team', team.id) ? 'Primary team' : 'Set as primary'}
  onClick={() => setPrimary({ type: 'team', id: team.id })}
>
  {isPrimary('team', team.id) ? '★' : '☆'}
</button>
<button className="btn-primary text-xs" onClick={() => handleChatTeam(team)}>Chat</button>
<button className="btn-danger text-xs" onClick={() => handleDelete(team)}>Delete</button>
```

Delete the inline one-shot run block: the JSX panel that renders when `selectedTeamId` is set (the section building a run request and calling the executions run API, navigating to `/executions/${result.execution_id}` at ~line 120), plus the now-unused `selectedTeamId` state, its setter usages, the run handler, and the now-unused executions-run import. Run the TypeScript build in Step 4 to surface any leftover unused symbols and remove them.

- [ ] **Step 4: Run test + typecheck**

Run: `cd apps/frontend && npx vitest run src/__tests__/Teams.test.tsx && npx tsc --noEmit`
Expected: tests PASS; `tsc` reports no errors (fix any "declared but never read" by deleting the dead code).

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/views/Teams.tsx apps/frontend/src/__tests__/Teams.test.tsx
git commit -m "feat(frontend): pin primary team and remove inline one-shot run"
```

---

## Task 4: `RootRedirect` controller (route `/`)

**Files:**
- Create: `apps/frontend/src/components/RootRedirect.tsx`
- Test: `apps/frontend/src/__tests__/RootRedirect.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// apps/frontend/src/__tests__/RootRedirect.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RootRedirect } from '../components/RootRedirect'

const navigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

vi.mock('../api/agents', () => ({
  agentsApi: { list: vi.fn() },
}))
vi.mock('../api/teams', () => ({
  teamsApi: { list: vi.fn() },
}))
vi.mock('../api/conversations', () => ({
  conversationsApi: { create: vi.fn() },
}))

import { agentsApi } from '../api/agents'
import { teamsApi } from '../api/teams'
import { conversationsApi } from '../api/conversations'

const AGENT = { id: 'a1', name: 'Main', model_config: { model: 'x', temperature: 0 } }

beforeEach(() => {
  navigate.mockReset()
  localStorage.clear()
  vi.mocked(agentsApi.list).mockResolvedValue([AGENT] as never)
  vi.mocked(teamsApi.list).mockResolvedValue([] as never)
  vi.mocked(conversationsApi.create).mockResolvedValue({ id: 'conv1' } as never)
})

function renderIt() {
  render(<MemoryRouter><RootRedirect /></MemoryRouter>)
}

describe('RootRedirect', () => {
  it('with no primary set, goes to /agents', async () => {
    renderIt()
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/agents', { replace: true }))
  })

  it('with a valid primary agent, creates a conversation and opens it', async () => {
    localStorage.setItem('agentdesk.primaryTarget', JSON.stringify({ type: 'agent', id: 'a1' }))
    renderIt()
    await waitFor(() => {
      expect(conversationsApi.create).toHaveBeenCalledWith({ type: 'agent', target_id: 'a1', title: 'Main' })
      expect(navigate).toHaveBeenCalledWith('/conversations/conv1', { replace: true })
    })
  })

  it('with a stale primary (deleted agent), clears it and goes to /agents', async () => {
    localStorage.setItem('agentdesk.primaryTarget', JSON.stringify({ type: 'agent', id: 'gone' }))
    renderIt()
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/agents', { replace: true }))
    expect(conversationsApi.create).not.toHaveBeenCalled()
    expect(localStorage.getItem('agentdesk.primaryTarget')).toBeNull()
  })

  it('falls back to /agents when conversation creation fails', async () => {
    localStorage.setItem('agentdesk.primaryTarget', JSON.stringify({ type: 'agent', id: 'a1' }))
    vi.mocked(conversationsApi.create).mockRejectedValue(new Error('boom'))
    renderIt()
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/agents', { replace: true }))
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && npx vitest run src/__tests__/RootRedirect.test.tsx`
Expected: FAIL — cannot resolve `../components/RootRedirect`.

- [ ] **Step 3: Write implementation**

```tsx
// apps/frontend/src/components/RootRedirect.tsx
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/frontend && npx vitest run src/__tests__/RootRedirect.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/components/RootRedirect.tsx apps/frontend/src/__tests__/RootRedirect.test.tsx
git commit -m "feat(frontend): add RootRedirect opening a new chat with the primary target"
```

---

## Task 5: Sidebar chat shell

**Files:**
- Modify: `apps/frontend/src/components/Sidebar.tsx`
- Test: `apps/frontend/src/__tests__/Sidebar.test.tsx`

The new Sidebar shows: logo + status, a "+ Novo chat" button with a ▾ dropdown to pick a different agent/team, the conversations list (from `conversationsApi.list`), and compact links to Agents / Teams / Configurações.

- [ ] **Step 1: Write the failing test**

```tsx
// apps/frontend/src/__tests__/Sidebar.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from '../components/Sidebar'

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))
vi.mock('../api/conversations', () => ({
  conversationsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'c1', type: 'agent', target_id: 'a1', title: 'First chat', created_at: '', updated_at: '' },
    ]),
  },
}))

beforeEach(() => localStorage.clear())

describe('Sidebar', () => {
  it('renders the new-chat button and nav links', async () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /novo chat/i })).toBeInTheDocument()
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('Teams')).toBeInTheDocument()
    expect(screen.getByText('Configurações')).toBeInTheDocument()
  })

  it('lists recent conversations', async () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('First chat')).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && npx vitest run src/__tests__/Sidebar.test.tsx`
Expected: FAIL — no "Novo chat" button / "Configurações" link.

- [ ] **Step 3: Write implementation** (replace the whole file)

```tsx
// apps/frontend/src/components/Sidebar.tsx
import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import { useBackendHealth } from '../hooks/useBackendHealth'
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
  const { primary } = usePrimaryTarget()
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<Conversation[]>([])
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
        ) : conversations.map(c => (
          <NavLink
            key={c.id}
            to={`/conversations/${c.id}`}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-md text-sm truncate transition-colors ${
                isActive ? 'bg-blue-600/20 text-blue-300' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'
              }`
            }
          >
            {c.title || 'Untitled chat'}
          </NavLink>
        ))}
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/frontend && npx vitest run src/__tests__/Sidebar.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/components/Sidebar.tsx apps/frontend/src/__tests__/Sidebar.test.tsx
git commit -m "feat(frontend): rebuild Sidebar as a chat shell"
```

---

## Task 6: `Config` grouped area

**Files:**
- Create: `apps/frontend/src/views/Config.tsx`
- Test: `apps/frontend/src/__tests__/Config.test.tsx`

`Config` reads `:section` from the URL and renders a grouped side-nav plus the matching catalog view as a panel. Unknown/empty section falls back to `providers`.

- [ ] **Step 1: Write the failing test**

```tsx
// apps/frontend/src/__tests__/Config.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Config } from '../views/Config'

// Stub every panel view so this test stays isolated from their data fetching.
vi.mock('../views/Providers', () => ({ Providers: () => <div>Providers Panel</div> }))
vi.mock('../views/Workspaces', () => ({ Workspaces: () => <div>Workspaces Panel</div> }))
vi.mock('../views/Tools', () => ({ Tools: () => <div>Tools Panel</div> }))
vi.mock('../views/McpServers', () => ({ McpServers: () => <div>Mcp Panel</div> }))
vi.mock('../views/Skills', () => ({ Skills: () => <div>Skills Panel</div> }))
vi.mock('../views/Plugins', () => ({ Plugins: () => <div>Plugins Panel</div> }))
vi.mock('../views/Memory', () => ({ Memory: () => <div>Memory Panel</div> }))
vi.mock('../views/Executions', () => ({ Executions: () => <div>Executions Panel</div> }))
vi.mock('../views/AuditLogs', () => ({ AuditLogs: () => <div>Audit Panel</div> }))
vi.mock('../views/Settings', () => ({ Settings: () => <div>System Panel</div> }))

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/config/:section" element={<Config />} /></Routes>
    </MemoryRouter>,
  )
}

describe('Config', () => {
  it('renders the providers panel for /config/providers', () => {
    renderAt('/config/providers')
    expect(screen.getByText('Providers Panel')).toBeInTheDocument()
  })

  it('renders the executions panel for /config/executions', () => {
    renderAt('/config/executions')
    expect(screen.getByText('Executions Panel')).toBeInTheDocument()
  })

  it('shows the four group headers', () => {
    renderAt('/config/tools')
    expect(screen.getByText('Modelos & Acesso')).toBeInTheDocument()
    expect(screen.getByText('Capacidades')).toBeInTheDocument()
    expect(screen.getByText('Atividade')).toBeInTheDocument()
    expect(screen.getByText('Sistema')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && npx vitest run src/__tests__/Config.test.tsx`
Expected: FAIL — cannot resolve `../views/Config`.

- [ ] **Step 3: Write implementation**

```tsx
// apps/frontend/src/views/Config.tsx
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
    { slug: 'system', label: 'Sistema', el: <Settings /> },
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
```

Note: ensure `tsconfig` allows `JSX.Element` (it does — these views already return JSX). If the linter prefers `React.ReactElement`, swap the type alias accordingly.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/frontend && npx vitest run src/__tests__/Config.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/views/Config.tsx apps/frontend/src/__tests__/Config.test.tsx
git commit -m "feat(frontend): add grouped Config area reusing catalog views as panels"
```

---

## Task 7: Wire `App.tsx` routes + delete Dashboard/RunAgent/Conversations + fix back-nav

**Files:**
- Modify: `apps/frontend/src/App.tsx`
- Modify: `ProviderForm.tsx`, `WorkspaceForm.tsx`, `ExecutionDetail.tsx`, `ConversationView.tsx`, `Executions.tsx`
- Delete: `views/Dashboard.tsx`, `__tests__/Dashboard.test.tsx`, `views/RunAgent.tsx`, `views/Conversations.tsx`, `__tests__/Conversations.test.tsx`

- [ ] **Step 1: Replace `App.tsx`**

```tsx
// apps/frontend/src/App.tsx
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { StartupScreen } from './components/StartupScreen'
import { RootRedirect } from './components/RootRedirect'
import { Agents } from './views/Agents'
import { AgentForm } from './views/AgentForm'
import { Teams } from './views/Teams'
import { ProviderForm } from './views/ProviderForm'
import { WorkspaceForm } from './views/WorkspaceForm'
import { ExecutionDetail } from './views/ExecutionDetail'
import { ConversationView } from './views/ConversationView'
import { Config } from './views/Config'

export function App() {
  return (
    <StartupScreen>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<RootRedirect />} />

            <Route path="agents" element={<Agents />} />
            <Route path="agents/new" element={<AgentForm />} />
            <Route path="agents/:id/edit" element={<AgentForm />} />

            <Route path="teams" element={<Teams />} />

            <Route path="providers/new" element={<ProviderForm />} />
            <Route path="providers/:id/edit" element={<ProviderForm />} />
            <Route path="workspaces/new" element={<WorkspaceForm />} />
            <Route path="workspaces/:id/edit" element={<WorkspaceForm />} />

            <Route path="conversations/:id" element={<ConversationView />} />
            <Route path="executions/:id" element={<ExecutionDetail />} />

            <Route path="config" element={<Navigate to="/config/providers" replace />} />
            <Route path="config/:section" element={<Config />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </HashRouter>
    </StartupScreen>
  )
}
```

- [ ] **Step 2: Fix back-navigation targets**

Edit these exact strings:
- `ProviderForm.tsx` (3 occurrences): `navigate('/providers')` → `navigate('/config/providers')`
- `WorkspaceForm.tsx` (3 occurrences): `navigate('/workspaces')` → `navigate('/config/workspaces')`
- `ExecutionDetail.tsx` (1): `navigate('/executions')` → `navigate('/config/executions')`
- `ConversationView.tsx` (1, ~line 302): `navigate('/workspaces')` → `navigate('/config/workspaces')`

In `Executions.tsx`, remove the two "Run Agent" buttons (the `actions` TopBar button ~line 74 and the empty-state button ~line 158) that call `navigate('/executions/run')`, plus any now-unused import. Keep the row click that opens `/executions/:id`.

- [ ] **Step 3: Delete retired files**

```bash
git rm apps/frontend/src/views/Dashboard.tsx \
       apps/frontend/src/__tests__/Dashboard.test.tsx \
       apps/frontend/src/views/RunAgent.tsx \
       apps/frontend/src/views/Conversations.tsx \
       apps/frontend/src/__tests__/Conversations.test.tsx
```

- [ ] **Step 4: Typecheck + full test suite**

Run: `cd apps/frontend && npx tsc --noEmit && npx vitest run`
Expected: `tsc` clean; all tests pass. Fix any remaining references to deleted modules/routes the compiler flags (e.g. stray imports of `Dashboard`, `RunAgent`, `Conversations`).

- [ ] **Step 5: Commit**

```bash
git add -A apps/frontend/src
git commit -m "feat(frontend): chat-shell routing; retire Dashboard, one-shot Run, standalone Chats list"
```

---

## Task 8: Build + manual smoke verification

**Files:** none (verification only)

- [ ] **Step 1: Production build**

Run: `cd apps/frontend && npm run build`
Expected: `tsc` clean and Vite build succeeds.

- [ ] **Step 2: Full frontend suite**

Run: `cd apps/frontend && npm test`
Expected: all tests green (the 59 baseline minus deleted Dashboard/Conversations tests, plus the new usePrimaryTarget/RootRedirect/Sidebar/Config tests).

- [ ] **Step 3: Manual smoke (dev server)**

Run `npm run dev`, then verify:
- Fresh `localStorage` → app opens on `/agents` (no primary).
- Pin an agent (☆ → ★) → reload → app opens a new conversation with that agent.
- Sidebar lists conversations; clicking one opens it; "+ Novo chat" starts a new one; ▾ picker lists agents and teams.
- "Configurações" → side-nav switches between Providers/Workspaces/Tools/MCP/Skills/Plugins/Memory/Executions/Audit/Sistema; provider & workspace "New" forms save and return to the right `/config/*` panel.
- Executions panel opens an execution detail (`/executions/:id`) and its approval flow still works; "back" returns to `/config/executions`.

- [ ] **Step 4: Commit (only if smoke surfaced fixes)**

```bash
git add -A apps/frontend/src
git commit -m "fix(frontend): chat-shell smoke-test fixes"
```

---

## Self-Review Notes

- **Spec coverage:** chat shell (Task 5), primary target hook + pin (Tasks 1,2,3), app-open behavior (Task 4), grouped Config with `/config/:section` (Task 6), retire Dashboard/one-shot/Executions-tab (Tasks 2,3,7), ExecutionDetail preserved for approvals (Tasks 6,7,8), no backend changes (all tasks frontend-only). All covered.
- **localStorage key** `agentdesk.primaryTarget` and event `agentdesk:primary-changed` are consistent across Tasks 1/2/3/4/5.
- **Conversation creation** always creates fresh (no reuse) in RootRedirect and Sidebar new-chat — matches "always a fresh, empty chat" decision. (Note: the per-card "Chat" buttons in Agents/Teams keep their existing reuse-if-exists behavior; that is intentional and unchanged.)
- **Navigation targets** to removed list routes all re-pointed in Task 7.
