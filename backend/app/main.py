import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from alembic.config import Config
from alembic import command

from app.db import database
from app.storage.appdata import ensure_appdata_structure
from app.tools.registry import register_core_tools
from app.api import health, storage
from app.api.routers import agents, teams, workspaces, providers, executions, skills, mcp, plugins, memories, tools, approvals, audit, logs, conversations, ollama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentdesk.startup")

def run_migrations():
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        # When packaged with PyInstaller, alembic files are extracted to AGENTDESK_BUNDLE_DIR
        bundle_dir = os.environ.get("AGENTDESK_BUNDLE_DIR", getattr(sys, "_MEIPASS", ""))
        ini_path = os.path.join(bundle_dir, "alembic.ini")
        script_location = os.path.join(bundle_dir, "alembic")
    else:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ini_path = os.path.join(current_dir, "alembic.ini")
        script_location = os.path.join(current_dir, "alembic")

    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", script_location)
    
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Migrations aplicadas com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao aplicar migrations: {e}")
        raise e

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_appdata_structure()
    logger.info("AppData structure verified/created.")

    run_migrations()

    register_core_tools()
    logger.info("Core tools registered.")

    db = database.SessionLocal()
    try:
        from app.skills.seeder import seed_base_skills
        seed_result = seed_base_skills(db)
        logger.info(f"Base skills seeded: {seed_result['seeded']}, updated: {seed_result['updated']}")

        from app.mcp.service import MCPService
        MCPService(db).list_servers()
        logger.info("Cached MCP tools registered.")
    finally:
        db.close()

    yield

app = FastAPI(title="AgentDesk API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "app://.", "file://"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(storage.router, prefix="/api", tags=["storage"])
app.include_router(agents.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")
app.include_router(providers.router, prefix="/api")
app.include_router(executions.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(mcp.router, prefix="/api")
app.include_router(plugins.router, prefix="/api")
app.include_router(memories.router, prefix="/api")
app.include_router(tools.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(ollama.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
