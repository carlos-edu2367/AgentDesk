from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.domain import schemas
from app.plugins.errors import PluginError
from app.plugins.service import PluginService

router = APIRouter(prefix="/plugins", tags=["plugins"])


def _service(db: Session) -> PluginService:
    return PluginService(db)


@router.get("", response_model=list[schemas.Plugin])
def list_plugins(db: Session = Depends(get_db)):
    return _service(db).list_plugins()


@router.post("/import", response_model=schemas.PluginImportResponse)
def import_plugin(request: schemas.PluginImportRequest, db: Session = Depends(get_db)):
    try:
        plugin = _service(db).import_plugin_folder(request.path)
        return schemas.PluginImportResponse(
            id=plugin.id,
            name=plugin.name,
            version=plugin.version,
            enabled=plugin.enabled,
            tools=[tool["name"] for tool in (plugin.tools_json or [])],
            skills=[skill["id"] for skill in (plugin.skills_json or [])],
        )
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/{plugin_id}", response_model=schemas.Plugin)
def get_plugin(plugin_id: str, db: Session = Depends(get_db)):
    try:
        return _service(db).get_plugin(plugin_id)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/{plugin_id}/enable", response_model=schemas.Plugin)
def enable_plugin(plugin_id: str, db: Session = Depends(get_db)):
    try:
        return _service(db).enable_plugin(plugin_id)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/{plugin_id}/disable", response_model=schemas.Plugin)
def disable_plugin(plugin_id: str, db: Session = Depends(get_db)):
    try:
        return _service(db).disable_plugin(plugin_id)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.delete("/{plugin_id}")
def delete_plugin(plugin_id: str, db: Session = Depends(get_db)):
    try:
        _service(db).delete_plugin(plugin_id)
        return {"status": "deleted"}
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/{plugin_id}/tools", response_model=list[schemas.PluginToolInfo])
def get_plugin_tools(plugin_id: str, db: Session = Depends(get_db)):
    try:
        return _service(db).get_plugin_tools(plugin_id)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/{plugin_id}/skills", response_model=list[schemas.Skill])
def get_plugin_skills(plugin_id: str, db: Session = Depends(get_db)):
    try:
        return _service(db).get_plugin_skills(plugin_id)
    except PluginError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
