from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import AuditLogModel, ExecutionEventModel, ExecutionModel
from app.domain import schemas
from app.domain.utils import generate_id

router = APIRouter(prefix="/logs", tags=["logs"])

PROTECTED_EXECUTION_STATUSES = {"running", "waiting_approval"}


@router.post("/cleanup", response_model=schemas.LogsCleanupResponse)
def cleanup_logs(request: schemas.LogsCleanupRequest, db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(days=max(request.older_than_days, 1))
    removable_execution_ids = [
        row.id for row in db.query(ExecutionModel.id)
        .filter(ExecutionModel.created_at < cutoff)
        .filter(~ExecutionModel.status.in_(PROTECTED_EXECUTION_STATUSES))
        .all()
    ]

    event_query = db.query(ExecutionEventModel).filter(
        ExecutionEventModel.execution_id.in_(removable_execution_ids)
    )
    audit_query = db.query(AuditLogModel).filter(
        AuditLogModel.created_at < cutoff,
        AuditLogModel.execution_id.in_(removable_execution_ids),
    )

    would_delete = schemas.LogsCleanupCounts(
        execution_events=event_query.count() if request.include_execution_events else 0,
        audit_logs=audit_query.count() if request.include_audit_logs else 0,
        executions=0,
    )

    if request.dry_run:
        return schemas.LogsCleanupResponse(dry_run=True, would_delete=would_delete)

    deleted = schemas.LogsCleanupCounts()
    if request.include_execution_events:
        deleted.execution_events = event_query.delete(synchronize_session=False)
    if request.include_audit_logs:
        deleted.audit_logs = audit_query.delete(synchronize_session=False)

    db.add(AuditLogModel(
        id=generate_id("audit"),
        execution_id="system",
        agent_id="system",
        event_type="logs_cleanup_executed",
        risk_level="medium",
        summary="Manual logs cleanup executed",
        data={
            "older_than_days": request.older_than_days,
            "include_audit_logs": request.include_audit_logs,
            "include_execution_events": request.include_execution_events,
            "deleted": deleted.model_dump(),
        },
    ))
    db.commit()

    return schemas.LogsCleanupResponse(
        dry_run=False,
        would_delete=would_delete,
        deleted=deleted,
    )
