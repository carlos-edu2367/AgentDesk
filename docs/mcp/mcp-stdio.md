# AgentDesk MCP stdio Guide

## Scope

The MVP supports MCP over stdio only. HTTP, SSE, WebSocket, OAuth, marketplace, and remote installation are out of scope.

## Register a Server

Create a server with:

- Name
- Transport: `stdio`
- Command, for example `python`
- Args, for example `examples/mcp/mock-mcp-server.py`
- Env as a JSON object
- Enabled flag

Env values are sensitive and must be masked in logs and UI.

## Test Connection

Use the MCP Servers screen to test a server. A successful test should initialize the process, call `tools/list`, cache tools, and register them in the Tool Registry.

## Associate With Agents

Associate the MCP server with an agent. The agent still needs the relevant MCP capability or explicit MCP tool entry.

## Tool Names

MCP tools appear through AgentDesk's tool registry with an MCP-prefixed name. Calls must pass through Permission Gate and generate audit logs.

## Safe Mock

Use `examples/mcp/mock-mcp-server.py` for local smoke tests. It has no external dependencies and only echoes provided text.
