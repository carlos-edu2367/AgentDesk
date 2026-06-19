from app.db.repositories.registry import team_repo
from app.domain.utils import generate_id
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError


class TeamListTool(BaseTool):
    name = "team.list"
    description = "List available agent teams."
    capability = "team_control"
    critical = False
    input_schema = {}
    output_schema = {
        "teams": [
            {"id": "team_id", "name": "Team name", "description": "Team description"}
        ]
    }

    async def execute(self, arguments: dict, context: ToolExecutionContext) -> dict:
        teams = team_repo.get_multi(context.db, limit=500)
        return {
            "teams": [
                {"id": t.id, "name": t.name, "description": t.description or ""}
                for t in teams
            ]
        }


class TeamExecuteTool(BaseTool):
    name = "team.execute"
    description = "Create a team execution for a configured agent team."
    capability = "team_control"
    critical = False
    input_schema = {
        "team_id": "string",
        "message": "string",
    }
    output_schema = {"execution_id": "string", "status": "string"}

    async def execute(self, arguments: dict, context: ToolExecutionContext) -> dict:
        team_id = str(arguments.get("team_id") or "").strip()
        message = str(arguments.get("message") or "").strip()
        if not team_id:
            raise ToolError("INVALID_ARGUMENTS", "team_id is required")
        if not message:
            raise ToolError("INVALID_ARGUMENTS", "message is required")
        if not team_repo.get(context.db, id=team_id):
            raise ToolError("TEAM_NOT_FOUND", f"Team '{team_id}' was not found")

        from app.db.repositories.registry import execution_repo
        from app.domain import schemas
        from app.domain.enums import ExecutionStatus, ExecutionType

        execution_id = generate_id("execution")
        execution_repo.create(
            context.db,
            obj_in=schemas.ExecutionCreate(
                type=ExecutionType.TEAM,
                target_id=team_id,
                user_input=message,
                status=ExecutionStatus.PENDING,
                approval_mode=context.approval_mode,
                workspace_ids=context.workspace_ids,
            ),
            id=execution_id,
        )
        return {"execution_id": execution_id, "status": "pending"}
