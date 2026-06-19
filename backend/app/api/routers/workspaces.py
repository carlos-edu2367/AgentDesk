from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.domain import schemas
from app.db.repositories.registry import workspace_repo
from app.domain.utils import generate_id

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@router.get("", response_model=List[schemas.Workspace])
def list_workspaces(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return workspace_repo.get_multi(db, skip=skip, limit=limit)

@router.post("", response_model=schemas.Workspace)
def create_workspace(obj_in: schemas.WorkspaceCreate, db: Session = Depends(get_db)):
    new_id = generate_id("workspace")
    return workspace_repo.create(db, obj_in=obj_in, id=new_id)

@router.get("/{id}", response_model=schemas.Workspace)
def get_workspace(id: str, db: Session = Depends(get_db)):
    obj = workspace_repo.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return obj

@router.put("/{id}", response_model=schemas.Workspace)
def update_workspace(id: str, obj_in: schemas.WorkspaceUpdate, db: Session = Depends(get_db)):
    obj = workspace_repo.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace_repo.update(db, db_obj=obj, obj_in=obj_in)

@router.delete("/{id}")
def delete_workspace(id: str, db: Session = Depends(get_db)):
    obj = workspace_repo.remove(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "deleted"}
