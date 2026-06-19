from typing import Any, Dict

from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError, WorkspaceNotFoundError


class WorkspaceListTool(BaseTool):
    name = "workspace.list"
    description = "Returns the list of workspaces associated with this execution."
    capability = "workspace"
    critical = False
    source = "core"
    input_schema = {}

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        from app.db.repositories.registry import workspace_repo

        workspaces = []
        for ws_id in context.workspace_ids:
            ws = workspace_repo.get(context.db, id=ws_id)
            if ws:
                workspaces.append({
                    "id": ws.id,
                    "name": ws.name,
                    "paths": ws.paths or [],
                    "permissions": ws.permissions or {},
                })
        return {"workspaces": workspaces}


class WorkspaceGetTool(BaseTool):
    name = "workspace.get"
    description = "Returns details of a specific workspace by ID."
    capability = "workspace"
    critical = False
    source = "core"
    input_schema = {
        "workspace_id": {"type": "string", "description": "Workspace ID.", "required": True}
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        from app.db.repositories.registry import workspace_repo

        workspace_id = arguments.get("workspace_id", "")
        if not workspace_id:
            raise ToolError("MISSING_WORKSPACE_ID", "Argument 'workspace_id' is required")

        if workspace_id not in context.workspace_ids:
            raise ToolError("WORKSPACE_NOT_IN_CONTEXT", f"Workspace '{workspace_id}' is not authorized for this execution")

        ws = workspace_repo.get(context.db, id=workspace_id)
        if not ws:
            raise WorkspaceNotFoundError(workspace_id)

        return {
            "id": ws.id,
            "name": ws.name,
            "paths": ws.paths or [],
            "permissions": ws.permissions or {},
        }
