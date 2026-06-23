from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.domain import schemas
from app.db.repositories.registry import (
    conversation_repo,
    execution_repo,
    execution_event_repo,
    approval_repo,
)
from app.domain.utils import CHAT_DISPLAY_MAX_CHARS, generate_id, sanitize_for_output
from app.domain.enums import ExecutionType, ExecutionStatus
from app.orchestrator.execution_engine import execution_engine
from app.orchestrator.team_engine import team_execution_engine

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=schemas.Conversation)
def create_conversation(obj_in: schemas.ConversationCreate, db: Session = Depends(get_db)):
    return conversation_repo.create(db, obj_in=obj_in, id=generate_id("conversation"))


@router.get("", response_model=List[schemas.Conversation])
def list_conversations(
    type: Optional[str] = None,
    target_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(conversation_repo.model)
    if type:
        q = q.filter(conversation_repo.model.type == type)
    if target_id:
        q = q.filter(conversation_repo.model.target_id == target_id)
    return q.order_by(conversation_repo.model.updated_at.desc()).limit(limit).all()


@router.patch("/{id}", response_model=schemas.Conversation)
def update_conversation(id: str, obj_in: schemas.ConversationUpdate, db: Session = Depends(get_db)):
    conv = conversation_repo.get(db, id=id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_repo.update(db, db_obj=conv, obj_in=obj_in)


@router.delete("/{id}", status_code=204)
def delete_conversation(id: str, db: Session = Depends(get_db)):
    """Delete a conversation along with all of its turns (executions, their
    events, and any approval requests). There is no FK cascade, so the child
    rows are removed explicitly to avoid orphans."""
    conv = conversation_repo.get(db, id=id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    execution_ids = [
        row[0]
        for row in db.query(execution_repo.model.id)
        .filter(execution_repo.model.conversation_id == id)
        .all()
    ]
    if execution_ids:
        db.query(execution_event_repo.model).filter(
            execution_event_repo.model.execution_id.in_(execution_ids)
        ).delete(synchronize_session=False)
        db.query(approval_repo.model).filter(
            approval_repo.model.execution_id.in_(execution_ids)
        ).delete(synchronize_session=False)
        db.query(execution_repo.model).filter(
            execution_repo.model.id.in_(execution_ids)
        ).delete(synchronize_session=False)

    db.delete(conv)
    db.commit()
    return Response(status_code=204)


@router.get("/{id}", response_model=schemas.ConversationDetail)
def get_conversation(id: str, db: Session = Depends(get_db)):
    conv = conversation_repo.get(db, id=id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    executions = (
        db.query(execution_repo.model)
        .filter(execution_repo.model.conversation_id == id)
        .order_by(execution_repo.model.created_at.asc())
        .all()
    )

    turns: List[schemas.ConversationTurn] = []
    for ex in executions:
        events = (
            db.query(execution_event_repo.model)
            .filter(execution_event_repo.model.execution_id == ex.id)
            .order_by(execution_event_repo.model.created_at.asc())
            .all()
        )
        event_views = [
            schemas.ExecutionEvent(
                **{
                    **schemas.ExecutionEvent.model_validate(e).model_dump(),
                    "content": sanitize_for_output(e.content or {}, max_chars=CHAT_DISPLAY_MAX_CHARS),
                }
            )
            for e in events
        ]
        turns.append(
            schemas.ConversationTurn(
                execution=schemas.Execution.model_validate(ex),
                events=event_views,
            )
        )

    return schemas.ConversationDetail(
        conversation=schemas.Conversation.model_validate(conv),
        turns=turns,
    )


@router.post("/{id}/messages")
def post_message(
    id: str,
    req: schemas.ConversationMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    conv = conversation_repo.get(db, id=id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Per-message workspace_ids override the conversation default; otherwise the
    # chat inherits the workspaces granted to the conversation. Without this the
    # chat never grants any workspace and write/terminal tools fail.
    workspace_ids = req.workspace_ids or list(conv.workspace_ids or [])
    # Per-message override wins; otherwise inherit the chat's configured step budget.
    max_steps = req.max_steps if req.max_steps is not None else conv.max_steps

    new_id = generate_id("execution")
    execution_in = schemas.ExecutionCreate(
        type=ExecutionType(conv.type),
        target_id=conv.target_id,
        user_input=req.message,
        status=ExecutionStatus.PENDING,
        approval_mode=req.approval_mode,
        workspace_ids=workspace_ids,
        max_steps=max_steps,
        conversation_id=id,
    )
    execution_repo.create(db, obj_in=execution_in, id=new_id)

    # Set a title from the first message if not already set.
    if not conv.title:
        conversation_repo.update(
            db, db_obj=conv, obj_in=schemas.ConversationUpdate(title=req.message[:60])
        )

    if conv.type == "team":
        background_tasks.add_task(
            team_execution_engine.run_team_execution, new_id, conv.target_id, req.stream
        )
    else:
        background_tasks.add_task(
            execution_engine.run_agent_execution, new_id, conv.target_id, req.stream
        )

    return {"execution_id": new_id, "conversation_id": id, "status": "running"}
