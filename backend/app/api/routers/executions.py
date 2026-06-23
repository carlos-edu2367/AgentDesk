from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from app.db.database import get_db
from app.domain import schemas
from app.db.repositories.registry import execution_repo
from app.domain.utils import CHAT_DISPLAY_MAX_CHARS, generate_id, sanitize_for_output

router = APIRouter(prefix="/executions", tags=["executions"])

@router.get("", response_model=List[schemas.Execution])
def list_executions(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    type: Optional[str] = None,
    target_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    team_id: Optional[str] = None,
    status: Optional[str] = None,
    approval_mode: Optional[str] = None,
    query: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    offset: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(execution_repo.model)
    parsed_from = _parse_datetime(date_from)
    parsed_to = _parse_datetime(date_to)
    if parsed_from:
        q = q.filter(execution_repo.model.created_at >= parsed_from)
    if parsed_to:
        q = q.filter(execution_repo.model.created_at <= parsed_to)
    if type:
        q = q.filter(execution_repo.model.type == type)
    if target_id:
        q = q.filter(execution_repo.model.target_id == target_id)
    if agent_id:
        q = q.filter(execution_repo.model.type == "agent", execution_repo.model.target_id == agent_id)
    if team_id:
        q = q.filter(execution_repo.model.type == "team", execution_repo.model.target_id == team_id)
    if status:
        q = q.filter(execution_repo.model.status == status)
    if approval_mode:
        q = q.filter(execution_repo.model.approval_mode == approval_mode)

    rows = q.order_by(execution_repo.model.created_at.desc()).all()
    if query:
        needle = query.lower()
        rows = [
            row for row in rows
            if needle in " ".join([
                str(row.id or ""),
                str(row.target_id or ""),
                str(row.user_input or ""),
                str(row.result or ""),
                str(row.error or ""),
            ]).lower()
        ]
    start = offset if offset is not None else skip
    return rows[start:start + limit]

@router.post("", response_model=schemas.Execution)
def create_execution(obj_in: schemas.ExecutionCreate, db: Session = Depends(get_db)):
    new_id = generate_id("execution")
    return execution_repo.create(db, obj_in=obj_in, id=new_id)

@router.get("/{id}", response_model=schemas.Execution)
def get_execution(id: str, db: Session = Depends(get_db)):
    obj = execution_repo.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Execution not found")
    return obj

@router.put("/{id}", response_model=schemas.Execution)
def update_execution(id: str, obj_in: schemas.ExecutionUpdate, db: Session = Depends(get_db)):
    obj = execution_repo.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution_repo.update(db, db_obj=obj, obj_in=obj_in)

@router.delete("/{id}")
def delete_execution(id: str, db: Session = Depends(get_db)):
    obj = execution_repo.remove(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"status": "deleted"}

# New phase 5 routes
from pydantic import BaseModel
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse
import asyncio
from app.db.repositories.registry import execution_event_repo
from app.orchestrator.execution_engine import execution_engine
from app.orchestrator.team_engine import team_execution_engine
from app.orchestrator.event_bus import event_bus
from app.domain.enums import ExecutionType, ExecutionStatus, ApprovalMode
import json
from datetime import datetime
from pathlib import Path
from app.storage.appdata import get_appdata_dir

class AgentExecutionRequest(BaseModel):
    agent_id: str
    message: str
    approval_mode: ApprovalMode = ApprovalMode.MANUAL
    workspace_ids: List[str] = []
    stream: bool = True

class TeamExecutionRequest(BaseModel):
    team_id: str
    message: str
    approval_mode: ApprovalMode = ApprovalMode.MANUAL
    workspace_ids: List[str] = []
    stream: bool = True

@router.post("/agent")
def create_agent_execution(req: AgentExecutionRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    new_id = generate_id("execution")
    
    execution_in = schemas.ExecutionCreate(
        type=ExecutionType.AGENT,
        target_id=req.agent_id,
        user_input=req.message,
        status=ExecutionStatus.PENDING,
        approval_mode=req.approval_mode,
        workspace_ids=req.workspace_ids
    )
    
    execution_repo.create(db, obj_in=execution_in, id=new_id)
    
    # Launch background task
    background_tasks.add_task(execution_engine.run_agent_execution, new_id, req.agent_id, req.stream)
    
    return {"execution_id": new_id, "status": "running"}


@router.post("/team")
def create_team_execution(req: TeamExecutionRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.db.repositories.registry import team_repo

    team = team_repo.get(db, id=req.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.execution_strategy != "leader_managed":
        raise HTTPException(status_code=400, detail="Only leader_managed strategy is supported")

    new_id = generate_id("execution")
    execution_in = schemas.ExecutionCreate(
        type=ExecutionType.TEAM,
        target_id=req.team_id,
        user_input=req.message,
        status=ExecutionStatus.PENDING,
        approval_mode=req.approval_mode,
        workspace_ids=req.workspace_ids,
    )
    execution_repo.create(db, obj_in=execution_in, id=new_id)
    background_tasks.add_task(team_execution_engine.run_team_execution, new_id, req.team_id, req.stream)
    return {"execution_id": new_id, "status": "running"}

@router.get("/{id}/events")
async def get_execution_events(id: str, db: Session = Depends(get_db)):
    execution = execution_repo.get(db, id=id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Subscribe BEFORE snapshotting existing events. Otherwise any event emitted
    # in the window between the snapshot and the subscription is lost (this is the
    # race that made resumed-after-approval turns only appear after a page reload):
    # the event_bus has no buffer, so a publish with no live subscriber is dropped.
    queue = event_bus.subscribe(id)

    async def event_generator():
        sent_ids: set[str] = set()

        def render(event: dict) -> str:
            if isinstance(event.get("created_at"), datetime):
                event["created_at"] = event["created_at"].isoformat()
            return f"data: {json.dumps(event)}\n\n"

        try:
            # Replay persisted events, skipping raw streaming token deltas.
            # model_chunk / model_reasoning_chunk are only useful while a turn
            # is actively streaming; replaying thousands of them on reconnect
            # slows the SSE handshake with no display benefit (the live stream
            # will deliver new chunks, and completed turns use agent_completed
            # for the final answer). Tool and lifecycle events are kept.
            _SKIP_REPLAY = frozenset({'model_chunk', 'model_reasoning_chunk'})
            db_events = (
                db.query(execution_event_repo.model)
                .filter(execution_event_repo.model.execution_id == id)
                .filter(execution_event_repo.model.type.notin_(_SKIP_REPLAY))
                .order_by(execution_event_repo.model.created_at.asc())
                .all()
            )
            for e in db_events:
                ev = schemas.ExecutionEvent.model_validate(e).model_dump()
                if ev.get("id"):
                    sent_ids.add(ev["id"])
                yield render(ev)

            # Re-read fresh status: the snapshot above may be stale if the engine
            # advanced while we were replaying.
            fresh = execution_repo.get(db, id=id)
            finished = fresh and fresh.status in [
                ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED,
            ]

            if finished:
                # Drain any live events that arrived during replay (deduped), then stop.
                while not queue.empty():
                    event = queue.get_nowait()
                    if isinstance(event, dict) and event.get("type") == "sse_close_connection":
                        return
                    if isinstance(event, dict) and event.get("id") in sent_ids:
                        continue
                    if isinstance(event, dict):
                        yield render(event)
                return

            while True:
                event = await queue.get()
                if isinstance(event, dict) and event.get("type") == "sse_close_connection":
                    break
                if isinstance(event, dict) and event.get("id") in sent_ids:
                    continue
                if isinstance(event, dict):
                    yield render(event)
        finally:
            event_bus.unsubscribe(id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{id}/audit", response_model=List[schemas.AuditLogView])
def get_execution_audit(id: str, db: Session = Depends(get_db)):
    execution = execution_repo.get(db, id=id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _execution_audit_logs(db, id)


@router.get("/{id}/detail", response_model=schemas.ExecutionDetail)
def get_execution_detail(id: str, db: Session = Depends(get_db)):
    return _build_execution_detail(db, id)


@router.post("/{id}/export", response_model=schemas.ExecutionExportResponse)
def export_execution(id: str, request: schemas.ExecutionExportRequest, db: Session = Depends(get_db)):
    detail = _build_execution_detail(db, id)
    safe_detail = sanitize_for_output(detail.model_dump(mode="json"))
    reports_dir = get_appdata_dir() / "exports" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if request.format == "json":
        content: Any = safe_detail
        path = reports_dir / f"{id}.json"
        path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        content = _render_markdown_report(safe_detail)
        path = reports_dir / f"{id}.md"
        path.write_text(content, encoding="utf-8")

    return schemas.ExecutionExportResponse(format=request.format, path=str(path), content=content)

@router.post("/{id}/cancel")
def cancel_execution(id: str, db: Session = Depends(get_db)):
    execution = execution_repo.get(db, id=id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
        return {"status": "already_finished"}

    execution_engine.cancel_execution(id)
    return {"status": "cancelled"}


from app.db.repositories.registry import approval_repo
from app.db.models import ApprovalRequestModel
from app.domain.schemas import ApprovalRequest, ApprovalResolutionRequest

@router.get("/{id}/approvals", response_model=List[ApprovalRequest])
def list_execution_approvals(id: str, db: Session = Depends(get_db)):
    execution = execution_repo.get(db, id=id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    approvals = db.query(ApprovalRequestModel).filter(
        ApprovalRequestModel.execution_id == id
    ).order_by(ApprovalRequestModel.created_at.desc()).all()
    return approvals


@router.post("/{id}/approvals/{approval_id}")
async def resolve_approval(
    id: str,
    approval_id: str,
    req: ApprovalResolutionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    execution = execution_repo.get(db, id=id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.status != ExecutionStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Execution is not waiting for approval (status: {execution.status})")

    approval = approval_repo.get(db, id=approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.execution_id != id:
        raise HTTPException(status_code=400, detail="Approval does not belong to this execution")

    from app.domain.enums import ApprovalStatus
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Approval is already {approval.status}")

    background_tasks.add_task(
        execution_engine.resume_agent_execution,
        id, approval_id,
        req.approved,
        req.reason or "",
        True,
        str(req.approval_mode.value) if req.approval_mode else None,
    )

    action = "approved" if req.approved else "rejected"
    return {"status": action, "approval_id": approval_id, "execution_id": id}


def _build_execution_detail(db: Session, execution_id: str) -> schemas.ExecutionDetail:
    execution = execution_repo.get(db, id=execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    events = db.query(execution_event_repo.model).filter(
        execution_event_repo.model.execution_id == execution_id
    ).order_by(execution_event_repo.model.created_at.asc()).all()
    approvals = db.query(ApprovalRequestModel).filter(
        ApprovalRequestModel.execution_id == execution_id
    ).order_by(ApprovalRequestModel.created_at.asc()).all()
    audit_logs = _execution_audit_logs(db, execution_id)
    event_views = [
        schemas.ExecutionEvent(
            **{
                **schemas.ExecutionEvent.model_validate(event).model_dump(),
                "content": sanitize_for_output(event.content or {}, max_chars=CHAT_DISPLAY_MAX_CHARS),
            }
        )
        for event in events
    ]
    approval_views = [
        schemas.ApprovalRequest(
            **{
                **schemas.ApprovalRequest.model_validate(approval).model_dump(),
                "arguments": sanitize_for_output(approval.arguments or {}),
                "pending_state": sanitize_for_output(approval.pending_state or {}),
            }
        )
        for approval in approvals
    ]
    summary = _build_detail_summary(execution, event_views, audit_logs, approval_views)

    return schemas.ExecutionDetail(
        execution=schemas.Execution.model_validate(execution),
        events=event_views,
        audit_logs=audit_logs,
        approvals=approval_views,
        artifacts=[],
        summary=summary,
    )


def _execution_audit_logs(db: Session, execution_id: str) -> List[schemas.AuditLogView]:
    from app.api.routers.audit import audit_to_view
    from app.db.models import AuditLogModel

    logs = db.query(AuditLogModel).filter(
        AuditLogModel.execution_id == execution_id
    ).order_by(AuditLogModel.created_at.asc()).all()
    return [audit_to_view(log) for log in logs]


def _build_detail_summary(
    execution,
    events: List[schemas.ExecutionEvent],
    audit_logs: List[schemas.AuditLogView],
    approvals: List[schemas.ApprovalRequest],
) -> schemas.ExecutionDetailSummary:
    tools: set[str] = set()
    agents: set[str] = set()
    mcp_servers: set[str] = set()
    plugins: set[str] = set()
    skills: set[str] = set()
    memories: set[str] = set()

    for event in events:
        _collect_tool(event.content, tools, mcp_servers)
        if event.source_id and (event.source_id.startswith("agent_") or event.source == "runtime"):
            agents.add(event.source_id)
        content = event.content or {}
        for memory_id in content.get("memory_ids", []) or []:
            memories.add(str(memory_id))
        if content.get("memory_id"):
            memories.add(str(content["memory_id"]))
        if content.get("skill"):
            skills.add(str(content["skill"]))
        for skill_id in content.get("skills", []) or []:
            skills.add(str(skill_id))

    critical_actions = 0
    for log in audit_logs:
        if log.agent_id:
            agents.add(log.agent_id)
        if log.tool:
            tools.add(log.tool)
            if log.tool.startswith("mcp."):
                parts = log.tool.split(".")
                if len(parts) >= 2:
                    mcp_servers.add(parts[1])
        if isinstance(log.data, dict):
            if log.data.get("plugin_id"):
                plugins.add(str(log.data["plugin_id"]))
            if log.data.get("risk_level") in {"high", "critical"} or log.risk_level in {"high", "critical"}:
                critical_actions += 1
        elif log.risk_level in {"high", "critical"}:
            critical_actions += 1

    return schemas.ExecutionDetailSummary(
        total_events=len(events),
        total_audit_logs=len(audit_logs),
        tools_used=sorted(tools),
        agents_involved=sorted(agent for agent in agents if agent),
        mcp_servers_used=sorted(mcp_servers),
        plugins_used=sorted(plugins),
        skills_used=sorted(skills),
        memories_used=sorted(memories),
        approval_mode=str(execution.approval_mode),
        critical_actions_count=critical_actions,
        auto_approved_count=sum(1 for log in audit_logs if log.event_type == "approval_auto_granted"),
        manual_approved_count=sum(1 for approval in approvals if _status_value(approval.status) == "approved"),
        manual_rejected_count=sum(1 for approval in approvals if _status_value(approval.status) == "rejected"),
    )


def _collect_tool(content: dict, tools: set[str], mcp_servers: set[str]) -> None:
    tool = content.get("tool") if isinstance(content, dict) else None
    if not tool:
        return
    tool_text = str(tool)
    tools.add(tool_text)
    if tool_text.startswith("mcp."):
        parts = tool_text.split(".")
        if len(parts) >= 2:
            mcp_servers.add(parts[1])


def _render_markdown_report(detail: dict[str, Any]) -> str:
    execution = detail["execution"]
    summary = detail["summary"]
    lines = [
        "# AgentDesk Execution Report",
        "",
        "## Execution",
        f"- ID: {execution.get('id')}",
        f"- Type: {execution.get('type')}",
        f"- Status: {execution.get('status')}",
        f"- Started: {execution.get('created_at')}",
        f"- Completed: {execution.get('completed_at')}",
        f"- Approval Mode: {execution.get('approval_mode')}",
        "",
        "## User Request",
        "",
        str(execution.get("user_input") or ""),
        "",
        "## Final Result",
        "",
        str(execution.get("result") or execution.get("error") or ""),
        "",
        "## Agents Involved",
        "",
        _bullet_list(summary.get("agents_involved", [])),
        "",
        "## Tools Used",
        "",
        _bullet_list(summary.get("tools_used", [])),
        "",
        "## Approvals",
        "",
        _approval_lines(detail.get("approvals", [])),
        "",
        "## Timeline",
        "",
        _event_lines(detail.get("events", [])),
        "",
        "## Audit Logs",
        "",
        _audit_lines(detail.get("audit_logs", [])),
        "",
    ]
    return "\n".join(lines)


def _bullet_list(items: list[Any]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def _approval_lines(approvals: list[dict[str, Any]]) -> str:
    if not approvals:
        return "- None"
    return "\n".join(
        f"- {item.get('created_at')} | {item.get('status')} | {item.get('tool')} | {item.get('summary')}"
        for item in approvals
    )


def _event_lines(events: list[dict[str, Any]]) -> str:
    if not events:
        return "- None"
    return "\n".join(
        f"- {item.get('created_at')} | {item.get('type')} | {item.get('source')}:{item.get('source_id')} | {json.dumps(item.get('content', {}), ensure_ascii=False)}"
        for item in events
    )


def _audit_lines(logs: list[dict[str, Any]]) -> str:
    if not logs:
        return "- None"
    return "\n".join(
        f"- {item.get('created_at')} | {item.get('risk_level')} | {item.get('event_type')} | {item.get('summary')}"
        for item in logs
    )


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid datetime: {value}") from exc


def _status_value(value: Any) -> str:
    return str(getattr(value, "value", value))
