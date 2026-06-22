# Chat streaming, workspace grant, file writes & chat list

Date: 2026-06-21

Resolves five reported chat issues.

## 1. Post-tool answer only appeared after a page reload

Two independent causes:

- **Frontend folding** — `groupTurnEvents` blanked the streamed text whenever a
  turn had tool calls (`toolCalls.length > 0 ? '' : streamed`), so the answer
  only showed once `agent_completed` set `finalAnswer`. Replaced with
  `finalAnswer || stripProtocolJson(streamed)`: the new `stripProtocolJson`
  helper removes AgentDesk protocol JSON objects (complete *and* truncated) from
  the streamed text, surfacing the model's narration live while never rendering
  raw `{"type":...}` JSON.
- **SSE reconnect race** — `event_bus` has no buffer; on approval resume the
  resumed execution (a background task) published events before the reconnecting
  `EventSource` re-subscribed, so they were dropped (only persisted). Fix in
  `GET /executions/{id}/events`: subscribe to the bus **before** snapshotting
  persisted events, replay with id tracking, then stream live events deduped by
  id. `useExecutionEvents` also dedups by event id (kills the duplicate render).

## 2. No way to list/create chats per agent

`ConversationView` now has a left rail listing sibling conversations
(`conversationsApi.list({type, target_id})`) plus a **New chat** button
(`create` + navigate, carrying the current workspace grant over).

## 3. Terminal tool — agent receives output? Yes.

`terminal.exec` returns `{stdout, stderr, exit_code, duration_ms}` which the
runtime feeds back to the model as a `tool_result` (compacted to ~12 KB).

## 4 & 5. File creation broken / no workspace in chat

- The chat never sent `workspace_ids`, so `filesystem.write` had no writable
  workspace. `ConversationModel` now persists `workspace_ids` (migration
  `b2c3d4e5f6a7`); `ConversationView` has a workspace picker that saves via
  `PATCH /conversations/{id}`; `post_message` uses `req.workspace_ids or
  conv.workspace_ids`.
- Large file content was truncated by `llm_config.max_tokens` (default **2048**),
  leaving the tool-call JSON unterminated → parser treated it as a plain-text
  final answer and the write never ran. `OutputParser.looks_like_truncated_tool_call`
  now detects an unterminated protocol object; the runtime feeds back a
  `tool_call_truncated` hint (split large writes into create_only + append) and
  retries instead of silently dropping the call. **Agents that write big files
  should also raise `max_tokens`.**

## Follow-up: 500 on `GET /conversations` (NULL workspace_ids)

The new `workspace_ids` column was added nullable, so conversations created
before the migration read back as `NULL`, which failed `Conversation`
serialization (`List[str]` required) → 500 on list, surfacing in the UI as a
failed "start chat". Fixed by: (a) a `mode="before"` validator on
`ConversationBase` coercing `None → []`, and (b) a backfill
(`UPDATE conversations SET workspace_ids = '[]' WHERE workspace_ids IS NULL`)
added to migration `b2c3d4e5f6a7` and run against the existing dev DB.

## Validation

- `python -m pytest -q` → 252 passed, 1 skipped (incl. alembic startup).
- `npm.cmd test -- --run` → 99 passed; `tsc --noEmit` clean.
- End-to-end live streaming/file-write needs a running backend + configured LLM
  provider (not exercised in this session).
