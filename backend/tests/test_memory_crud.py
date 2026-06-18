"""Tests for MemoryService CRUD operations."""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime

from app.db.models import Base, MemoryModel, MemoryEmbeddingModel
from app.domain.schemas import MemoryCreate
from app.domain.enums import MemoryScope, MemoryType
from app.memory.service import MemoryService


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_create_global_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        mem_in = MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PREFERENCE,
            title="Prefere respostas objetivas", content="Resposta direta.",
            tags=["estilo"], confidence=0.9, importance=0.8, source={}
        )
        mem = await svc.create_memory(mem_in)
    assert mem.id.startswith("memory_")
    assert mem.scope == "global"
    assert mem.scope_id is None


@pytest.mark.asyncio
async def test_create_agent_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        mem_in = MemoryCreate(
            scope=MemoryScope.AGENT, scope_id="agent_001", type=MemoryType.DECISION,
            title="Usa Python para scripts", content="O agente prefere Python.",
            tags=[], confidence=0.8, importance=0.7, source={}
        )
        mem = await svc.create_memory(mem_in)
    assert mem.scope == "agent"
    assert mem.scope_id == "agent_001"


@pytest.mark.asyncio
async def test_create_team_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        mem_in = MemoryCreate(
            scope=MemoryScope.TEAM, scope_id="team_001", type=MemoryType.WORKFLOW,
            title="Workflow do time", content="O time usa revisao em pares.",
            tags=["process"], confidence=0.9, importance=0.9, source={}
        )
        mem = await svc.create_memory(mem_in)
    assert mem.scope == "team"
    assert mem.scope_id == "team_001"


@pytest.mark.asyncio
async def test_embedding_generated_when_ollama_available(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    mock_vec = [0.1, 0.2, 0.3]
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=mock_vec)):
        svc = MemoryService(db)
        mem_in = MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PREFERENCE,
            title="Teste", content="Conteudo de teste.",
            tags=[], confidence=0.5, importance=0.5, source={}
        )
        mem = await svc.create_memory(mem_in)
    db_mem = db.query(MemoryModel).filter(MemoryModel.id == mem.id).first()
    assert db_mem.embedding_status == "done"
    emb = db.query(MemoryEmbeddingModel).filter(MemoryEmbeddingModel.memory_id == mem.id).first()
    assert emb is not None


@pytest.mark.asyncio
async def test_embedding_failure_does_not_prevent_creation(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        mem_in = MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PREFERENCE,
            title="Sem embedding", content="Conteudo.",
            tags=[], confidence=0.5, importance=0.5, source={}
        )
        mem = await svc.create_memory(mem_in)
    db_mem = db.query(MemoryModel).filter(MemoryModel.id == mem.id).first()
    assert db_mem is not None
    assert db_mem.embedding_status == "failed"


@pytest.mark.asyncio
async def test_update_memory_regenerates_embedding(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    mock_vec = [0.1, 0.2, 0.3]
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=mock_vec)):
        svc = MemoryService(db)
        mem_in = MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PREFERENCE,
            title="Original", content="Conteudo original.",
            tags=[], confidence=0.5, importance=0.5, source={}
        )
        mem = await svc.create_memory(mem_in)
        updated = await svc.update_memory(mem.id, {"content": "Novo conteudo."})
    assert updated is not None
    db_mem = db.query(MemoryModel).filter(MemoryModel.id == mem.id).first()
    assert db_mem.embedding_status == "done"


@pytest.mark.asyncio
async def test_delete_memory_soft_deletes(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        mem_in = MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PREFERENCE,
            title="Para deletar", content="Conteudo.",
            tags=[], confidence=0.5, importance=0.5, source={}
        )
        mem = await svc.create_memory(mem_in)
        await svc.delete_memory(mem.id)
    db_mem = db.query(MemoryModel).filter(MemoryModel.id == mem.id).first()
    assert db_mem.deleted_at is not None


@pytest.mark.asyncio
async def test_list_by_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        for i in range(3):
            await svc.create_memory(MemoryCreate(
                scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PREFERENCE,
                title=f"Global {i}", content=".", tags=[], confidence=0.5, importance=0.5, source={}
            ))
        await svc.create_memory(MemoryCreate(
            scope=MemoryScope.AGENT, scope_id="agent_x", type=MemoryType.DECISION,
            title="Agent only", content=".", tags=[], confidence=0.5, importance=0.5, source={}
        ))
    global_mems = svc.list_memories(scope="global")
    assert len(global_mems) == 3
    agent_mems = svc.list_memories(scope="agent", scope_id="agent_x")
    assert len(agent_mems) == 1


@pytest.mark.asyncio
async def test_list_by_type(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        svc = MemoryService(db)
        await svc.create_memory(MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.PREFERENCE,
            title="Pref", content=".", tags=[], confidence=0.5, importance=0.5, source={}
        ))
        await svc.create_memory(MemoryCreate(
            scope=MemoryScope.GLOBAL, scope_id=None, type=MemoryType.DECISION,
            title="Dec", content=".", tags=[], confidence=0.5, importance=0.5, source={}
        ))
    prefs = svc.list_memories(type="preference")
    assert len(prefs) == 1
    assert prefs[0].type == "preference"
