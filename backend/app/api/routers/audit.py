from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import AuditLogModel
from app.domain import schemas
from app.domain.utils import sanitize_for_output

router = APIRouter(prefix="/audit", tags=["audit"])


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid datetime: {value}") from exc


def audit_to_view(log: AuditLogModel) -> schemas.AuditLogView:
    data = sanitize_for_output(log.data or {})
    if not isinstance(data, dict):
        data = {"value": data}
    return schemas.AuditLogView(
        id=log.id,
        execution_id=log.execution_id,
        agent_id=log.agent_id,
        event_type=log.event_type,
        risk_level=log.risk_level,
        summary=sanitize_for_output(log.summary),
        data=data,
        created_at=log.created_at,
        team_id=_data_value(data, "team_id"),
        tool=_data_value(data, "tool"),
        source=_data_value(data, "source"),
        source_id=_data_value(data, "source_id"),
        approval_mode=_data_value(data, "approval_mode"),
        status=_data_value(data, "status"),
        duration_ms=_int_or_none(_data_value(data, "duration_ms")),
    )


@router.get("", response_model=schemas.PaginatedAuditLogs)
def list_audit_logs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    execution_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    team_id: Optional[str] = None,
    event_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    tool: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    approval_mode: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLogModel)
    parsed_from = _parse_datetime(date_from)
    parsed_to = _parse_datetime(date_to)
    if parsed_from:
        q = q.filter(AuditLogModel.created_at >= parsed_from)
    if parsed_to:
        q = q.filter(AuditLogModel.created_at <= parsed_to)
    if execution_id:
        q = q.filter(AuditLogModel.execution_id == execution_id)
    if agent_id:
        q = q.filter(AuditLogModel.agent_id == agent_id)
    if event_type:
        q = q.filter(AuditLogModel.event_type == event_type)
    if risk_level:
        q = q.filter(AuditLogModel.risk_level == risk_level)

    logs = q.order_by(AuditLogModel.created_at.desc()).all()
    filtered = [
        log for log in logs
        if _matches_data_filters(log, team_id, tool, source, status, approval_mode)
        and _matches_query(log, query)
    ]
    page = filtered[offset:offset + limit]
    return schemas.PaginatedAuditLogs(
        items=[audit_to_view(log) for log in page],
        total=len(filtered),
        limit=limit,
        offset=offset,
    )


@router.get("/{audit_id}", response_model=schemas.AuditLogView)
def get_audit_log(audit_id: str, db: Session = Depends(get_db)):
    log = db.query(AuditLogModel).filter(AuditLogModel.id == audit_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return audit_to_view(log)


def _matches_data_filters(
    log: AuditLogModel,
    team_id: Optional[str],
    tool: Optional[str],
    source: Optional[str],
    status: Optional[str],
    approval_mode: Optional[str],
) -> bool:
    data = log.data or {}
    return (
        _match_optional(data, "team_id", team_id)
        and _match_optional(data, "tool", tool)
        and _match_optional(data, "source", source)
        and _match_optional(data, "status", status)
        and _match_optional(data, "approval_mode", approval_mode)
    )


def _matches_query(log: AuditLogModel, query: Optional[str]) -> bool:
    if not query:
        return True
    needle = query.lower()
    haystack = " ".join([
        str(log.id or ""),
        str(log.execution_id or ""),
        str(log.agent_id or ""),
        str(log.event_type or ""),
        str(log.risk_level or ""),
        str(log.summary or ""),
        str(log.data or ""),
    ]).lower()
    return needle in haystack


def _match_optional(data: dict[str, Any], key: str, expected: Optional[str]) -> bool:
    if expected is None:
        return True
    return str(data.get(key, "")) == expected


def _data_value(data: dict[str, Any], key: str) -> Optional[str]:
    value = data.get(key)
    return None if value is None else str(value)


def _int_or_none(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
