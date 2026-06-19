from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.domain import schemas
from app.mcp.errors import MCPError
from app.mcp.service import MCPService

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _service(db: Session) -> MCPService:
    return MCPService(db)


def _raise(exc: MCPError):
    status = 404 if exc.code == "MCP_SERVER_NOT_FOUND" else 400
    raise HTTPException(status_code=status, detail=exc.message)


@router.get("", response_model=list[schemas.MCPServer])
def list_mcp(db: Session = Depends(get_db)):
    return _service(db).list_servers()


@router.post("", response_model=schemas.MCPServer)
def create_mcp(obj_in: schemas.MCPServerCreate, db: Session = Depends(get_db)):
    try:
        return _service(db).create_server(obj_in)
    except MCPError as exc:
        _raise(exc)


@router.get("/{server_id}", response_model=schemas.MCPServer)
def get_mcp(server_id: str, db: Session = Depends(get_db)):
    try:
        return _service(db).get_server(server_id)
    except MCPError as exc:
        _raise(exc)


@router.put("/{server_id}", response_model=schemas.MCPServer)
def update_mcp(server_id: str, obj_in: schemas.MCPServerUpdate, db: Session = Depends(get_db)):
    try:
        return _service(db).update_server(server_id, obj_in)
    except MCPError as exc:
        _raise(exc)


@router.delete("/{server_id}")
def delete_mcp(server_id: str, db: Session = Depends(get_db)):
    try:
        _service(db).delete_server(server_id)
        return {"status": "deleted"}
    except MCPError as exc:
        _raise(exc)


@router.post("/{server_id}/enable", response_model=schemas.MCPServer)
def enable_mcp(server_id: str, db: Session = Depends(get_db)):
    try:
        return _service(db).enable_server(server_id)
    except MCPError as exc:
        _raise(exc)


@router.post("/{server_id}/disable", response_model=schemas.MCPServer)
def disable_mcp(server_id: str, db: Session = Depends(get_db)):
    try:
        return _service(db).disable_server(server_id)
    except MCPError as exc:
        _raise(exc)


@router.post("/{server_id}/test", response_model=schemas.MCPTestResponse)
async def test_mcp(server_id: str, db: Session = Depends(get_db)):
    try:
        status, tools, error = await _service(db).test_connection(server_id)
    except MCPError as exc:
        _raise(exc)
    return schemas.MCPTestResponse(
        server_id=server_id,
        status=status,
        tools=[schemas.MCPToolInfo.model_validate(tool) for tool in tools],
        error=schemas.MCPTestError(code=error.code, message=error.message) if error else None,
    )


@router.get("/{server_id}/tools", response_model=list[schemas.MCPToolInfo])
def get_mcp_tools(server_id: str, db: Session = Depends(get_db)):
    try:
        return [schemas.MCPToolInfo.model_validate(tool) for tool in _service(db).get_tools(server_id)]
    except MCPError as exc:
        _raise(exc)
