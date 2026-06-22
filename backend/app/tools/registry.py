from typing import Dict, List, Optional

from app.tools.base import BaseTool
from app.tools.errors import ToolNotFoundError
from app.tools.schemas import CapabilityInfo, ToolDefinition


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if not tool:
            raise ToolNotFoundError(name)
        return tool

    def exists(self, name: str) -> bool:
        return name in self._tools

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def unregister_plugin(self, plugin_id: str) -> None:
        for name, tool in list(self._tools.items()):
            if getattr(tool, "source", "") == "plugin" and getattr(tool, "plugin_id", "") == plugin_id:
                self.unregister(name)

    def unregister_mcp_server(self, server_id: str) -> None:
        for name, tool in list(self._tools.items()):
            if getattr(tool, "source", "") == "mcp" and getattr(tool, "server_id", "") == server_id:
                self.unregister(name)

    def get_definition(self, name: str) -> ToolDefinition:
        tool = self.get(name)
        return ToolDefinition(
            name=tool.name,
            description=tool.description,
            source=tool.source,
            capability=tool.capability,
            critical=tool.critical,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            plugin_id=getattr(tool, "plugin_id", None),
            server_id=getattr(tool, "server_id", None),
        )

    def list_all(self) -> List[ToolDefinition]:
        return [self.get_definition(name) for name in sorted(self._tools.keys())]

    def list_by_capability(self, capability: str) -> List[ToolDefinition]:
        return [
            self.get_definition(name)
            for name, tool in self._tools.items()
            if tool.capability == capability or (capability == "mcp" and getattr(tool, "source", "") == "mcp")
        ]

    def list_capabilities(self) -> List[CapabilityInfo]:
        from app.tools.capabilities import CAPABILITIES

        result = []
        seen = set()
        for cap_name, tool_names in CAPABILITIES.items():
            existing = [t for t in tool_names if t in self._tools]
            seen.add(cap_name)
            result.append(CapabilityInfo(name=cap_name, tools=existing))
        dynamic: Dict[str, List[str]] = {}
        for name, tool in self._tools.items():
            if tool.capability and tool.capability not in seen:
                dynamic.setdefault(tool.capability, []).append(name)
            if getattr(tool, "source", "") == "mcp":
                dynamic.setdefault("mcp", []).append(name)
        for cap_name in sorted(dynamic):
            result.append(CapabilityInfo(name=cap_name, tools=sorted(dynamic[cap_name])))
        return result


tool_registry = ToolRegistry()


def register_core_tools() -> None:
    """Registers all core tools. Safe to call multiple times (idempotent)."""
    from app.tools.core.filesystem import (
        FilesystemListTool,
        FilesystemReadTool,
        FilesystemSearchTool,
        FilesystemStatTool,
    )
    from app.tools.core.filesystem_write import (
        FilesystemWriteTool,
        FilesystemDeleteTool,
        FilesystemMoveTool,
        FilesystemCopyTool,
    )
    from app.tools.core.terminal import TerminalExecTool
    from app.tools.core.http_tool import HttpRequestTool
    from app.tools.core.workspace import WorkspaceGetTool, WorkspaceListTool
    from app.tools.core.logs import LogsGetExecutionTool, LogsSearchTool
    from app.tools.core.memory import (
        MemorySearchTool,
        MemoryCreateTool,
        MemoryUpdateTool,
        MemoryDeleteTool,
        MemoryListTool,
    )
    from app.tools.core.agent_tools import AgentListTool, AgentCallTool
    from app.tools.core.team_tools import TeamListTool, TeamExecuteTool

    core_tools = [
        # Read-only filesystem
        FilesystemListTool(),
        FilesystemReadTool(),
        FilesystemStatTool(),
        FilesystemSearchTool(),
        # Critical filesystem
        FilesystemWriteTool(),
        FilesystemDeleteTool(),
        FilesystemMoveTool(),
        FilesystemCopyTool(),
        # Terminal
        TerminalExecTool(),
        # HTTP
        HttpRequestTool(),
        # Workspace
        WorkspaceListTool(),
        WorkspaceGetTool(),
        # Logs
        LogsSearchTool(),
        LogsGetExecutionTool(),
        # Memory
        MemorySearchTool(),
        MemoryCreateTool(),
        MemoryUpdateTool(),
        MemoryDeleteTool(),
        MemoryListTool(),
        # Agent/team orchestration
        AgentListTool(),
        AgentCallTool(),
        TeamListTool(),
        TeamExecuteTool(),
    ]
    for tool in core_tools:
        if not tool_registry.exists(tool.name):
            tool_registry.register(tool)
