import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from app.db.models import AgentModel, AuditLogModel, ExecutionEventModel, PluginModel
from app.domain.utils import sanitize_for_output
from app.domain.utils import generate_id
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

STDIO_PREVIEW_CHARS = 4000
DEFAULT_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 300


class PluginTool(BaseTool):
    source = "plugin"

    def __init__(self, plugin_id: str, install_path: str, spec: dict[str, Any]):
        self.plugin_id = plugin_id
        self.install_path = install_path
        self.name = spec["name"]
        self.description = spec.get("description", "")
        self.capability = spec["capability"]
        self.critical = bool(spec.get("critical", False))
        self.input_schema = spec.get("input_schema") or {}
        self.output_schema = spec.get("output_schema") or {}
        self.entrypoint = spec["entrypoint"]
        self.runtime = spec.get("runtime", "python")

    async def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        return await run_plugin_tool(self, arguments, context)


async def run_plugin_tool(tool: PluginTool, arguments: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
    db = context.db
    plugin = db.query(PluginModel).filter(PluginModel.id == tool.plugin_id, PluginModel.deleted_at.is_(None)).first()
    if not plugin:
        _audit(db, context, "plugin_tool_denied", f"Plugin tool denied: {tool.name}", {"tool": tool.name, "code": "PLUGIN_NOT_FOUND"})
        raise ToolError("PLUGIN_NOT_FOUND", f"Plugin '{tool.plugin_id}' not found")
    if not plugin.enabled:
        _event(db, context, "plugin_disabled_tool_blocked", {"tool": tool.name, "plugin_id": tool.plugin_id})
        _audit(db, context, "plugin_tool_denied", f"Plugin disabled for tool {tool.name}", {"tool": tool.name, "code": "PLUGIN_DISABLED"})
        raise ToolError("PLUGIN_DISABLED", f"Plugin '{tool.plugin_id}' is disabled")
    if tool.capability not in (plugin.permissions or []):
        _audit(db, context, "plugin_tool_denied", f"Plugin tool denied: undeclared capability {tool.capability}", {"tool": tool.name})
        raise ToolError("PLUGIN_PERMISSION_UNDECLARED", f"Plugin tool capability '{tool.capability}' is not declared")
    agent = db.query(AgentModel).filter(AgentModel.id == context.agent_id).first()
    if agent and tool.plugin_id not in (agent.plugins or []):
        _audit(db, context, "plugin_tool_denied", f"Plugin tool denied: plugin not associated to agent", {"tool": tool.name, "plugin_id": tool.plugin_id})
        raise ToolError("PLUGIN_NOT_ASSIGNED_TO_AGENT", f"Plugin '{tool.plugin_id}' is not assigned to this agent")

    root = Path(plugin.install_path or tool.install_path).resolve()
    entrypoint = (root / tool.entrypoint).resolve()
    if root != entrypoint and root not in entrypoint.parents:
        raise ToolError("PLUGIN_ENTRYPOINT_OUTSIDE_ROOT", "Plugin entrypoint is outside plugin folder")
    if not entrypoint.exists():
        raise ToolError("PLUGIN_ENTRYPOINT_NOT_FOUND", "Plugin entrypoint was not found")

    tool_arguments = dict(arguments or {})
    timeout = min(int(tool_arguments.pop("timeout_seconds", DEFAULT_TIMEOUT_SECONDS) or DEFAULT_TIMEOUT_SECONDS), MAX_TIMEOUT_SECONDS)
    payload = {
        "arguments": tool_arguments,
        "context": {
            "execution_id": context.execution_id,
            "agent_id": context.agent_id,
            "workspace_ids": context.workspace_ids,
            "approval_mode": context.approval_mode,
        },
    }

    _event(db, context, "plugin_tool_started", {"tool": tool.name, "plugin_id": tool.plugin_id})
    started = asyncio.get_running_loop().time()
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(entrypoint),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(root),
            env=_safe_env(),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(json.dumps(payload).encode("utf-8")),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        _audit(db, context, "plugin_tool_failed", f"Plugin tool timeout: {tool.name}", {"tool": tool.name, "timeout_seconds": timeout}, "high")
        raise ToolError("PLUGIN_TOOL_TIMEOUT", f"Plugin tool '{tool.name}' timed out", {"timeout_seconds": timeout}) from exc

    duration_ms = int((asyncio.get_running_loop().time() - started) * 1000)
    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    stderr_preview = _preview(stderr_text)

    try:
        parsed = json.loads(stdout_text)
    except Exception as exc:
        _audit(db, context, "plugin_tool_failed", f"Plugin tool invalid stdout: {tool.name}", {
            "tool": tool.name,
            "stdout_preview": _preview(stdout_text),
            "stderr_preview": stderr_preview,
            "duration_ms": duration_ms,
        }, "medium")
        raise ToolError("PLUGIN_INVALID_STDOUT", "Plugin tool returned invalid JSON stdout", {
            "stdout_preview": _preview(stdout_text),
            "stderr_preview": stderr_preview,
        }) from exc

    if parsed.get("status") == "error":
        error = parsed.get("error") or {}
        message = error.get("message", "Plugin tool failed")
        code = error.get("code", "PLUGIN_TOOL_FAILED")
        _audit(db, context, "plugin_tool_failed", f"Plugin tool failed: {tool.name}", {"tool": tool.name, "code": code, "stderr_preview": stderr_preview}, "medium")
        raise ToolError(code, message, {"stderr_preview": stderr_preview})

    if parsed.get("status") != "success":
        raise ToolError("PLUGIN_INVALID_STDOUT", "Plugin tool stdout must contain status=success or status=error")

    result = parsed.get("result") or {}
    _event(db, context, "plugin_tool_completed", {"tool": tool.name, "plugin_id": tool.plugin_id, "duration_ms": duration_ms})
    _audit(db, context, "plugin_tool_executed", f"Plugin tool executed: {tool.name}", {
        "tool": tool.name,
        "plugin_id": tool.plugin_id,
        "result_preview": _preview(json.dumps(result, ensure_ascii=False)),
        "stderr_preview": stderr_preview,
        "duration_ms": duration_ms,
    })
    return result


def _safe_env() -> dict[str, str]:
    allowed = {"PATH", "SystemRoot", "WINDIR", "TEMP", "TMP"}
    return {key: value for key, value in os.environ.items() if key in allowed}


def _preview(value: str) -> str:
    return str(sanitize_for_output(value[:STDIO_PREVIEW_CHARS]))


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
        data=sanitize_for_output(data),
    ))
    db.commit()
