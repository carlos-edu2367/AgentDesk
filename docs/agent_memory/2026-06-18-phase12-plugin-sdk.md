# Phase 12 Plugin SDK MVP

## Context

Phase 12 introduced local plugin support for AgentDesk. Plugins are imported from a local folder containing `plugin.json` and are copied into `%APPDATA%/AgentDesk/plugins/installed/{plugin_id}`.

## Backend decisions

- Plugin manifests are validated in `backend/app/plugins/validator.py`.
- Reserved namespaces are blocked: `filesystem`, `terminal`, `memory`, `agent`, `team`, `workspace`, `logs`, `http`, `mcp`.
- Plugin tools must use a prefixed name, declare a capability listed in the plugin permissions, and use a Python entrypoint inside the plugin folder.
- Plugin tools are registered as normal `BaseTool` instances with `source="plugin"` and optional `plugin_id`.
- Dynamic plugin capabilities are exposed through the existing Tool Registry and Permission Gate.
- Python plugin tools run via subprocess using JSON stdin/stdout, timeout, captured stderr preview, and audit logs.
- Plugin skills are imported into the normal skills table with `plugin_id`. Prompt injection skips plugin skills when the owning plugin is disabled or removed.
- Agent/plugin association uses the existing `AgentModel.plugins` list plus `agent_plugins` rows.

## Frontend decisions

- Added a Plugins page with local path import, enable/disable, remove, manifest summary, tools, skills, and permissions.
- AgentForm lists installed plugins and lets agents associate plugin IDs.
- Plugin permissions are shown as capability options in AgentForm.
- Tools page separates Core Tools and Plugin Tools and shows source/capability/critical/plugin ID.
- ExecutionDetail labels plugin tool timeline events without showing full stdout/stderr.

## Validation

- Backend: `python -m pytest backend/tests -q` passed with `196 passed, 1 skipped`.
- Frontend: `npm.cmd test` passed with `41 passed`.
- Frontend build: `npm.cmd run build` passed.

## Out of scope kept for future phases

- Marketplace.
- Remote install.
- Auto-update.
- Cryptographic signing.
- Advanced sandboxing.
- Per-plugin virtualenv.
- Node.js plugins.
- MCP plugins.
