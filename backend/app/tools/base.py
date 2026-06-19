from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class ToolExecutionContext:
    def __init__(
        self,
        execution_id: str,
        agent_id: str,
        workspace_ids: List[str],
        db,
        approval_mode: str = "manual",
        extra: Dict[str, Any] | None = None,
    ):
        self.execution_id = execution_id
        self.agent_id = agent_id
        self.workspace_ids = workspace_ids
        self.db = db
        self.approval_mode = approval_mode
        self.extra = extra or {}

    def get_workspace_paths(self) -> List[str]:
        from app.db.repositories.registry import workspace_repo
        paths: List[str] = []
        for ws_id in self.workspace_ids:
            ws = workspace_repo.get(self.db, id=ws_id)
            if ws and ws.paths:
                paths.extend(ws.paths)
        return paths

    def get_workspace_paths_with_permission(self, permission: str) -> List[str]:
        """Returns paths from workspaces where the given permission flag is True."""
        from app.db.repositories.registry import workspace_repo
        paths: List[str] = []
        for ws_id in self.workspace_ids:
            ws = workspace_repo.get(self.db, id=ws_id)
            if ws and ws.paths:
                perms = ws.permissions if isinstance(ws.permissions, dict) else {}
                if perms.get(permission, False):
                    paths.extend(ws.paths)
        return paths

    def get_workspace_roots(self) -> List[Path]:
        """Returns resolved root Path objects for all workspaces."""
        from app.db.repositories.registry import workspace_repo
        roots: List[Path] = []
        for ws_id in self.workspace_ids:
            ws = workspace_repo.get(self.db, id=ws_id)
            if ws and ws.paths:
                for p in ws.paths:
                    try:
                        roots.append(Path(p).resolve())
                    except Exception:
                        pass
        return roots


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    capability: str = ""
    critical: bool = False
    source: str = "core"
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        pass
