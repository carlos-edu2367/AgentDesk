# Phase 13 MCP stdio memory

## Context

Phase 13 added the initial MCP integration for AgentDesk using only stdio transport. The implementation follows the existing plugin/tool architecture: MCP tools are registered dynamically in the same `ToolRegistry`, pass through the existing permission gate, use the existing manual/auto approval flow, and write execution/audit records.

## Backend decisions

- SQLite remains the source of truth for MCP servers.
- `%APPDATA%/AgentDesk/config/mcp.config.json` is still only a future/export-style config path; the current implementation stores MCP servers in `mcp_servers`.
- MCP tools are registered as `mcp.{server_id}.{tool_name}`.
- MCP server IDs and tool names are normalized to lowercase underscore-safe path parts.
- MCP tools are critical by default.
- MCP server execution uses a short-lived process per call/test for stability.
- `POST /api/mcp/{server_id}/test` starts the stdio process, runs `initialize`, runs `tools/list`, updates `tools_cache_json`, updates `last_connected_at` or `last_error`, registers cached tools, and closes the process.
- On backend startup, cached MCP tools from enabled servers are re-registered in `ToolRegistry`.
- Agent association is enforced at MCP tool execution time through `agent.mcp_servers`.
- Team MCP associations are stored simply in `team.tools_policy["mcp_servers"]` plus the `team_mcp_servers` table for forward compatibility.

## Security and audit notes

- MCP env values and MCP audit payloads are masked with keys containing `TOKEN`, `API_KEY`, `SECRET`, `PASSWORD`, `AUTH`, or `BEARER`.
- MCP arguments/results are truncated in previews.
- MCP disabled and not-associated cases emit explicit execution events and audit logs.
- Generic runtime audit data for MCP tools is masked before persistence.

## Files introduced

- `backend/app/mcp/stdio.py`: JSON-RPC stdio MCP client.
- `backend/app/mcp/service.py`: CRUD/test/association service.
- `backend/app/mcp/registry.py`: dynamic `MCPTool` registration and execution.
- `backend/app/mcp/errors.py`, `schemas.py`, `utils.py`: MCP support contracts.
- `backend/tests/mocks/mock_mcp_server.py`: JSON-RPC MCP mock server for tests.
- `backend/tests/test_phase13_mcp.py`: backend phase 13 coverage.
- `apps/frontend/src/views/McpServers.tsx`: MCP Servers UI.
- `apps/frontend/src/api/mcp.ts`: frontend MCP API client.

## Verification

- Backend full suite passed: `python -m pytest -q` with 202 passed, 1 skipped.
- Frontend suite passed with increased timeout: `npm.cmd test -- --run --testTimeout=10000` with 47 passed.
- Frontend production build passed: `npm.cmd run build`.

## Known follow-up

- MCP HTTP/SSE/WebSocket, OAuth, marketplace, automatic installation, advanced secret storage, and read-only MCP risk classification remain out of scope for Phase 13.
- The implementation has backend support for team MCP associations, but the Phase 13 UI focuses on agent association.
