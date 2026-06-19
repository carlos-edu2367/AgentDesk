# 2026-06-18 - Phase 10 Subagents and Teams

## What changed

Phase 10 added the first working multiagent layer:

- Core tools `agent.list`, `agent.call`, `team.list`, and `team.execute`.
- Capabilities `agent_control` and `team_control`.
- Parser support for model output shaped as `subagent_call`, routed through the same permission path as `agent.call`.
- `TeamExecutionEngine` with the MVP `leader_managed` strategy.
- `POST /api/executions/team`.
- Team/subagent execution events for the timeline.
- Team memory scope injection through runtime options.
- Basic Teams frontend with create/delete/list and team execution.

## Important behavior

`agent.call` is not a bypass. The caller still needs `agent_control` or explicit tool access, and `blocked_tools=["agent.call"]` still blocks it through the existing permission gate.

`agent.call` also checks the caller agent's `subagents` configuration:

- `can_call=false` blocks calls.
- `allowed_agent_ids=["*"]` allows any configured agent.
- A specific `allowed_agent_ids` list restricts calls to those IDs.
- `max_subagent_depth` and `max_subagent_calls` are enforced through runtime/tool context.

Team executions currently use only `leader_managed`. The team engine grants the leader explicit `agent.call` for that execution unless the leader explicitly blocks `agent.call`, and restricts allowed subagents to the team's member IDs.

## Memory and timeline

Runtime memory lookup now supports:

- `global`
- `agent:{agent_id}`
- `team:{team_id}`

Team memory is injected only when the runtime receives a team context and the agent's memory config allows team memory.

Timeline events added include:

- `team_started`
- `leader_started`
- `leader_plan_created`
- `member_assigned`
- `member_started`
- `member_completed`
- `member_failed`
- `subagent_call_requested`
- `subagent_started`
- `subagent_completed`
- `subagent_failed`
- `leader_review_started`
- `leader_finalized`
- `team_completed`
- `team_failed`

## Known limits

This is still the MVP path:

- No MCP, plugins, marketplace, distributed execution, graph UI, or advanced strategies were added.
- Team approval resume is still shallow: critical tools inside subagents create the normal approval request and timeline event, but full continuation of a paused nested subagent execution should be hardened in a later phase.
- `team.execute` tool creates a pending execution but does not launch background processing; the main supported path is `POST /api/executions/team`.

## Validation

- Backend full suite: `python -m pytest -q` from `backend` passed with 175 passed, 1 skipped.
- Frontend full suite: `npm.cmd test` from `apps/frontend` passed with 34 passed.
- Frontend build: `npm.cmd run build` passed.
- Dev server responded 200 at `http://127.0.0.1:5173`.
