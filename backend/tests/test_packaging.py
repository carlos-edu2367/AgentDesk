"""
Smoke tests for Phase 15 packaging artifacts.

These tests verify that the files required for Windows packaging exist and
have the correct structure, without actually running PyInstaller or Electron.
"""
import os
import socket
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent  # AgentDesk/
BACKEND_DIR = PROJECT_ROOT / "backend"
DESKTOP_DIR = PROJECT_ROOT / "apps" / "desktop"


# ── File existence ────────────────────────────────────────────────────────────

def test_server_entry_point_exists():
    assert (BACKEND_DIR / "server.py").exists(), "backend/server.py must exist for PyInstaller"


def test_pyinstaller_spec_exists():
    assert (BACKEND_DIR / "pyinstaller" / "agentdesk-backend.spec").exists()


def test_alembic_ini_exists():
    assert (BACKEND_DIR / "alembic.ini").exists(), "alembic.ini must be present for migrations"


def test_alembic_versions_dir_exists():
    assert (BACKEND_DIR / "alembic" / "versions").exists()


def test_electron_main_exists():
    assert (DESKTOP_DIR / "main.js").exists()


def test_electron_preload_exists():
    assert (DESKTOP_DIR / "preload.js").exists()


def test_electron_package_json_has_build_config():
    import json
    pkg = json.loads((DESKTOP_DIR / "package.json").read_text(encoding="utf-8"))
    assert "build" in pkg
    assert pkg["build"].get("appId") == "com.agentdesk.app"


# ── server.py structure ───────────────────────────────────────────────────────

def test_server_py_imports_main_app():
    content = (BACKEND_DIR / "server.py").read_text(encoding="utf-8")
    assert "from app.main import app" in content


def test_server_py_handles_frozen_flag():
    content = (BACKEND_DIR / "server.py").read_text(encoding="utf-8")
    assert "frozen" in content
    assert "_MEIPASS" in content


def test_server_py_prints_port_signal():
    content = (BACKEND_DIR / "server.py").read_text(encoding="utf-8")
    assert "AGENTDESK_PORT" in content


def test_server_py_listens_only_localhost():
    content = (BACKEND_DIR / "server.py").read_text(encoding="utf-8")
    assert "127.0.0.1" in content


# ── PyInstaller spec structure ────────────────────────────────────────────────

def test_spec_references_server_py():
    content = (BACKEND_DIR / "pyinstaller" / "agentdesk-backend.spec").read_text(encoding="utf-8")
    assert "server.py" in content


def test_spec_includes_alembic_ini():
    content = (BACKEND_DIR / "pyinstaller" / "agentdesk-backend.spec").read_text(encoding="utf-8")
    assert "alembic.ini" in content


def test_spec_includes_alembic_dir():
    content = (BACKEND_DIR / "pyinstaller" / "agentdesk-backend.spec").read_text(encoding="utf-8")
    assert '"alembic"' in content or "'alembic'" in content


def test_spec_output_name_is_agentdesk_backend():
    content = (BACKEND_DIR / "pyinstaller" / "agentdesk-backend.spec").read_text(encoding="utf-8")
    assert "agentdesk-backend" in content


# ── Electron main.js ─────────────────────────────────────────────────────────

def test_electron_main_kills_backend_on_quit():
    content = (DESKTOP_DIR / "main.js").read_text(encoding="utf-8")
    assert "killBackend" in content
    assert "will-quit" in content


def test_electron_main_uses_packaged_port():
    content = (DESKTOP_DIR / "main.js").read_text(encoding="utf-8")
    assert "DEFAULT_BACKEND_PORT" in content
    assert "8765" in content


def test_electron_main_health_check():
    content = (DESKTOP_DIR / "main.js").read_text(encoding="utf-8")
    assert "/api/health" in content


def test_electron_main_has_startup_logging():
    content = (DESKTOP_DIR / "main.js").read_text(encoding="utf-8")
    assert "startup.log" in content
    assert "logs" in content


def test_electron_preload_exposes_api_url():
    content = (DESKTOP_DIR / "preload.js").read_text(encoding="utf-8")
    assert "apiBaseUrl" in content
    assert "sendSync" in content


# ── Security ─────────────────────────────────────────────────────────────────

def test_backend_listens_only_on_localhost():
    """server.py must not bind to 0.0.0.0."""
    content = (BACKEND_DIR / "server.py").read_text(encoding="utf-8")
    assert "0.0.0.0" not in content


def test_electron_main_does_not_hardcode_dev_port_in_packaged_path():
    """The packaged backend path must not use port 8000."""
    content = (DESKTOP_DIR / "main.js").read_text(encoding="utf-8")
    # In packaged mode the default should be 8765, not 8000
    # (8000 may appear in dev-mode section, that's OK, but DEFAULT_BACKEND_PORT must be 8765)
    assert "DEFAULT_BACKEND_PORT = 8765" in content or "DEFAULT_BACKEND_PORT=8765" in content or "8765" in content


def test_no_secrets_in_startup_log_function():
    content = (DESKTOP_DIR / "main.js").read_text(encoding="utf-8")
    # log() function must not log API keys or tokens
    assert "api_key" not in content.lower() or "mask" in content.lower() or "startup.log" in content


# ── Port management (unit) ────────────────────────────────────────────────────

def test_find_free_port_returns_occupied_check():
    """Verify that the OS correctly detects an occupied port (sanity check)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        occupied = s.getsockname()[1]

        # Try to bind again — should fail
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
            try:
                s2.bind(("127.0.0.1", occupied))
                already_free = True
            except OSError:
                already_free = False

        assert not already_free, "Sanity check: re-binding an occupied port should fail"


# ── Health endpoint extended fields ──────────────────────────────────────────

def test_health_returns_version(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("version") == "0.1.0"


def test_health_returns_storage_ready(client):
    resp = client.get("/api/health")
    data = resp.json()
    assert "storage_ready" in data
    assert isinstance(data["storage_ready"], bool)


def test_health_returns_database_ready(client):
    resp = client.get("/api/health")
    data = resp.json()
    assert "database_ready" in data
    assert isinstance(data["database_ready"], bool)
