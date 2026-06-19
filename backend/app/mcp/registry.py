from __future__ import annotations

import asyncio
import json
from typing import Any

from app.db.models import AgentModel, AuditLogModel, ExecutionEventModel, MCPServerModel
from app.domain.utils import generate_id
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError
from app.tools.registry import tool_registry

from .stdio import StdioMCPClient
from .utils import mask_secrets, mcp_tool_name, preview


class MCPTool(BaseTool):
    source = "mcp"

    def __init__(self, server_id: str, original_name: str, description: str = "", input_schema: dict[str, Any] | None = None):
        self.server_id = server_id
        self.original_name = original_name
        self.name = mcp_tool_name(server_id, original_name)
        self.description = description
        self.capability = f"mcp.{server_id}"
        self.critical = True
        self.input_schema = input_schema or {}
        self.output_schema = {}

    async def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        return await run_mcp_tool(self, arguments, context)


def register_mcp_tools(server: MCPServerModel) -> None:
    tool_registry.unregister_mcp_server(server.id)
    if not server.enabled or server.deleted_at is not None:
        return
    for spec in server.tools_cache_json or []:
        name = spec.get("name")
        if name and tool_registry.exists(name):
            existing = tool_registry.get(name)
            if getattr(existing, "source", "") != "mcp" or getattr(existing, "server_id", "") != server.id:
                raise ValueError(f"Tool '{name}' is already registered")
            tool_registry.unregister(name)
        original = spec.get("original_name") or str(name).split(".")[-1]
        tool_registry.register(MCPTool(
            server.id,
            original,
            spec.get("description", ""),
            spec.get("input_schema") or {},
        ))


async def run_mcp_tool(tool: MCPTool, arguments: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
    db = context.db
    server = db.query(MCPServerModel).filter(MCPServerModel.id == tool.server_id, MCPServerModel.deleted_at.is_(None)).first()
    if not server:
        _audit(db, context, "mcp_tool_denied", f"MCP tool denied: server not found", {"tool": tool.name, "server_id": tool.server_id}, "high")
        raise ToolError("MCP_SERVER_NOT_FOUND", f"MCP server '{tool.server_id}' was not found")
    if not server.enabled:
        _event(db, context, "mcp_server_disabled_tool_blocked", {"tool": tool.name, "server_id": tool.server_id})
        _audit(db, context, "mcp_tool_denied", f"MCP tool denied: server disabled", {"tool": tool.name, "server_id": tool.server_id}, "high")
        raise ToolError("MCP_SERVER_DISABLED", f"MCP server '{tool.server_id}' is disabled")

    agent = db.query(AgentModel).filter(AgentModel.id == context.agent_id).first()
    if not agent or tool.server_id not in (agent.mcp_servers or []):
        _event(db, context, "mcp_server_not_associated", {"tool": tool.name, "server_id": tool.server_id, "agent_id": context.agent_id})
        _audit(db, context, "mcp_tool_denied", f"MCP tool denied: server not associated to agent", {"tool": tool.name, "server_id": tool.server_id}, "high")
        raise ToolError("MCP_SERVER_NOT_ASSOCIATED", f"MCP server '{tool.server_id}' is not associated to this agent")

    timeout = int((arguments or {}).get("timeout_seconds", 30) or 30)
    tool_arguments = dict(arguments or {})
    tool_arguments.pop("timeout_seconds", None)
    _event(db, context, "mcp_tool_started", {"tool": tool.name, "server_id": tool.server_id})
    started = asyncio.get_running_loop().time()
    try:
        async with StdioMCPClient(server.command, server.args or [], server.env or {}, timeout) as client:
            await client.initialize()
            result = await client.call_tool(tool.original_name, tool_arguments)
            stderr_preview = client.stderr_preview
    except Exception as exc:
        message = getattr(exc, "message", str(exc))
        code = getattr(exc, "code", "MCP_TOOL_EXECUTION_FAILED")
        _event(db, context, "mcp_tool_failed", {"tool": tool.name, "server_id": tool.server_id, "error": message, "code": code})
        _audit(db, context, "mcp_tool_failed", f"MCP tool failed: {tool.name}", {
            "tool": tool.name,
            "server_id": tool.server_id,
            "arguments": mask_secrets(tool_arguments),
            "error": message,
            "code": code,
        }, "high")
        raise ToolError(code, message) from exc

    duration_ms = int((asyncio.get_running_loop().time() - started) * 1000)
    result_preview = preview(json.dumps(mask_secrets(result), ensure_ascii=False))
    _event(db, context, "mcp_tool_completed", {"tool": tool.name, "server_id": tool.server_id, "duration_ms": duration_ms, "result_preview": result_preview})
    _audit(db, context, "mcp_tool_executed", f"MCP tool executed: {tool.name}", {
        "tool": tool.name,
        "server_id": tool.server_id,
        "arguments": mask_secrets(tool_arguments),
        "result_preview": result_preview,
        "stderr_preview": stderr_preview,
        "duration_ms": duration_ms,
    }, "high")
    return result


def _event(db, context: ToolExecutionContext, event_type: str, content: dict[str, Any]) -> None:
    if context.execution_id == "test":
        return
    db.add(ExecutionEventModel(
        id=generate_id("event"),
        execution_id=context.execution_id,
        type=event_type,
        source="tool",
        source_id=content.get("tool", ""),
        content=content,
    ))
    db.commit()


def _audit(db, context: ToolExecutionContext, event_type: str, summary: str, data: dict[str, Any], risk_level: str = "low") -> None:
    db.add(AuditLogModel(
        id=generate_id("audit"),
        execution_id=context.execution_id,
        agent_id=context.agent_id,
        event_type=event_type,
        risk_level=risk_level,
        summary=summary,
        data=mask_secrets(data),
    ))
    db.commit()
