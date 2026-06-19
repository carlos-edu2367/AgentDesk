import os

routers = [
    ("teams", "Team", "team"),
    ("workspaces", "Workspace", "workspace"),
    ("executions", "Execution", "execution"),
    ("skills", "Skill", "skill"),
    ("plugins", "Plugin", "plugin"),
    ("mcp", "MCPServer", "mcp"),
    ("memories", "Memory", "memory")
]

template = """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.domain import schemas
from app.db.repositories.registry import {repo_name}_repo
from app.domain.utils import generate_id

router = APIRouter(prefix="/{route}", tags=["{route}"])

@router.get("", response_model=List[schemas.{schema_name}])
def list_{route}(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return {repo_name}_repo.get_multi(db, skip=skip, limit=limit)

@router.post("", response_model=schemas.{schema_name})
def create_{singular}(obj_in: schemas.{schema_name}Create, db: Session = Depends(get_db)):
    new_id = generate_id("{singular}")
    return {repo_name}_repo.create(db, obj_in=obj_in, id=new_id)

@router.get("/{{id}}", response_model=schemas.{schema_name})
def get_{singular}(id: str, db: Session = Depends(get_db)):
    obj = {repo_name}_repo.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="{schema_name} not found")
    return obj

@router.put("/{{id}}", response_model=schemas.{schema_name})
def update_{singular}(id: str, obj_in: schemas.{schema_name}Update, db: Session = Depends(get_db)):
    obj = {repo_name}_repo.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="{schema_name} not found")
    return {repo_name}_repo.update(db, db_obj=obj, obj_in=obj_in)

@router.delete("/{{id}}")
def delete_{singular}(id: str, db: Session = Depends(get_db)):
    obj = {repo_name}_repo.remove(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="{schema_name} not found")
    return {{"status": "deleted"}}
"""

base_dir = r"c:\Users\Carlos\Documents\Carlos Eduardo\agentes\AgentDesk\backend\app\api\routers"
os.makedirs(base_dir, exist_ok=True)

for route, schema_name, singular in routers:
    repo_name = singular
    content = template.format(route=route, schema_name=schema_name, singular=singular, repo_name=repo_name)
    with open(os.path.join(base_dir, f"{route}.py"), "w", encoding="utf-8") as f:
        f.write(content)
