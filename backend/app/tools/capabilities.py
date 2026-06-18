from typing import Dict, List

CAPABILITIES: Dict[str, List[str]] = {
    "filesystem_read": [
        "filesystem.list",
        "filesystem.read",
        "filesystem.stat",
        "filesystem.search",
    ],
    "filesystem_write": [
        "filesystem.write",
        "filesystem.move",
        "filesystem.copy",
    ],
    "filesystem_delete": [
        "filesystem.delete",
    ],
    "terminal": [
        "terminal.exec",
    ],
    "http": [
        "http.request",
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
    ],
}

CRITICAL_TOOLS = frozenset({
    "filesystem.write",
    "filesystem.delete",
    "filesystem.move",
    "filesystem.copy",
    "terminal.exec",
    "http.request",
})

TOOL_RISK_LEVELS: Dict[str, str] = {
    "filesystem.write": "medium",
    "filesystem.delete": "high",
    "filesystem.move": "medium",
    "filesystem.copy": "low",
    "terminal.exec": "high",
    "http.request": "medium",
}

TOOL_SUMMARIES: Dict[str, str] = {
    "filesystem.write": "Write content to a file",
    "filesystem.delete": "Delete a file or directory",
    "filesystem.move": "Move a file or directory",
    "filesystem.copy": "Copy a file or directory",
    "terminal.exec": "Execute a terminal command",
    "http.request": "Make an HTTP request",
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
    return TOOL_RISK_LEVELS.get(tool_name, "low")


def get_tool_summary(tool_name: str) -> str:
    return TOOL_SUMMARIES.get(tool_name, f"Execute {tool_name}")
