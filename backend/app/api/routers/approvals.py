from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db.models import ApprovalRequestModel
from app.domain import schemas
from app.db.repositories.registry import approval_repo

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=List[schemas.ApprovalRequest])
def list_approvals(status: str = None, db: Session = Depends(get_db)):
    q = db.query(ApprovalRequestModel)
    if status:
        q = q.filter(ApprovalRequestModel.status == status)
    return q.order_by(ApprovalRequestModel.created_at.desc()).all()


@router.get("/{approval_id}", response_model=schemas.ApprovalRequest)
def get_approval(approval_id: str, db: Session = Depends(get_db)):
    obj = approval_repo.get(db, id=approval_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Approval not found")
    return obj
