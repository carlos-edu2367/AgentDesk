"""Tests for embedding backfill (reembed_failed) and embedding-provider config."""
import json

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, MemoryModel, MemoryEmbeddingModel
from app.domain.schemas import MemoryCreate
from app.domain.enums import MemoryScope, MemoryType
from app.memory.service import MemoryService
from app.storage.appdata import get_embedding_config


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_reembed_backfills_failed_memories(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()

    # Create a memory while the embedding provider is unavailable -> status failed.
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        mem = await svc.create_memory(MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PROFILE,
            title="Perfil", content="Dev Python", tags=[], confidence=0.8, importance=0.7, source={},
        ))
    row = db.query(MemoryModel).filter(MemoryModel.id == mem.id).first()
    assert row.embedding_status == "failed"

    # Provider comes back -> backfill succeeds.
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=[0.1, 0.2, 0.3])):
        result = await MemoryService(db).reembed_failed()

    assert result == {"processed": 1, "succeeded": 1, "failed": 0}
    db.expire_all()
    row = db.query(MemoryModel).filter(MemoryModel.id == mem.id).first()
    assert row.embedding_status == "done"
    assert db.query(MemoryEmbeddingModel).filter(MemoryEmbeddingModel.memory_id == mem.id).first() is not None


@pytest.mark.asyncio
async def test_reembed_reports_still_failing(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        await svc.create_memory(MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PREFERENCE,
            title="x", content="y", tags=[], confidence=0.8, importance=0.7, source={},
        ))
        result = await MemoryService(db).reembed_failed()
    assert result == {"processed": 1, "succeeded": 0, "failed": 1}


@pytest.mark.asyncio
async def test_reembed_endpoint(client):
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        client.post("/api/memories", json={
            "scope": "global", "scope_id": None, "type": "preference",
            "title": "t", "content": "c", "tags": [], "confidence": 0.8, "importance": 0.7, "source": {},
        })
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=[0.5, 0.5])):
        resp = client.post("/api/memories/reembed")
    assert resp.status_code == 200
    assert resp.json()["succeeded"] == 1


def test_embedding_config_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))  # no config file written
    cfg = get_embedding_config()
    assert cfg["model"] == "nomic-embed-text"
    assert cfg["base_url"] == "http://localhost:11434"


def test_embedding_config_reads_custom_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg_dir = tmp_path / "AgentDesk" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "providers.config.json").write_text(json.dumps({
        "providers": [],
        "embedding_provider": {"type": "ollama", "model": "mxbai-embed-large", "base_url": "http://host:9999"},
    }), encoding="utf-8")

    cfg = get_embedding_config()
    assert cfg["model"] == "mxbai-embed-large"
    assert cfg["base_url"] == "http://host:9999"


def test_memory_service_uses_configured_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg_dir = tmp_path / "AgentDesk" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "providers.config.json").write_text(json.dumps({
        "embedding_provider": {"type": "ollama", "model": "custom-embed", "base_url": "http://x:1"},
    }), encoding="utf-8")

    svc = MemoryService(_make_db())
    assert svc.embedding_model == "custom-embed"
    assert svc.ollama_url == "http://x:1"
