import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient


# ── Ensure APPDATA is isolated for every test ──
@pytest.fixture(autouse=True)
def mock_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


# ── Ensure core tools are registered once per session ──
@pytest.fixture(autouse=True, scope="session")
def _register_tools():
    from app.tools.registry import tool_registry, register_core_tools
    if not tool_registry.exists("filesystem.list"):
        register_core_tools()


# ── In-memory database for API tests via the client fixture ──
# This avoids module-level engine singleton conflicts when running the full suite.
@pytest.fixture
def client(mock_appdata, monkeypatch):
    from app.main import app
    from app.db.database import get_db
    from app.db.models import Base
    from app.storage.appdata import ensure_appdata_structure

    ensure_appdata_structure()

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.db.database.SessionLocal", TestingSessionLocal)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
