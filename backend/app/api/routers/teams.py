from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.domain import schemas
from app.db.repositories.registry import team_repo
from app.domain.utils import generate_id
from app.skills.errors import SkillError
from app.skills.service import SkillService
from app.mcp.errors import MCPError
from app.mcp.service import MCPService

router = APIRouter(prefix="/teams", tags=["teams"])

@router.get("", response_model=List[schemas.Team])
def list_teams(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return team_repo.get_multi(db, skip=skip, limit=limit)

@router.post("", response_model=schemas.Team)
def create_team(obj_in: schemas.TeamCreate, db: Session = Depends(get_db)):
    new_id = generate_id("team")
    return team_repo.create(db, obj_in=obj_in, id=new_id)

@router.get("/{id}", response_model=schemas.Team)
def get_team(id: str, db: Session = Depends(get_db)):
    obj = team_repo.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Team not found")
    return obj

@router.put("/{id}", response_model=schemas.Team)
def update_team(id: str, obj_in: schemas.TeamUpdate, db: Session = Depends(get_db)):
    obj = team_repo.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Team not found")
    return team_repo.update(db, db_obj=obj, obj_in=obj_in)

@router.delete("/{id}")
def delete_team(id: str, db: Session = Depends(get_db)):
    obj = team_repo.remove(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"status": "deleted"}


@router.get("/{team_id}/skills", response_model=List[schemas.Skill])
def get_team_skills(team_id: str, db: Session = Depends(get_db)):
    try:
        return SkillService(db).get_team_skills(team_id)
    except SkillError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.put("/{team_id}/skills", response_model=List[schemas.Skill])
def update_team_skills(team_id: str, request: schemas.SkillIdsRequest, db: Session = Depends(get_db)):
    try:
        return SkillService(db).set_team_skills(team_id, request.skill_ids)
    except SkillError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/{team_id}/skills/{skill_id}", response_model=List[schemas.Skill])
def assign_skill_to_team(team_id: str, skill_id: str, db: Session = Depends(get_db)):
    try:
        return SkillService(db).assign_skill_to_team(team_id, skill_id)
    except SkillError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.delete("/{team_id}/skills/{skill_id}", response_model=List[schemas.Skill])
def remove_skill_from_team(team_id: str, skill_id: str, db: Session = Depends(get_db)):
    try:
        return SkillService(db).remove_skill_from_team(team_id, skill_id)
    except SkillError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/{team_id}/mcp", response_model=List[schemas.MCPServer])
def get_team_mcp_servers(team_id: str, db: Session = Depends(get_db)):
    try:
        return MCPService(db).get_team_servers(team_id)
    except MCPError as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.put("/{team_id}/mcp", response_model=List[schemas.MCPServer])
def update_team_mcp_servers(team_id: str, request: schemas.MCPServerIdsRequest, db: Session = Depends(get_db)):
    try:
        return MCPService(db).set_team_servers(team_id, request.server_ids)
    except MCPError as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.post("/{team_id}/mcp/{server_id}", response_model=List[schemas.MCPServer])
def assign_mcp_to_team(team_id: str, server_id: str, db: Session = Depends(get_db)):
    try:
        return MCPService(db).assign_team_server(team_id, server_id)
    except MCPError as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.delete("/{team_id}/mcp/{server_id}", response_model=List[schemas.MCPServer])
def remove_mcp_from_team(team_id: str, server_id: str, db: Session = Depends(get_db)):
    try:
        return MCPService(db).remove_team_server(team_id, server_id)
    except MCPError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
