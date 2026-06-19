import os
import json
from pathlib import Path
from typing import Dict, Any

def get_appdata_dir() -> Path:
    # Use APPDATA env var or fallback to ~/.agentdesk for testing
    appdata = os.getenv("APPDATA")
    if appdata:
        base_dir = Path(appdata) / "AgentDesk"
    else:
        base_dir = Path.home() / ".agentdesk"
    return base_dir

def ensure_appdata_structure():
    base_dir = get_appdata_dir()
    directories = [
        base_dir / "config",
        base_dir / "database",
        base_dir / "database" / "migrations",
        base_dir / "memories" / "global",
        base_dir / "memories" / "agents",
        base_dir / "memories" / "teams",
        base_dir / "memories" / "workspaces",
        base_dir / "skills" / "installed",
        base_dir / "skills" / "custom",
        base_dir / "plugins" / "installed",
        base_dir / "plugins" / "custom",
        base_dir / "logs" / "executions",
        base_dir / "logs" / "audit",
        base_dir / "exports" / "reports",
        base_dir / "exports" / "backups",
        base_dir / "temp" / "executions",
        base_dir / "temp" / "downloads",
        base_dir / "workspaces"
    ]
    
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)
        
    # Default configs
    _ensure_config_file(base_dir / "config" / "app.config.json", {
        "app_name": "AgentDesk",
        "version": "0.1.0",
        "theme": "system",
        "default_approval_mode": "manual",
        "default_workspace_policy": "user_selected",
        "telemetry": False,
        "logs_retention_days": 90,
        "audit_retention_days": 365,
        "keep_failed_executions": True
    })
    
    _ensure_config_file(base_dir / "config" / "providers.config.json", {
        "providers": [],
        "embedding_provider": {
            "type": "ollama",
            "model": "nomic-embed-text",
            "base_url": "http://localhost:11434"
        }
    })
    
    _ensure_config_file(base_dir / "config" / "mcp.config.json", {
        "servers": []
    })
    
    _ensure_config_file(base_dir / "config" / "permissions.config.json", {
        "default_capabilities": [],
        "critical_tools": [
            "filesystem.write",
            "filesystem.delete",
            "filesystem.move",
            "terminal.exec",
            "http.request",
            "memory.delete",
            "plugin.install",
            "mcp.call"
        ]
    })
    
    _ensure_config_file(base_dir / "workspaces" / "registry.json", {})

def _ensure_config_file(path: Path, default_data: Dict[str, Any]):
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2, ensure_ascii=False)

def get_db_path() -> Path:
    return get_appdata_dir() / "database" / "agentdesk.sqlite"
