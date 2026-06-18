"""Tests for memory tools."""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, MemoryModel
from app.tools.base import ToolExecutionContext
from app.tools.core.memory import MemorySearchTool, MemoryCreateTool
from app.tools.errors import ToolError


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _ctx(db):
    return ToolExecutionContext(
        execution_id="exec_test", agent_id="agent_test",
        workspace_ids=[], db=db, approval_mode="auto",
    )


def _add_memory(db, id, title, content, scope="global"):
    m = MemoryModel(
        id=id, scope=scope, scope_id=None, type="preference",
        title=title, content=content, tags=[], confidence=0.8, importance=0.7,
        source={}, usage_count=0, embedding_status="pending",
    )
    db.add(m)
    db.commit()


@pytest.mark.asyncio
async def test_memory_search_tool_text_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Prefere Python", "Usa Python para scripts")
    tool = MemorySearchTool()
    result = await tool.execute(
        {"query": "Python", "scopes": ["global"], "mode": "text", "limit": 5},
        _ctx(db),
    )
    assert result["count"] >= 1
    assert any(r["memory_id"] == "m1" for r in result["results"])


@pytest.mark.asyncio
async def test_memory_search_tool_missing_query_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    tool = MemorySearchTool()
    with pytest.raises(ToolError):
        await tool.execute({}, _ctx(db))


@pytest.mark.asyncio
async def test_memory_create_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    tool = MemoryCreateTool()
    with patch("app.memory.service.get_embedding_for_memory", AsyncMock(return_value=None)):
        result = await tool.execute(
            {
                "title": "Nova memória",
                "content": "Conteúdo da memória",
                "scope": "global",
                "type": "preference",
                "tags": ["teste"],
                "confidence": 0.8,
                "importance": 0.7,
            },
            _ctx(db),
        )
    assert result["status"] == "created"
    assert "memory_id" in result


@pytest.mark.asyncio
async def test_memory_create_tool_missing_title_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    tool = MemoryCreateTool()
    with pytest.raises(ToolError):
        await tool.execute({"content": "sem título"}, _ctx(db))


def test_memory_search_tool_capability():
    assert MemorySearchTool().capability == "memory"


def test_memory_create_tool_not_critical():
    assert MemoryCreateTool().critical is False


@pytest.mark.asyncio
async def test_memory_create_tool_invalid_scope_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    tool = MemoryCreateTool()
    with pytest.raises(ToolError):
        await tool.execute({"title": "T", "content": "C", "scope": "invalid_scope"}, _ctx(db))


@pytest.mark.asyncio
async def test_memory_create_tool_missing_content_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    tool = MemoryCreateTool()
    with pytest.raises(ToolError):
        await tool.execute({"title": "Tem título"}, _ctx(db))
