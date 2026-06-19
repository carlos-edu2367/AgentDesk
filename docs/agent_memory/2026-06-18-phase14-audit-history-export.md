# Phase 14 - Audit Logs, History and Export

## What changed

- Added `/api/audit`, `/api/audit/{audit_id}` and `/api/executions/{execution_id}/audit`.
- Added filters for audit logs: date range, execution, agent, team, event type, risk, tool, source, status, approval mode, query, limit and offset.
- Added `/api/executions/{execution_id}/detail` with execution, events, audit logs, approvals, empty artifacts and derived summary.
- Added `/api/executions/{execution_id}/export` for `json` and `markdown`, writing reports under `%APPDATA%/AgentDesk/exports/reports/`.
- Added `/api/logs/cleanup` with `dry_run=true` default, conservative event cleanup, no audit deletion by default, and audit log for real cleanup.
- Added centralized `mask_secrets`, `sanitize_for_output` and truncation utilities in `app.domain.utils`; MCP masking now reuses the central utility.
- Added retention defaults to `app.config.json`: `logs_retention_days`, `audit_retention_days`, `keep_failed_executions`.
- Added frontend Audit Logs page and sidebar entry.
- Added execution filters and export actions in the Executions page.
- Added aggregate sections and export actions in ExecutionDetail.
- Added MCP server selection to TeamForm, persisted through existing team MCP association API after team creation.

## Safety notes

- Audit optional fields such as `tool`, `source`, `status` and `approval_mode` are derived from `AuditLog.data`; no database migration was needed for this phase.
- Cleanup never removes `running` or `waiting_approval` execution events.
- Cleanup does not remove audit logs unless `include_audit_logs=true`.
- Exports and API detail/audit responses sanitize known secret keys and token-like values and truncate large strings with `[truncated]`.

## Validation

- Backend: `python -m pytest backend\\tests -q` -> 207 passed, 1 skipped.
- Frontend: `npm.cmd test -- --run --reporter=dot` -> 51 passed.
- Frontend build: `npm.cmd run build` -> passed.
