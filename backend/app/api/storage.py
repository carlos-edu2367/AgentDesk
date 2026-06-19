from fastapi import APIRouter
from app.storage.appdata import get_appdata_dir

router = APIRouter()

@router.get("/storage/info")
def get_storage_info():
    base_dir = get_appdata_dir()
    return {
        "appdata_path": str(base_dir),
        "database_path": str(base_dir / "database" / "agentdesk.sqlite")
    }
