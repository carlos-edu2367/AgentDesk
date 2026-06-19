from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.domain import schemas
from app.db.repositories.registry import agent_repo
from app.domain.utils import generate_id
from app.tools.schemas import AgentToolsConfig, ToolDefinition
from app.permissions.gate import get_available_tool_definitions
from app.skills.errors import SkillError
from app.skills.service import SkillService
from app.plugins.errors import PluginError
from app.plugins.service import PluginService
from app.mcp.errors import MCPError
from app.mcp.service import MCPService

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("", response_model=List[schemas.Agent])
def list_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return agent_repo.get_multi(db, skip=skip, limit=limit)

@router.post("", response_model=schemas.Agent)
def create_agent(agent_in: schemas.AgentCreate, db: Session = Depends(get_db)):
    new_id = generate_id("agent")
    return agent_repo.create(db, obj_in=agent_in, id=new_id)

@router.get("/{agent_id}", response_model=schemas.Agent)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = agent_repo.get(db, id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.put("/{agent_id}", response_model=schemas.Agent)
def update_agent(agent_id: str, agent_in: schemas.AgentUpdate, db: Session = Depends(get_db)):
    agent = agent_repo.get(db, id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent_repo.update(db, db_obj=agent, obj_in=agent_in)

@router.delete("/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = agent_repo.remove(db, id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deleted"}


@router.get("/{agent_id}/tools", response_model=AgentToolsConfig)
def get_agent_tools(agent_id: str, db: Session = Depends(get_db)):
    agent = agent_repo.get(db, id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentToolsConfig(
        capabilities=agent.capabilities or [],
        explicit_tools=agent.explicit_tools or [],
        blocked_tools=agent.blocked_tools or [],
    )


@router.put("/{agent_id}/tools", response_model=AgentToolsConfig)
def update_agent_tools(agent_id: str, config: AgentToolsConfig, db: Session = Depends(get_db)):
    agent = agent_repo.get(db, id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent_repo.update(db, db_obj=agent, obj_in=schemas.AgentUpdate(
        capabilities=config.capabilities,
        explicit_tools=config.explicit_tools,
        blocked_tools=config.blocked_tools,
    ))
    return config


@router.get("/{agent_id}/tools/available", response_model=List[ToolDefinition])
def get_agent_available_tools(agent_id: str, db: Session = Depends(get_db)):
    """Returns all tool definitions available for this agent after applying permissions."""
    agent = agent_repo.get(db, id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return get_available_tool_definitions(
        agent.capabilities or [],
        agent.explicit_tools or [],
        agent.blocked_tools or [],
    )


@router.get("/{agent_id}/skills", response_model=List[schemas.Skill])
def get_agent_skills(agent_id: str, db: Session = Depends(get_db)):
    try:
        return SkillService(db).get_agent_skills(agent_id)
    except SkillError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.put("/{agent_id}/skills", response_model=List[schemas.Skill])
def update_agent_skills(agent_id: str, request: schemas.SkillIdsRequest, db: Session = Depends(get_db)):
    try:
        return SkillService(db).set_agent_skills(agent_id, request.skill_ids)
    except SkillError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/{agent_id}/skills/{skill_id}", response_model=List[schemas.Skill])
def assign_skill_to_agent(agent_id: str, skill_id: str, db: Session = Depends(get_db)):
    try:
        return SkillService(db).assign_skill_to_agent(agent_id, skill_id)
    except SkillError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.delete("/{agent_id}/skills/{skill_id}", response_model=List[schemas.Skill])
def remove_skill_from_agent(agent_id: str, skill_id: str, db: Session = Depends(get_db)):
    try:
        return SkillService(db).remove_skill_from_agent(agent_id, skill_id)
    except SkillError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/{agent_id}/plugins", response_model=List[schemas.Plugin])
def get_agent_plugins(agent_id: str, db: Session = Depends(get_db)):
    try:
        return PluginService(db).get_agent_plugins(agent_id)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.put("/{agent_id}/plugins", response_model=List[schemas.Plugin])
def update_agent_plugins(agent_id: str, request: schemas.PluginIdsRequest, db: Session = Depends(get_db)):
    try:
        return PluginService(db).set_agent_plugins(agent_id, request.plugin_ids)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/{agent_id}/plugins/{plugin_id}", response_model=List[schemas.Plugin])
def assign_plugin_to_agent(agent_id: str, plugin_id: str, db: Session = Depends(get_db)):
    try:
        return PluginService(db).assign_plugin_to_agent(agent_id, plugin_id)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.delete("/{agent_id}/plugins/{plugin_id}", response_model=List[schemas.Plugin])
def remove_plugin_from_agent(agent_id: str, plugin_id: str, db: Session = Depends(get_db)):
    try:
        return PluginService(db).remove_plugin_from_agent(agent_id, plugin_id)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/{agent_id}/mcp", response_model=List[schemas.MCPServer])
def get_agent_mcp_servers(agent_id: str, db: Session = Depends(get_db)):
    try:
        return MCPService(db).get_agent_servers(agent_id)
    except MCPError as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.put("/{agent_id}/mcp", response_model=List[schemas.MCPServer])
def update_agent_mcp_servers(agent_id: str, request: schemas.MCPServerIdsRequest, db: Session = Depends(get_db)):
    try:
        return MCPService(db).set_agent_servers(agent_id, request.server_ids)
    except MCPError as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.post("/{agent_id}/mcp/{server_id}", response_model=List[schemas.MCPServer])
def assign_mcp_to_agent(agent_id: str, server_id: str, db: Session = Depends(get_db)):
    try:
        return MCPService(db).assign_agent_server(agent_id, server_id)
    except MCPError as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.delete("/{agent_id}/mcp/{server_id}", response_model=List[schemas.MCPServer])
def remove_mcp_from_agent(agent_id: str, server_id: str, db: Session = Depends(get_db)):
    try:
        return MCPService(db).remove_agent_server(agent_id, server_id)
    except MCPError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
