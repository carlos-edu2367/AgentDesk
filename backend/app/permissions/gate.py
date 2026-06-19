from typing import List

from app.tools.capabilities import CAPABILITIES
from app.tools.errors import ToolDeniedError, ToolNotFoundError
from app.tools.registry import tool_registry
from app.tools.schemas import ToolDefinition


def check_tool_permission(
    tool_name: str,
    capabilities: List[str],
    explicit_tools: List[str],
    blocked_tools: List[str],
) -> None:
    """
    Validates whether the agent is permitted to execute a tool.

    Raises:
        ToolNotFoundError: if the tool is not registered.
        ToolDeniedError: if the tool is blocked or not authorized.
    """
    if not tool_registry.exists(tool_name):
        raise ToolNotFoundError(tool_name)

    if tool_name in blocked_tools:
        raise ToolDeniedError("TOOL_BLOCKED", f"Tool '{tool_name}' is explicitly blocked for this agent")

    for cap in capabilities:
        if cap == "mcp" and tool_name.startswith("mcp."):
            return
        if tool_name in CAPABILITIES.get(cap, []):
            return
        if tool_registry.exists(tool_name) and tool_registry.get_definition(tool_name).capability == cap:
            return

    if tool_name in explicit_tools:
        return

    raise ToolDeniedError("TOOL_NOT_AUTHORIZED", f"Agent is not authorized to use tool '{tool_name}'")


def get_available_tool_definitions(
    capabilities: List[str],
    explicit_tools: List[str],
    blocked_tools: List[str],
) -> List[ToolDefinition]:
    """Returns definitions of all tools this agent can use."""
    available: set = set()

    for cap in capabilities:
        for name in CAPABILITIES.get(cap, []):
            available.add(name)
        for definition in tool_registry.list_by_capability(cap):
            available.add(definition.name)

    for name in explicit_tools:
        if tool_registry.exists(name):
            available.add(name)

    for name in blocked_tools:
        available.discard(name)

    return [tool_registry.get_definition(name) for name in sorted(available) if tool_registry.exists(name)]
