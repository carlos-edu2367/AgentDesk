# Frontend Chat-Shell Redesign — Design

**Date:** 2026-06-21
**Scope:** Frontend only (`apps/frontend`). No backend changes.
**Goal:** Eliminate the "too many sidebar tabs, complex to use" problem by turning AgentDesk from an admin panel into a chat-first app where agents/teams are central and configuration is tucked away but easy to reach.

## Problem

The sidebar exposes 14 flat nav items that mix four unrelated concerns at equal visual weight:

- **Daily use:** Chats, Executions/Run Agent
- **What you create:** Agents, Teams
- **Resources agents consume (rare config):** Tools, MCP Servers, Skills, Plugins, Memory
- **Infra/config (set up once):** Providers, Workspaces, Settings
- **Observability:** Dashboard, Audit Logs

Rare setup tasks compete for attention with the one thing done daily: talking to an agent.

## Direction (validated with user)

- Agents and Teams are central; configuring them must be easy, but the focus is **usage**.
- The app should behave like a **chat shell** (ChatGPT/Claude-style): it opens straight into a **new chat with a "primary" agent/team**.
- Agents and Teams stay **visible** in the primary navigation alongside Chat.
- Everything else collapses into a **Configurações** area.
- The one-shot run flow and the Dashboard are **retired** — a one-shot run is just a one-turn conversation.

## New Information Architecture

### Primary shell (sidebar)

The sidebar stops being a 14-item list and becomes chat-dominated:

```
┌ Sidebar ──────────────┐ ┌ Main area ───────────────┐
│ AgentDesk  ●online     │ │                           │
│ [ + Novo chat  ▾ ]     │ │   Conversation thread     │
│                        │ │   (ConversationView)      │
│ CONVERSAS              │ │                           │
│  · Recent conversation │ │                           │
│  · ...                 │ │                           │
│ ───────────────        │ │                           │
│  👤 Agents             │ │                           │
│  👥 Teams              │ │                           │
│  ⚙  Configurações      │ │                           │
│ v0.1.0                 │ │                           │
└────────────────────────┘ └───────────────────────────┘
```

- **"+ Novo chat"** button: primary action opens a new conversation with the **primary** agent/team. A **▾ dropdown** on the button lets the user pick a different agent or team to start a chat with.
- **CONVERSAS**: the former "Chats" view (conversations list) now lives directly in the sidebar. Clicking a conversation opens it in the main area.
- **Agents / Teams / Configurações**: compact links, always visible.

### Primary agent/team

- A **pin** toggle (star icon) appears on each item in the Agents list **and** the Teams list.
- Exactly **one** primary at a time; pinning a new target un-pins the previous one.
- Persisted in `localStorage` under key `agentdesk.primaryTarget` as `{ type: 'agent' | 'team', id: string }`.
- Accessed via a new hook `usePrimaryTarget()` exposing `{ primary, setPrimary, clearPrimary }`.
- No backend involvement (desktop, single user, single machine).

### App-open behavior (route `/`)

```
open app → primary defined AND still exists?
   ├─ yes → create a new conversation for the primary → navigate to /conversations/:id
   └─ no  → any agents exist?
            ├─ yes → navigate to /agents
            └─ no  → navigate to /agents (empty state: "create your first agent")
```

Always a **fresh, empty** chat on open (no resume).

"Still exists" is verified by listing agents/teams on startup and checking the stored id against them; a stale pin (deleted target) falls through to the `/agents` branch and the stale value is cleared.

### Configurações area (`/config`)

A single destination behind the gear, with **secondary navigation grouped into four sections** (a side-nav inside the page). Routing is explicit and bookmarkable: `/config` redirects to the first panel, and each panel is `/config/:section` (e.g. `/config/providers`, `/config/tools`, `/config/activity`). Reuses the existing catalog views as panels — they are not rewritten, only re-parented.

- **Modelos & Acesso:** Providers, Workspaces
- **Capacidades:** Tools, MCP Servers, Skills, Plugins, Memory
- **Atividade:** Executions (read-only history) + Audit Logs
- **Sistema:** storage/paths (the current Settings screen)

Nothing is deleted from functionality — these only leave first-class navigation.

### Retired

- **Dashboard** — removed from navigation and deleted (`Dashboard.tsx`). The "open and use" role is now the direct chat.
- **Run Agent / one-shot flow** — the "Run" button is removed from the Agents list; route `/executions/run` is removed; `RunAgent.tsx` is deleted.
- **Executions as a top-level tab** — becomes read-only history under Config › Atividade. `ExecutionDetail` stays reachable from that history because it currently hosts the **approval flow** (must be preserved).

## Technical Impact (frontend only)

**Rewrite**
- `components/Sidebar.tsx` → chat shell (new-chat button + dropdown, conversations list, compact Agents/Teams/Config links).
- `App.tsx` → route `/` becomes a redirect controller implementing the app-open logic; add `/config` and `/config/:section`; remove `/` = Dashboard and `/executions/run`.

**New**
- `hooks/usePrimaryTarget.ts` — localStorage-backed primary agent/team.
- `views/Config.tsx` — container rendering the four grouped sections, each panel reusing an existing catalog view.
- A "new chat" entry component/logic (button + agent/team picker dropdown) — may live in the Sidebar or a small dedicated component.

**Edit**
- `views/Agents.tsx` — add pin toggle; remove the "Run" button (keep "Chat", "Edit", "Delete").
- `views/Teams.tsx` — add pin toggle.
- `components/Layout.tsx` — unchanged structurally (sidebar + outlet), verify it still fits the chat shell.

**Delete**
- `views/Dashboard.tsx`, `views/RunAgent.tsx`, and their imports/routes/links (including the Dashboard "New Agent / Run Agent" buttons and any `navigate('/executions/run')` callers).

**Untouched**
- `views/ConversationView.tsx`, all `components/chat/*`, `views/ExecutionDetail.tsx`, and every catalog view (Providers, Workspaces, Tools, McpServers, Memory, Skills, Plugins, Executions, AuditLogs) — these become Config panels as-is.
- All API clients and the entire backend.

## Data Flow

- `usePrimaryTarget()` reads/writes `localStorage`; no network.
- On `/`, the redirect controller calls `agentsApi.list()` (+ `teamsApi.list()` when primary type is team) to validate the pinned target, then `conversationsApi.create({ type, target_id, title })` and navigates to the new conversation — mirroring the existing `handleChat` flow already in `Agents.tsx`.
- Conversations list in the sidebar uses the existing `conversationsApi.list()`.

## Error / Edge Handling

- **Stale primary** (pinned target deleted): startup validation fails → clear stored value → fall through to `/agents`.
- **Backend offline at startup**: the existing `StartupScreen` already gates the app; the `/` controller runs after it. If list calls fail, fall back to `/agents` with the existing `ErrorState`.
- **No primary set / no agents**: `/agents` (empty state already exists).
- **Creating a chat fails**: surface the existing error pattern (alert/ErrorState), stay on a safe route (`/agents`).

## Testing

- `usePrimaryTarget` — unit tests: set/clear/replace primary, stale value handling.
- `/` redirect controller — tests for the four branches (primary valid → new conversation; stale primary → /agents; agents exist no primary → /agents; no agents → /agents empty state).
- `Sidebar` — renders conversations, new-chat button + dropdown, nav links.
- `Config` — renders the four groups and switches panels.
- Agents/Teams pin toggle — pin/un-pin updates `usePrimaryTarget`; only one primary at a time.
- Update/adjust existing frontend tests that reference removed routes/Dashboard/RunAgent. (Current suite: 59 frontend tests passing — keep green.)

## Out of Scope (explicit)

- Inline approvals inside the chat thread (still handled via ExecutionDetail; noted as a future follow-up).
- Any backend preference store / cross-machine sync of the primary target.
- Visual restyle beyond what the new shell requires.
