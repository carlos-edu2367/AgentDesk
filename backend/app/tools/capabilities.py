from typing import Dict, List

CAPABILITIES: Dict[str, List[str]] = {
    "filesystem_read": [
        "filesystem.list",
        "filesystem.read",
        "filesystem.stat",
        "filesystem.search",
        "filesystem.grep",
    ],
    "filesystem_write": [
        "filesystem.write",
        "filesystem.edit",
        "filesystem.multi_edit",
        "filesystem.move",
        "filesystem.copy",
    ],
    "filesystem_delete": [
        "filesystem.delete",
    ],
    "terminal": [
        "terminal.exec",
        "terminal.poll",
    ],
    "http": [
        "http.request",
    ],
    "web": [
        "web.search",
    ],
    "workspace": [
        "workspace.list",
        "workspace.get",
    ],
    "logs": [
        "logs.search",
        "logs.get_execution",
    ],
    "memory": [
        "memory.search",
        "memory.create",
        "memory.update",
        "memory.delete",
        "memory.list",
    ],
    "agent_control": [
        "agent.list",
        "agent.call",
    ],
    "team_control": [
        "team.list",
        "team.execute",
    ],
    "computer_use": [
        "screen.perceive",
        "screen.click",
        "screen.type",
        "screen.key",
        "screen.scroll",
    ],
}

# Tools every agent can always use, regardless of its capability list.
# Memory is treated as native platform infrastructure (not a grantable
# permission) so agents can persist and recall facts about the user by default.
# Still subject to an agent's blocked_tools.
NATIVE_TOOLS = frozenset({
    "memory.search",
    "memory.create",
    "memory.update",
    "memory.delete",
    "memory.list",
})

CRITICAL_TOOLS = frozenset({
    "filesystem.write",
    "filesystem.edit",
    "filesystem.multi_edit",
    "filesystem.delete",
    "filesystem.move",
    "filesystem.copy",
    "terminal.exec",
    "http.request",
    "web.search",
    "screen.click",
    "screen.type",
    "screen.key",
    "screen.scroll",
})

TOOL_RISK_LEVELS: Dict[str, str] = {
    "filesystem.write": "medium",
    "filesystem.edit": "medium",
    "filesystem.multi_edit": "medium",
    "filesystem.delete": "high",
    "filesystem.move": "medium",
    "filesystem.copy": "low",
    "terminal.exec": "high",
    "http.request": "medium",
    "web.search": "low",
    "memory.search": "low",
    "memory.create": "low",
    "memory.update": "low",
    "memory.delete": "low",
    "memory.list": "low",
    "agent.list": "low",
    "agent.call": "medium",
    "team.list": "low",
    "team.execute": "medium",
    "screen.perceive": "low",
    "screen.click": "high",
    "screen.type": "high",
    "screen.key": "high",
    "screen.scroll": "low",
}

TOOL_SUMMARIES: Dict[str, str] = {
    "filesystem.write": "Write content to a file",
    "filesystem.edit": "Replace an exact string in a file",
    "filesystem.multi_edit": "Apply multiple edits to a file atomically",
    "filesystem.delete": "Delete a file or directory",
    "filesystem.move": "Move a file or directory",
    "filesystem.copy": "Copy a file or directory",
    "terminal.exec": "Execute a terminal command",
    "http.request": "Make an HTTP request",
    "web.search": "Search the web",
    "memory.search": "Search stored memories",
    "memory.create": "Store a new memory entry",
    "memory.update": "Update an existing memory entry",
    "memory.delete": "Delete a memory entry",
    "memory.list": "List stored memories",
    "agent.list": "List available agents",
    "agent.call": "Call another agent as a subagent",
    "team.list": "List available teams",
    "team.execute": "Execute an agent team",
    "screen.perceive": "Capture screen and list interactive elements",
    "screen.click": "Click a UI element or coordinate",
    "screen.type": "Type text into the focused element",
    "screen.key": "Send a keyboard shortcut",
    "screen.scroll": "Scroll the screen",
}


def get_tools_for_capability(capability: str) -> List[str]:
    return CAPABILITIES.get(capability, [])


def get_capability_for_tool(tool_name: str) -> str | None:
    for cap, tools in CAPABILITIES.items():
        if tool_name in tools:
            return cap
    return None


def is_critical_tool(tool_name: str) -> bool:
    return tool_name in CRITICAL_TOOLS


def get_risk_level(tool_name: str) -> str:
    if tool_name.startswith("mcp."):
        return "high"
    return TOOL_RISK_LEVELS.get(tool_name, "low")


def get_tool_summary(tool_name: str) -> str:
    if tool_name.startswith("mcp."):
        return f"Execute MCP tool {tool_name}"
    return TOOL_SUMMARIES.get(tool_name, f"Execute {tool_name}")
