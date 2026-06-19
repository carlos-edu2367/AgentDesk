from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.domain import schemas
from app.skills.errors import SkillError
from app.skills.service import SkillService

router = APIRouter(prefix="/skills", tags=["skills"])


def _handle_skill_error(exc: SkillError):
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("", response_model=List[schemas.Skill])
def list_skills(db: Session = Depends(get_db)):
    return SkillService(db).list_skills()


@router.post("", response_model=schemas.Skill)
def create_skill(obj_in: schemas.SkillCreate, db: Session = Depends(get_db)):
    try:
        return SkillService(db).create_skill(obj_in)
    except SkillError as exc:
        _handle_skill_error(exc)


@router.post("/import", response_model=schemas.Skill)
def import_skill(request: schemas.SkillImportRequest, overwrite: bool = False, db: Session = Depends(get_db)):
    try:
        return SkillService(db).import_skill_json(request.skill, overwrite=overwrite)
    except SkillError as exc:
        _handle_skill_error(exc)


@router.get("/{skill_id}/export")
def export_skill(skill_id: str, db: Session = Depends(get_db)):
    try:
        return SkillService(db).export_skill_json(skill_id)
    except SkillError as exc:
        _handle_skill_error(exc)


@router.get("/{skill_id}", response_model=schemas.Skill)
def get_skill(skill_id: str, db: Session = Depends(get_db)):
    try:
        return SkillService(db).get_skill(skill_id)
    except SkillError as exc:
        _handle_skill_error(exc)


@router.put("/{skill_id}", response_model=schemas.Skill)
def update_skill(skill_id: str, obj_in: schemas.SkillUpdate, db: Session = Depends(get_db)):
    try:
        return SkillService(db).update_skill(skill_id, obj_in)
    except SkillError as exc:
        _handle_skill_error(exc)


@router.delete("/{skill_id}")
def delete_skill(skill_id: str, db: Session = Depends(get_db)):
    try:
        SkillService(db).delete_skill(skill_id)
        return {"status": "deleted"}
    except SkillError as exc:
        _handle_skill_error(exc)
