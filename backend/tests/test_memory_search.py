"""Tests for memory search module."""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime

from app.db.models import Base, MemoryModel, MemoryEmbeddingModel
from app.memory.search import search_text, search_semantic, search_hybrid
from app.memory.embeddings import vector_to_json


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _add_memory(db, id, scope, scope_id, title, content, tags=None, importance=0.5, confidence=0.5):
    m = MemoryModel(
        id=id, scope=scope, scope_id=scope_id, type="preference",
        title=title, content=content, tags=tags or [],
        confidence=confidence, importance=importance,
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


# --- Text search ---

def test_text_search_finds_by_title(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Relatorio objetivos", "conteudo qualquer")
    _add_memory(db, "m2", "global", None, "Outro titulo", "conteudo qualquer 2")
    results = search_text(db, "Relatorio", ["global"], limit=10)
    ids = [r.memory_id for r in results]
    assert "m1" in ids
    assert "m2" not in ids


def test_text_search_finds_by_content(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Titulo X", "resposta direta e pratica")
    results = search_text(db, "pratica", ["global"], limit=10)
    assert any(r.memory_id == "m1" for r in results)


def test_text_search_finds_by_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Titulo X", "algum conteudo", tags=["estilo", "resposta"])
    results = search_text(db, "estilo", ["global"], limit=10)
    assert any(r.memory_id == "m1" for r in results)


def test_text_search_respects_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m_global", "global", None, "Preferencia global", "conteudo")
    _add_memory(db, "m_agent", "agent", "agent_001", "Preferencia agente", "conteudo")
    results = search_text(db, "Preferencia", ["global"], limit=10)
    ids = [r.memory_id for r in results]
    assert "m_global" in ids
    assert "m_agent" not in ids


def test_text_search_does_not_return_another_agents_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "agent", "agent_001", "Memoria do agente 1", "conteudo")
    _add_memory(db, "m2", "agent", "agent_002", "Memoria do agente 2", "conteudo")
    results = search_text(db, "Memoria", ["agent:agent_001"], limit=10)
    ids = [r.memory_id for r in results]
    assert "m1" in ids
    assert "m2" not in ids


def test_text_search_excludes_soft_deleted(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    m = _add_memory(db, "m1", "global", None, "Deletada", "conteudo")
    m.deleted_at = datetime.utcnow()
    db.commit()
    results = search_text(db, "Deletada", ["global"], limit=10)
    assert results == []


# --- Semantic search ---

@pytest.mark.asyncio
async def test_semantic_search_returns_score(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Relatorio", "conteudo")
    _add_embedding(db, "m1", [1.0, 0.0, 0.0])

    mock_embed = AsyncMock(return_value=[1.0, 0.0, 0.0])
    with patch("app.memory.search.get_embedding_for_memory", mock_embed):
        results = await search_semantic(db, "relatorio", ["global"], limit=10)
    assert len(results) == 1
    assert results[0].memory_id == "m1"
    assert results[0].score > 0.9


@pytest.mark.asyncio
async def test_semantic_search_skips_no_embedding(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Sem embedding", "conteudo")
    mock_embed = AsyncMock(return_value=[1.0, 0.0, 0.0])
    with patch("app.memory.search.get_embedding_for_memory", mock_embed):
        results = await search_semantic(db, "query", ["global"], limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_when_ollama_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Titulo", "conteudo")
    _add_embedding(db, "m1", [1.0, 0.0])
    mock_embed = AsyncMock(return_value=None)
    with patch("app.memory.search.get_embedding_for_memory", mock_embed):
        results = await search_semantic(db, "query", ["global"], limit=10)
    assert results == []


# --- Hybrid search ---

@pytest.mark.asyncio
async def test_hybrid_search_combines_results(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Relatorio objetivo", "preferencias do usuario")
    _add_embedding(db, "m1", [1.0, 0.0])

    mock_embed = AsyncMock(return_value=[1.0, 0.0])
    with patch("app.memory.search.get_embedding_for_memory", mock_embed):
        results = await search_hybrid(db, "Relatorio", ["global"], limit=10)
    assert any(r.memory_id == "m1" for r in results)


# --- Tokenized text search (natural-language queries) ---

def test_text_search_matches_keywords_in_question(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Cor favorita do usuario", "O usuario gosta de azul")
    # Whole-string substring would never match this question; tokens should.
    results = search_text(db, "qual a minha cor favorita?", ["global"], limit=10)
    assert any(r.memory_id == "m1" for r in results)


def test_text_search_ignores_stopwords_only_query(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Projeto X", "detalhes do projeto")
    # Query made only of stopwords/short tokens shouldn't spuriously match.
    results = search_text(db, "o que e", ["global"], limit=10)
    assert results == []


# --- Pinned recall ---

def test_get_pinned_results_returns_high_importance_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    from app.memory.service import MemoryService
    # profile/preference with high importance -> pinned
    db.add(MemoryModel(
        id="p1", scope="global", scope_id=None, type="profile",
        title="Nome", content="O usuario se chama Carlos", tags=[],
        confidence=0.9, importance=0.9, source={}, usage_count=0,
        embedding_status="pending",
    ))
    # low importance -> excluded
    db.add(MemoryModel(
        id="p2", scope="global", scope_id=None, type="preference",
        title="Trivial", content="algo", tags=[],
        confidence=0.5, importance=0.2, source={}, usage_count=0,
        embedding_status="pending",
    ))
    # non-pinned type -> excluded
    db.add(MemoryModel(
        id="p3", scope="global", scope_id=None, type="lesson",
        title="Licao", content="algo", tags=[],
        confidence=0.9, importance=0.9, source={}, usage_count=0,
        embedding_status="pending",
    ))
    db.commit()

    pinned = MemoryService(db).get_pinned_results(["global"], limit=3)
    ids = {r.memory_id for r in pinned}
    assert ids == {"p1"}
