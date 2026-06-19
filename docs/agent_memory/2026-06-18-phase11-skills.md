# Phase 11 Skills

## Context

Phase 11 implements prompt/template-only Skills for AgentDesk. Skills do not execute code and are injected into agent/team runtime prompts as behavior instructions.

## What exists

- Backend skill module exists at `backend/app/skills/` with service, schemas facade, importer, exporter, and errors.
- Skills persist in SQLite through `SkillModel`.
- Agent and team associations are stored in both legacy JSON fields (`agents.skills`, `teams.skills`) and association tables (`agent_skills`, `team_skills`) for compatibility with existing repository/schema patterns.
- REST APIs exist for:
  - `GET/POST/PUT/DELETE /api/skills`
  - `POST /api/skills/import`
  - `GET /api/skills/{skill_id}/export`
  - agent skill association routes under `/api/agents/{agent_id}/skills`
  - team skill association routes under `/api/teams/{team_id}/skills`
- Runtime skill injection is implemented in `AgentRuntime` through `SkillService.format_skills_for_prompt`.
- Prompt order includes team context before tools, then active skills, memories, execution context, and user request.
- Skill prompt limits are:
  - `max_skills_per_prompt = 10`
  - `max_skill_chars_per_item = 1200`
  - `max_total_skill_chars = 6000`
- Runtime emits skill timeline events:
  - `skills_loaded`
  - `skill_injected`
  - `skills_truncated`
  - `skill_load_failed`
- Frontend has a Skills page, AgentForm skill selection, TeamForm team skills, and ExecutionDetail rendering for skill events.

## Verification

- Backend full suite on 2026-06-18: `python -m pytest -q` from `backend` passed with `180 passed, 1 skipped`.
- Frontend full suite on 2026-06-18: `npm.cmd test -- --run` from `apps/frontend` passed with `38 passed`.

## Notes

- The prompt references `docs/plans/implementation-roadmap.md`, but the repository currently contains `docs/plans/agentdesk-implementation-plan.md`.
- Current tests use provider mocks and do not depend on a real Ollama instance for Phase 11 runtime coverage.
