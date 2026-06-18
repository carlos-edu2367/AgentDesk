"""Tests for memory links and deduplication."""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, MemoryModel, MemoryLinkModel, MemoryEmbeddingModel
from app.memory.links import create_link, get_links, check_duplicate
from app.memory.embeddings import vector_to_json


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _add_memory(db, id, title, content, scope="global", scope_id=None):
    m = MemoryModel(
        id=id, scope=scope, scope_id=scope_id, type="preference",
        title=title, content=content, tags=[], confidence=0.8, importance=0.7,
        source={}, usage_count=0, embedding_status="pending",
    )
    db.add(m)
    db.commit()
    return m


def _add_embedding(db, memory_id, vector):
    from app.domain.utils import generate_id
    e = MemoryEmbeddingModel(
        id=generate_id("emb"), memory_id=memory_id,
        embedding_model="nomic-embed-text",
        embedding_vector=vector_to_json(vector),
    )
    db.add(e)
    db.commit()


def test_create_link(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Titulo A", "Conteudo A")
    _add_memory(db, "m2", "Titulo B", "Conteudo B")
    link = create_link(db, "m1", "m2", "related_to", strength=0.9)
    assert link.source_memory_id == "m1"
    assert link.target_memory_id == "m2"
    assert link.relation_type == "related_to"


def test_get_links_returns_for_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Titulo A", "Conteudo A")
    _add_memory(db, "m2", "Titulo B", "Conteudo B")
    create_link(db, "m1", "m2", "supports", strength=0.8)
    links = get_links(db, "m1")
    assert len(links) == 1
    assert links[0].target_memory_id == "m2"


@pytest.mark.asyncio
async def test_check_duplicate_high_similarity(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Preferencia do usuario", "Usuario prefere respostas objetivas")
    _add_embedding(db, "m1", [1.0, 0.0, 0.0])

    mock_embed = AsyncMock(return_value=[1.0, 0.0, 0.0])
    with patch("app.memory.links.get_embedding_for_memory", mock_embed):
        result = await check_duplicate(db, "Preferencia do usuario", "Usuario prefere respostas objetivas", ["global"])
    assert result["is_duplicate"] is True
    assert result["duplicate_id"] == "m1"


@pytest.mark.asyncio
async def test_check_duplicate_no_match(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Preferencia X", "Conteudo X")
    _add_embedding(db, "m1", [1.0, 0.0, 0.0])

    mock_embed = AsyncMock(return_value=[0.0, 1.0, 0.0])
    with patch("app.memory.links.get_embedding_for_memory", mock_embed):
        result = await check_duplicate(db, "Outro assunto", "Conteudo totalmente diferente", ["global"])
    assert result["is_duplicate"] is False
