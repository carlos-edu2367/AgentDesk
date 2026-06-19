from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict, List

from app.db.database import get_db
from app.db.repositories.registry import agent_repo, workspace_repo
from app.domain.schemas import AgentUpdate
from app.tools.registry import tool_registry
from app.tools.schemas import AgentToolsConfig, CapabilityInfo, ToolDefinition
from app.permissions.gate import check_tool_permission, get_available_tool_definitions
from app.tools.errors import ToolDeniedError, ToolError, ToolNotFoundError
from pydantic import BaseModel

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=List[ToolDefinition])
def list_tools():
    return tool_registry.list_all()


@router.get("/capabilities", response_model=List[CapabilityInfo])
def list_capabilities():
    return tool_registry.list_capabilities()


class ToolTestRequest(BaseModel):
    agent_id: str
    tool: str
    arguments: Dict[str, Any] = {}
    workspace_ids: List[str] = []


class ToolTestResult(BaseModel):
    tool: str
    status: str
    result: Any = None
    error: str = ""
    error_code: str = ""


@router.post("/test", response_model=ToolTestResult)
async def test_tool(req: ToolTestRequest, db: Session = Depends(get_db)):
    agent = agent_repo.get(db, id=req.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        check_tool_permission(
            req.tool,
            agent.capabilities or [],
            agent.explicit_tools or [],
            agent.blocked_tools or [],
        )
    except ToolNotFoundError as exc:
        return ToolTestResult(tool=req.tool, status="error", error=exc.message, error_code=exc.code)
    except ToolDeniedError as exc:
        return ToolTestResult(tool=req.tool, status="denied", error=exc.message, error_code=exc.code)

    from app.tools.base import ToolExecutionContext

    # Validate workspace_ids exist
    for ws_id in req.workspace_ids:
        ws = workspace_repo.get(db, id=ws_id)
        if not ws:
            raise HTTPException(status_code=404, detail=f"Workspace '{ws_id}' not found")

    context = ToolExecutionContext(
        execution_id="test",
        agent_id=req.agent_id,
        workspace_ids=req.workspace_ids,
        db=db,
    )

    try:
        tool = tool_registry.get(req.tool)
        result = await tool.execute(req.arguments, context)
        return ToolTestResult(tool=req.tool, status="success", result=result)
    except ToolError as exc:
        return ToolTestResult(tool=req.tool, status="error", error=exc.message, error_code=exc.code)
    except Exception as exc:
        return ToolTestResult(tool=req.tool, status="error", error=str(exc))
