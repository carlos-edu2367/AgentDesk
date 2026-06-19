# Phase 14 Audit History Export Plan

## Current facts

- `09-domain-model.md` remains the source of truth for `Execution`, `ExecutionEvent`, `ApprovalRequest` and `AuditLog`.
- Backend already persists executions, execution events, approvals and audit logs.
- Backend already has team MCP association endpoints.
- Missing backend surface: `/api/audit`, `/api/executions/{id}/detail`, `/api/executions/{id}/export`, `/api/logs/cleanup`, centralized secret masking and retention defaults.
- Missing frontend surface: Audit Logs route/page, execution filters/export/detail sections and TeamForm MCP checkboxes.

## Implementation approach

1. Add a central `mask_secrets`/truncate utility in `app.domain.utils` and keep MCP imports compatible.
2. Add API schemas for paginated audit responses, execution detail, export, cleanup and retention settings.
3. Add `audit` router and `logs` router; extend `executions` router with filters, detail and export.
4. Keep schema changes minimal and derive optional audit fields from `AuditLog.data` to avoid migration churn.
5. Add retention defaults to `app.config.json`; cleanup remains manual and conservative.
6. Add focused frontend API/types/pages for Audit Logs, execution filters/export and TeamForm MCP association.
7. Add/adjust tests before implementation and run backend/frontend focused tests plus broader suites when feasible.

## Constraints

- Do not break SSE event streaming.
- Do not remove audit logs by default.
- Do not remove `running` or `waiting_approval` execution data.
- Do not expose secrets in exports or API audit/detail responses.
- Do not implement packaging, auto-update, cloud sync or MCP HTTP transports in this phase.
