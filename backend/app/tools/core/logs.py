from typing import Any, Dict

from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError


class LogsSearchTool(BaseTool):
    name = "logs.search"
    description = "Searches execution events/logs by event type or content."
    capability = "logs"
    critical = False
    source = "core"
    input_schema = {
        "execution_id": {"type": "string", "description": "Execution ID to search within."},
        "event_type": {"type": "string", "description": "Filter by event type."},
        "limit": {"type": "integer", "description": "Maximum results to return.", "default": 50},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        from app.db.models import ExecutionEventModel

        execution_id = arguments.get("execution_id", context.execution_id)
        event_type = arguments.get("event_type")
        limit = min(int(arguments.get("limit", 50)), 200)

        query = context.db.query(ExecutionEventModel).filter(
            ExecutionEventModel.execution_id == execution_id
        )
        if event_type:
            query = query.filter(ExecutionEventModel.type == event_type)

        events = query.order_by(ExecutionEventModel.created_at.asc()).limit(limit).all()

        return {
            "execution_id": execution_id,
            "events": [
                {
                    "id": e.id,
                    "type": e.type,
                    "source": e.source,
                    "source_id": e.source_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "content_preview": _preview_content(e.content),
                }
                for e in events
            ],
        }


class LogsGetExecutionTool(BaseTool):
    name = "logs.get_execution"
    description = "Returns details and events of a specific execution."
    capability = "logs"
    critical = False
    source = "core"
    input_schema = {
        "execution_id": {"type": "string", "description": "Execution ID.", "required": True}
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        from app.db.models import ExecutionModel, ExecutionEventModel

        execution_id = arguments.get("execution_id", "")
        if not execution_id:
            raise ToolError("MISSING_EXECUTION_ID", "Argument 'execution_id' is required")

        execution = context.db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
        if not execution:
            raise ToolError("EXECUTION_NOT_FOUND", f"Execution '{execution_id}' not found")

        events = (
            context.db.query(ExecutionEventModel)
            .filter(ExecutionEventModel.execution_id == execution_id)
            .order_by(ExecutionEventModel.created_at.asc())
            .limit(100)
            .all()
        )

        return {
            "id": execution.id,
            "type": execution.type,
            "status": execution.status,
            "target_id": execution.target_id,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "result_preview": (execution.result or "")[:500] if execution.result else None,
            "error": execution.error,
            "events": [
                {
                    "id": e.id,
                    "type": e.type,
                    "source": e.source,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ],
        }


def _preview_content(content: dict, max_len: int = 200) -> str:
    if not content:
        return ""
    import json
    try:
        raw = json.dumps(content, ensure_ascii=False)
        return raw[:max_len] + ("..." if len(raw) > max_len else "")
    except Exception:
        return str(content)[:max_len]
