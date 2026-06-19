from fastapi import APIRouter
from app.storage.appdata import get_appdata_dir, get_db_path

router = APIRouter()

APP_VERSION = "0.1.0"


@router.get("/health")
def get_health():
    storage_ready = get_appdata_dir().exists()
    database_ready = get_db_path().exists()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "storage_ready": storage_ready,
        "database_ready": database_ready,
    }
