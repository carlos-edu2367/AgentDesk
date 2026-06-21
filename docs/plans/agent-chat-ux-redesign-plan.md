# Agent Chat UX Redesign — Design Spec

**Status:** Approved design (brainstorm) — ready for implementation plan
**Date:** 2026-06-21
**Area:** `apps/frontend` (chat UX) + `backend` (multi-turn conversations, reasoning capture)

## Problem

The current flow for using agents in the frontend is hard to use and has poor UX/UI:

- Running an agent is a one-shot **form** (`RunAgent.tsx`) → redirect to an **`ExecutionDetail.tsx`** page that is essentially a raw event **timeline** with JSON dumps.
- There is no conversational flow: the model's answer, its reasoning ("thinkings"), and the chain of tool calls are all flattened into the same technical timeline.
- Responses are rendered as raw `whitespace-pre-wrap` text — no markdown formatting.
- There is no way to send a follow-up message to the same agent with shared history.
- Teams reuse the same execution-timeline view, with no distinct rendering of the leader ↔ members conversation.

## Goal

Give each agent a **real chat**: formatted markdown answers, expandable **thinking** blocks, and the **tool-call chain** rendered inline in the same conversational flow, easy to understand and expand. Raw **logs** are moved out of that flow into a separate, collapsible panel, and the user can keep sending messages to the agent (multi-turn). Chatting with a **team** is a chat with the **team leader**, with the inter-agent conversation shown distinctly.

## Decisions (from brainstorm)

| Decision | Choice |
|---|---|
| Multi-turn | **Real multi-turn** — backend keeps conversation history; the agent remembers prior messages. |
| "Thinking" content | **Both** — real model reasoning tokens when the model emits them, **and** the agent's intermediate steps (tool calls / decisions) as expandable blocks. |
| Logs placement | **A — Collapsible side drawer.** Chat is the main flow; raw event timeline + audit live in a drawer that opens on demand. |
| Team conversation | **A — Nested sub-thread under the leader.** Leader bubbles are the main flow; member contributions appear indented as an expandable thread within the turn. |

## Current architecture (as-is)

- **Execution = one-shot run.** `POST /api/executions/agent` (or `/team`) creates an `Execution` row (`user_input`, `status`, `approval_mode`, `workspace_ids`) and launches `execution_engine.run_agent_execution` as a background task. Result lands in `execution.result`. (`backend/app/api/routers/executions.py`)
- **Events over SSE.** `GET /api/executions/{id}/events` streams `ExecutionEvent`s; the frontend `useExecutionEvents` hook consumes them. (`apps/frontend/src/hooks/useExecutionEvents.ts`)
- **Prompt is built fresh per run.** `PromptBuilder.build_messages()` returns `[system, user_request]` — no conversation history. (`backend/app/runtime/prompt_builder.py:113`)
- **Model streaming** emits `MODEL_CHUNK` events with `{delta}`; reasoning is **not** captured. (`backend/app/runtime/agent_runtime.py:236`)
- **Tool-call lifecycle events already exist**: `tool_call_requested → tool_call_validated → tool_executed → tool_result` (plus plugin/mcp variants). These will be grouped into chat tool-call cards.
- **Approvals** (`waiting_approval`, `ApprovalCard`) and **team events** (`leader_*`, `member_*`) already exist and are reused.

## Design

### 1. Core concept: Conversation (thread) groups turns

Introduce a **Conversation** entity that groups executions. Each user message is **one turn = one execution**, reusing the existing robust engine (events, approvals, audit, cancel, export). The only new behavior is grouping and **history injection**.

- **`Conversation`**: `id`, `type` (`agent` | `team`), `target_id` (agent/team id), `title`, `created_at`, `updated_at`.
- **`executions.conversation_id`**: nullable FK linking each turn-execution to its conversation. Legacy one-shot executions keep `conversation_id = NULL`.
- **History injection**: `PromptBuilder.build_messages()` receives the prior turns of the conversation and injects them as alternating `user` / `assistant` messages before the current user message. A configurable cap limits how many turns / how much context is included.

This delivers "real multi-turn" while reusing the existing execution machinery — no rewrite of the execution engine.

### 2. Backend changes

- **Model + Alembic migration**: new `conversations` table; add nullable `conversation_id` column to `executions`.
- **Router `/api/conversations`**:
  - `POST /conversations` — create a conversation for an agent or team.
  - `GET /conversations` — list (filter by type/target).
  - `GET /conversations/{id}` — conversation + ordered turns (executions) with their summaries.
  - `POST /conversations/{id}/messages` — append a user message → creates a turn-execution with `conversation_id` and dispatches the engine (same path as today).
  - Existing `/executions/agent` and `/executions/team` accept an optional `conversation_id` (or auto-create a conversation) so the entry points converge.
- **History loading**: `agent_runtime` and `team_engine` load prior turns of the conversation and pass them to `PromptBuilder`. Truncation strategy: most-recent-N turns within a token/char budget.
- **Reasoning capture ("thinking" — real)**: extend provider `stream_chat` to surface reasoning tokens (OpenRouter supports reasoning; Ollama models like `deepseek-r1`). Emit a new event `model_reasoning_chunk` (analogous to `model_chunk`). When the model emits no reasoning, no event is produced and the UI hides the block.

### 3. Frontend component architecture

New chat module, reusing `useExecutionEvents` (SSE) per turn.

- **`ConversationView`** — primary entry point (replaces the `RunAgent` form as the main way to use an agent). Header (agent/team) + thread + always-available composer that posts a new turn.
- **`ChatThread`** — renders turns in order. Per turn:
  - **`UserBubble`** — the user's message.
  - **`AssistantTurn`** — formatted **markdown** (via `react-markdown` + `remark-gfm`, sanitized), an expandable **`ThinkingBlock`** (real reasoning + intermediate steps), and a **`ToolCallChain`** of inline, expandable tool-call cards (args + result) in the same flow.
- **`LogsDrawer`** — collapsible side panel (decision A) with the raw event timeline + audit + export. Largely the current `ExecutionDetail` content, reused.
- **`ApprovalCard`** — reused, now rendered inline within a turn when status is `waiting_approval`.
- **Team (decision A)**: the leader's `AssistantTurn` contains a **`TeamSubThread`** — an indented, expandable thread showing member contributions, each tagged with the member's avatar/color, derived from `leader_*` / `member_*` events.

### 4. Navigation

- In **Agents** and **Teams** views, the **"Run"** button becomes **"Chat"** → opens/creates a conversation and routes to `ConversationView`.
- **Executions** view stays as history/audit (unchanged). Conversations are listable and reachable.
- Add `react-markdown` + `remark-gfm` for answer rendering (today answers are raw `whitespace-pre-wrap`).

### 5. Data flow (per turn)

1. User submits message in the composer → `POST /conversations/{id}/messages`.
2. Backend creates a turn-execution (`conversation_id` set), loads prior turns, dispatches engine.
3. Frontend opens SSE for that turn-execution via `useExecutionEvents`.
4. Events stream in and are grouped: `model_reasoning_chunk` → ThinkingBlock; `tool_*` → ToolCallChain; `model_chunk` → streaming answer; `agent_completed` / `result` → final markdown bubble.
5. On completion, the turn is appended to the thread; composer is ready for the next message.

### 6. Error handling & edge cases

- A failed turn shows an error bubble in the flow, with full detail available in the LogsDrawer.
- SSE reconnect handling; ability to cancel an in-progress turn.
- Model without reasoning → ThinkingBlock hides the reasoning section (shows intermediate steps only).
- Long conversations → history truncation (most-recent-N within budget).
- Approval mid-turn within a multi-turn conversation → inline `ApprovalCard`, resume flow unchanged.

### 7. Testing

- **Backend (pytest)**: conversation CRUD, history injection in the prompt, migration, message endpoint dispatch, reasoning event emission.
- **Frontend (vitest)**: markdown rendering, tool-call grouping, expandable thinking, new-turn submission flow, team sub-thread rendering.
- **E2E (playwright, optional)**: end-to-end chat flow (send → stream → follow-up).

## Phasing (each phase shippable)

1. **Backend foundation** — `Conversation` model + migration, `conversation_id` on executions, history injection in `PromptBuilder`, `/api/conversations` endpoints.
2. **Frontend chat (single agent)** — `ConversationView` + `ChatThread` + markdown + `ToolCallChain` + `LogsDrawer`; rewire Agents "Chat" button.
3. **Reasoning capture** — provider `stream_chat` reasoning tokens + `model_reasoning_chunk` event + ThinkingBlock real reasoning.
4. **Team sub-thread** — `TeamSubThread` rendering of leader ↔ members; rewire Teams "Chat" button.

## Non-goals (YAGNI)

- No change to the execution engine's core agentic loop or approval mechanics.
- No removal of the existing Executions/audit views.
- No new providers; reasoning capture only leverages what current providers expose.
