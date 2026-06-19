# Phase 9 — Memory System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a local-first memory system for AgentDesk with scoped memories, Ollama embeddings, hybrid search, and Agent Runtime injection.

**Architecture:** SQLite stores memory metadata + JSON-serialized embedding vectors. A `MemoryService` orchestrates CRUD, embedding generation (via existing OllamaProvider), and text/semantic/hybrid search. The Agent Runtime calls MemoryService before each model invocation to inject relevant memories into the system prompt.

**Tech Stack:** Python + SQLAlchemy + FastAPI (backend); React + TypeScript (frontend); Ollama `nomic-embed-text` for embeddings; cosine similarity computed in Python.

---

## File Map

**Create:**
- `backend/app/memory/__init__.py`
- `backend/app/memory/embeddings.py` — embedding generation + cosine similarity
- `backend/app/memory/search.py` — text, semantic, hybrid search
- `backend/app/memory/links.py` — link management + deduplication check
- `backend/app/memory/service.py` — main MemoryService orchestrator
- `backend/app/tools/core/memory.py` — MemorySearchTool + MemoryCreateTool
- `backend/alembic/versions/c9f1a2b3d4e5_add_memory_tables.py` — migration
- `backend/tests/test_memory_crud.py`
- `backend/tests/test_memory_embeddings.py`
- `backend/tests/test_memory_search.py`
- `backend/tests/test_memory_links.py`
- `backend/tests/test_memory_runtime.py`
- `backend/tests/test_memory_tools.py`
- `apps/frontend/src/api/memories.ts`
- `apps/frontend/src/views/Memory.tsx`
- `apps/frontend/src/__tests__/Memory.test.tsx`

**Modify:**
- `backend/app/db/models.py` — add `MemoryEmbeddingModel`, `MemoryLinkModel`, `MemoryUsageModel`; add `deleted_at` + `embedding_status` to `MemoryModel`
- `backend/app/domain/schemas.py` — add `MemoryLinkCreate`, `MemoryLink`, `MemorySearchRequest`, `MemorySearchResult`, `MemorySearchResponse`
- `backend/app/domain/enums.py` — add memory EventType values
- `backend/app/db/repositories/registry.py` — add repos for new models
- `backend/app/api/routers/memories.py` — add search, links, filtering, soft-delete
- `backend/app/tools/capabilities.py` — add `memory` capability
- `backend/app/tools/registry.py` — register memory tools in `register_core_tools()`
- `backend/app/runtime/prompt_builder.py` — add `_get_memory_context()` method
- `backend/app/runtime/agent_runtime.py` — memory lookup before model call
- `apps/frontend/src/App.tsx` — add Memory route
- `apps/frontend/src/components/Sidebar.tsx` — add Memory nav item
- `apps/frontend/src/views/ExecutionDetail.tsx` — add memory event labels
- `apps/frontend/src/types/domain.ts` — add Memory types

---

## Task 1: Update DB Models

**Files:**
- Modify: `backend/app/db/models.py`

- [ ] **Step 1: Add columns to MemoryModel and new model classes**

Open `backend/app/db/models.py` and make these changes:

Add to the `MemoryModel` class (after `usage_count`):
```python
    deleted_at = Column(DateTime, nullable=True)
    embedding_status = Column(String, default="pending")  # pending, done, failed
```

Add three new model classes after `MemoryModel`:
```python
class MemoryEmbeddingModel(Base):
    __tablename__ = "memory_embeddings"
    id = Column(String, primary_key=True)
    memory_id = Column(String, ForeignKey("memories.id"))
    embedding_model = Column(String)
    embedding_vector = Column(Text)  # JSON-serialized list[float]
    created_at = Column(DateTime, default=datetime.utcnow)

class MemoryLinkModel(Base):
    __tablename__ = "memory_links"
    id = Column(String, primary_key=True)
    source_memory_id = Column(String, ForeignKey("memories.id"))
    target_memory_id = Column(String, ForeignKey("memories.id"))
    relation_type = Column(String)  # related_to, contradicts, updates, supports, belongs_to_project, derived_from
    strength = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class MemoryUsageModel(Base):
    __tablename__ = "memory_usage"
    id = Column(String, primary_key=True)
    memory_id = Column(String, ForeignKey("memories.id"))
    execution_id = Column(String)
    agent_id = Column(String)
    used_at = Column(DateTime, default=datetime.utcnow)
    score = Column(Float, default=0.0)
```

- [ ] **Step 2: Verify models load without error**

```bash
cd backend && python -c "from app.db.models import MemoryModel, MemoryEmbeddingModel, MemoryLinkModel, MemoryUsageModel; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/db/models.py
git commit -m "feat(memory): add MemoryEmbedding, MemoryLink, MemoryUsage models"
```

---

## Task 2: DB Migration

**Files:**
- Create: `backend/alembic/versions/c9f1a2b3d4e5_add_memory_tables.py`

- [ ] **Step 1: Create migration file**

Create `backend/alembic/versions/c9f1a2b3d4e5_add_memory_tables.py`:

```python
"""add memory tables

Revision ID: c9f1a2b3d4e5
Revises: 8f3a2d1b4c9e
Create Date: 2026-06-18 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c9f1a2b3d4e5'
down_revision: Union[str, None] = '8f3a2d1b4c9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('memories', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('memories', sa.Column('embedding_status', sa.String(), nullable=True, server_default='pending'))

    op.create_table('memory_embeddings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('memory_id', sa.String(), nullable=True),
        sa.Column('embedding_model', sa.String(), nullable=True),
        sa.Column('embedding_vector', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['memory_id'], ['memories.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('memory_links',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('source_memory_id', sa.String(), nullable=True),
        sa.Column('target_memory_id', sa.String(), nullable=True),
        sa.Column('relation_type', sa.String(), nullable=True),
        sa.Column('strength', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['source_memory_id'], ['memories.id']),
        sa.ForeignKeyConstraint(['target_memory_id'], ['memories.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('memory_usage',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('memory_id', sa.String(), nullable=True),
        sa.Column('execution_id', sa.String(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['memory_id'], ['memories.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('memory_usage')
    op.drop_table('memory_links')
    op.drop_table('memory_embeddings')
    op.drop_column('memories', 'embedding_status')
    op.drop_column('memories', 'deleted_at')
```

- [ ] **Step 2: Verify previous migration exists** 

```bash
ls backend/alembic/versions/
```
Expected: `8f3a2d1b4c9e_add_execution_approvals.py` present (matches `down_revision`)

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/c9f1a2b3d4e5_add_memory_tables.py
git commit -m "feat(memory): alembic migration for memory_embeddings, memory_links, memory_usage"
```

---

## Task 3: Schemas + Enums

**Files:**
- Modify: `backend/app/domain/enums.py`
- Modify: `backend/app/domain/schemas.py`

- [ ] **Step 1: Add memory EventType values to enums.py**

In `backend/app/domain/enums.py`, add these values to the `EventType` enum (after `TERMINAL_TIMEOUT`):

```python
    MEMORY_LOOKUP = "memory_lookup"
    MEMORY_LOOKUP_RESULT = "memory_lookup_result"
    MEMORY_CREATED = "memory_created"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_deleted"
    MEMORY_EMBEDDING_GENERATED = "memory_embedding_generated"
    MEMORY_EMBEDDING_FAILED = "memory_embedding_failed"
    MEMORY_USAGE_RECORDED = "memory_usage_recorded"
```

Note: `MEMORY_LOOKUP` and `MEMORY_WRITE` already exist in the enum — check and remove duplicates. Remove `MEMORY_WRITE` (unused) and keep `MEMORY_LOOKUP`. Add the new ones.

- [ ] **Step 2: Add new schemas to schemas.py**

At the end of `backend/app/domain/schemas.py`, add:

```python
class MemoryLinkCreate(BaseModel):
    target_memory_id: str
    relation_type: str  # related_to, contradicts, updates, supports, belongs_to_project, derived_from
    strength: float = 1.0

class MemoryLink(MemoryLinkCreate):
    id: str
    source_memory_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class MemorySearchRequest(BaseModel):
    query: str
    scopes: List[str] = Field(default_factory=lambda: ["global"])
    mode: str = "hybrid"  # text, semantic, hybrid
    limit: int = 10

class MemorySearchResult(BaseModel):
    memory_id: str
    score: float
    scope: str
    scope_id: Optional[str]
    type: str
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    confidence: float
    importance: float
    has_embedding: bool

class MemorySearchResponse(BaseModel):
    results: List[MemorySearchResult]
```

Also update the existing `Memory` schema to include the new fields:

```python
class Memory(MemoryBase):
    id: str
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    deleted_at: Optional[datetime] = None
    embedding_status: str = "pending"
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 3: Verify schemas import**

```bash
cd backend && python -c "from app.domain.schemas import MemoryLinkCreate, MemorySearchRequest, MemorySearchResponse, MemorySearchResult; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/domain/enums.py backend/app/domain/schemas.py
git commit -m "feat(memory): add memory schemas and EventType values"
```

---

## Task 4: Repository Registry Update

**Files:**
- Modify: `backend/app/db/repositories/registry.py`

- [ ] **Step 1: Add repos for new models**

In `backend/app/db/repositories/registry.py`, add after the existing repos:

```python
from app.domain.schemas import MemoryLinkCreate, MemoryLink

memory_embedding_repo = BaseRepository[models.MemoryEmbeddingModel, object, object](models.MemoryEmbeddingModel)
memory_link_repo = BaseRepository[models.MemoryLinkModel, MemoryLinkCreate, MemoryLinkCreate](models.MemoryLinkModel)
memory_usage_repo = BaseRepository[models.MemoryUsageModel, object, object](models.MemoryUsageModel)
```

Since `MemoryLinkCreate` and similar don't perfectly map to the ORM constructor (which includes `source_memory_id`), the memory service will use direct ORM objects instead of going through the BaseRepository for these. The repos above are still useful for queries.

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.db.repositories.registry import memory_embedding_repo, memory_link_repo, memory_usage_repo; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/db/repositories/registry.py
git commit -m "feat(memory): add memory embedding/link/usage repos"
```

---

## Task 5: Memory Embeddings Module

**Files:**
- Create: `backend/app/memory/__init__.py`
- Create: `backend/app/memory/embeddings.py`

- [ ] **Step 1: Write failing test first**

Create `backend/tests/test_memory_embeddings.py`:

```python
"""Tests for memory embeddings module."""
import json
import math
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.memory.embeddings import cosine_similarity, vector_to_json, json_to_vector, get_embedding_for_memory


def test_cosine_similarity_identical():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_zero_vector():
    a = [0.0, 0.0]
    b = [1.0, 0.0]
    assert cosine_similarity(a, b) == 0.0


def test_vector_roundtrip():
    vec = [0.1, 0.2, 0.3, -0.5]
    assert json_to_vector(vector_to_json(vec)) == vec


@pytest.mark.asyncio
async def test_get_embedding_for_memory_success():
    mock_embedding = [0.1, 0.2, 0.3]
    with patch("app.memory.embeddings.httpx.AsyncClient") as mock_client_cls:
        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [mock_embedding]}
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await get_embedding_for_memory("test text")
        assert result == mock_embedding


@pytest.mark.asyncio
async def test_get_embedding_for_memory_failure_returns_none():
    with patch("app.memory.embeddings.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value = mock_client

        result = await get_embedding_for_memory("test text")
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_memory_embeddings.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'app.memory'`

- [ ] **Step 3: Create the module**

Create `backend/app/memory/__init__.py` (empty):
```python
```

Create `backend/app/memory/embeddings.py`:
```python
import json
import math
from typing import List, Optional

import httpx

EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 if either is zero-length."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def vector_to_json(vector: List[float]) -> str:
    return json.dumps(vector)


def json_to_vector(data: str) -> List[float]:
    return json.loads(data)


async def get_embedding_for_memory(
    text: str,
    model: str = EMBEDDING_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> Optional[List[float]]:
    """Fetch an embedding from Ollama. Returns None if Ollama is unavailable."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/api/embed",
                json={"model": model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            return embeddings[0] if embeddings else None
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_memory_embeddings.py -v
```
Expected: all 5 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/__init__.py backend/app/memory/embeddings.py backend/tests/test_memory_embeddings.py
git commit -m "feat(memory): embeddings module with cosine similarity"
```

---

## Task 6: Memory Search Module

**Files:**
- Create: `backend/app/memory/search.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_memory_search.py`:

```python
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
    _add_memory(db, "m1", "global", None, "Relatório objetivos", "conteúdo qualquer")
    _add_memory(db, "m2", "global", None, "Outro título", "conteúdo qualquer 2")
    results = search_text(db, "Relatório", ["global"], limit=10)
    ids = [r.memory_id for r in results]
    assert "m1" in ids
    assert "m2" not in ids


def test_text_search_finds_by_content(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Título X", "resposta direta e prática")
    results = search_text(db, "prática", ["global"], limit=10)
    assert any(r.memory_id == "m1" for r in results)


def test_text_search_finds_by_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Título X", "algum conteúdo", tags=["estilo", "resposta"])
    results = search_text(db, "estilo", ["global"], limit=10)
    assert any(r.memory_id == "m1" for r in results)


def test_text_search_respects_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m_global", "global", None, "Preferência global", "conteúdo")
    _add_memory(db, "m_agent", "agent", "agent_001", "Preferência agente", "conteúdo")
    results = search_text(db, "Preferência", ["global"], limit=10)
    ids = [r.memory_id for r in results]
    assert "m_global" in ids
    assert "m_agent" not in ids


def test_text_search_does_not_return_another_agents_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "agent", "agent_001", "Memória do agente 1", "conteúdo")
    _add_memory(db, "m2", "agent", "agent_002", "Memória do agente 2", "conteúdo")
    results = search_text(db, "Memória", ["agent:agent_001"], limit=10)
    ids = [r.memory_id for r in results]
    assert "m1" in ids
    assert "m2" not in ids


# --- Semantic search ---

@pytest.mark.asyncio
async def test_semantic_search_returns_score(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Relatório", "conteúdo")
    _add_embedding(db, "m1", [1.0, 0.0, 0.0])

    mock_embed = AsyncMock(return_value=[1.0, 0.0, 0.0])
    with patch("app.memory.search.get_embedding_for_memory", mock_embed):
        results = await search_semantic(db, "relatório", ["global"], limit=10)
    assert len(results) == 1
    assert results[0].memory_id == "m1"
    assert results[0].score > 0.9


@pytest.mark.asyncio
async def test_semantic_search_skips_no_embedding(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Sem embedding", "conteúdo")
    mock_embed = AsyncMock(return_value=[1.0, 0.0, 0.0])
    with patch("app.memory.search.get_embedding_for_memory", mock_embed):
        results = await search_semantic(db, "query", ["global"], limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_when_ollama_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "global", None, "Título", "conteúdo")
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
    _add_memory(db, "m1", "global", None, "Relatório objetivo", "preferências do usuário")
    _add_embedding(db, "m1", [1.0, 0.0])

    mock_embed = AsyncMock(return_value=[1.0, 0.0])
    with patch("app.memory.search.get_embedding_for_memory", mock_embed):
        results = await search_hybrid(db, "Relatório", ["global"], limit=10)
    assert any(r.memory_id == "m1" for r in results)


def test_text_search_excludes_soft_deleted(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    m = _add_memory(db, "m1", "global", None, "Deletada", "conteúdo")
    m.deleted_at = datetime.utcnow()
    db.commit()
    results = search_text(db, "Deletada", ["global"], limit=10)
    assert results == []
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd backend && python -m pytest tests/test_memory_search.py -v 2>&1 | head -10
```
Expected: `ModuleNotFoundError: No module named 'app.memory.search'`

- [ ] **Step 3: Create search.py**

Create `backend/app/memory/search.py`:

```python
from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import MemoryModel, MemoryEmbeddingModel
from app.domain.schemas import MemorySearchResult
from app.memory.embeddings import cosine_similarity, get_embedding_for_memory, json_to_vector


def _parse_scopes(scopes: List[str]) -> List[tuple]:
    """Convert ["global", "agent:agent_001"] -> [("global", None), ("agent", "agent_001")]"""
    parsed = []
    for s in scopes:
        if ':' in s:
            scope_name, scope_id = s.split(':', 1)
            parsed.append((scope_name, scope_id))
        else:
            parsed.append((s, None))
    return parsed


def _apply_scope_filter(query, scopes: List[str]):
    parsed = _parse_scopes(scopes)
    conditions = []
    for scope_name, scope_id in parsed:
        if scope_id is None:
            conditions.append(
                and_(MemoryModel.scope == scope_name, MemoryModel.scope_id == None)
            )
        else:
            conditions.append(
                and_(MemoryModel.scope == scope_name, MemoryModel.scope_id == scope_id)
            )
    if conditions:
        query = query.filter(or_(*conditions))
    return query


def _model_to_result(m: MemoryModel, score: float, has_embedding: bool) -> MemorySearchResult:
    tags = m.tags if isinstance(m.tags, list) else (json.loads(m.tags) if m.tags else [])
    return MemorySearchResult(
        memory_id=m.id,
        score=score,
        scope=m.scope,
        scope_id=m.scope_id,
        type=m.type,
        title=m.title,
        content=m.content,
        tags=tags,
        confidence=m.confidence or 0.5,
        importance=m.importance or 0.5,
        has_embedding=has_embedding,
    )


def search_text(db: Session, query: str, scopes: List[str], limit: int = 10) -> List[MemorySearchResult]:
    """Full-text search across title, content, tags. Returns scored results."""
    q = db.query(MemoryModel).filter(MemoryModel.deleted_at == None)
    q = _apply_scope_filter(q, scopes)
    memories = q.all()

    query_lower = query.lower()
    results = []
    for m in memories:
        tags = m.tags if isinstance(m.tags, list) else (json.loads(m.tags) if m.tags else [])
        tags_str = " ".join(tags).lower()
        title_lower = (m.title or "").lower()
        content_lower = (m.content or "").lower()

        score = 0.0
        if query_lower in title_lower:
            score = max(score, 0.8)
        if query_lower in content_lower:
            score = max(score, 0.5)
        if query_lower in tags_str:
            score = max(score, 0.4)

        if score > 0.0:
            results.append(_model_to_result(m, score, m.embedding_status == "done"))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


async def search_semantic(
    db: Session, query: str, scopes: List[str], limit: int = 10,
    ollama_url: str = "http://localhost:11434",
) -> List[MemorySearchResult]:
    """Semantic search using stored embeddings and cosine similarity."""
    query_embedding = await get_embedding_for_memory(query, base_url=ollama_url)
    if query_embedding is None:
        return []

    q = db.query(MemoryModel, MemoryEmbeddingModel).join(
        MemoryEmbeddingModel, MemoryModel.id == MemoryEmbeddingModel.memory_id
    ).filter(MemoryModel.deleted_at == None)
    q = _apply_scope_filter(q, scopes)
    rows = q.all()

    results = []
    for memory, embedding in rows:
        try:
            vec = json_to_vector(embedding.embedding_vector)
            sim = cosine_similarity(query_embedding, vec)
        except Exception:
            continue
        results.append(_model_to_result(memory, sim, True))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


async def search_hybrid(
    db: Session, query: str, scopes: List[str], limit: int = 10,
    ollama_url: str = "http://localhost:11434",
) -> List[MemorySearchResult]:
    """Hybrid search combining text and semantic scores."""
    text_results = search_text(db, query, scopes, limit=limit * 2)
    semantic_results = await search_semantic(db, query, scopes, limit=limit * 2, ollama_url=ollama_url)

    scores: dict[str, float] = {}

    for r in text_results:
        scores[r.memory_id] = scores.get(r.memory_id, 0.0) + 0.4 * r.score

    for r in semantic_results:
        scores[r.memory_id] = scores.get(r.memory_id, 0.0) + 0.6 * r.score

    all_memories: dict[str, MemorySearchResult] = {}
    for r in text_results + semantic_results:
        if r.memory_id not in all_memories:
            all_memories[r.memory_id] = r

    final = []
    for mem_id, score in scores.items():
        r = all_memories[mem_id]
        boost = 0.7 + 0.15 * r.importance + 0.15 * r.confidence
        final_score = score * boost
        final.append(MemorySearchResult(
            memory_id=r.memory_id, score=round(final_score, 4),
            scope=r.scope, scope_id=r.scope_id, type=r.type,
            title=r.title, content=r.content, tags=r.tags,
            confidence=r.confidence, importance=r.importance,
            has_embedding=r.has_embedding,
        ))

    final.sort(key=lambda r: r.score, reverse=True)
    return final[:limit]
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_memory_search.py -v
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/search.py backend/tests/test_memory_search.py
git commit -m "feat(memory): text, semantic, and hybrid search"
```

---

## Task 7: Memory Links Module

**Files:**
- Create: `backend/app/memory/links.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_memory_links.py`:

```python
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
    _add_memory(db, "m1", "Título A", "Conteúdo A")
    _add_memory(db, "m2", "Título B", "Conteúdo B")
    link = create_link(db, "m1", "m2", "related_to", strength=0.9)
    assert link.source_memory_id == "m1"
    assert link.target_memory_id == "m2"
    assert link.relation_type == "related_to"


def test_get_links_returns_for_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Título A", "Conteúdo A")
    _add_memory(db, "m2", "Título B", "Conteúdo B")
    create_link(db, "m1", "m2", "supports", strength=0.8)
    links = get_links(db, "m1")
    assert len(links) == 1
    assert links[0].target_memory_id == "m2"


@pytest.mark.asyncio
async def test_check_duplicate_high_similarity(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Preferência do usuário", "Usuário prefere respostas objetivas")
    _add_embedding(db, "m1", [1.0, 0.0, 0.0])

    mock_embed = AsyncMock(return_value=[1.0, 0.0, 0.0])
    with patch("app.memory.links.get_embedding_for_memory", mock_embed):
        result = await check_duplicate(db, "Preferência do usuário", "Usuário prefere respostas objetivas", ["global"])
    assert result["is_duplicate"] is True
    assert result["duplicate_id"] == "m1"


@pytest.mark.asyncio
async def test_check_duplicate_no_match(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Preferência X", "Conteúdo X")
    _add_embedding(db, "m1", [1.0, 0.0, 0.0])

    mock_embed = AsyncMock(return_value=[0.0, 1.0, 0.0])
    with patch("app.memory.links.get_embedding_for_memory", mock_embed):
        result = await check_duplicate(db, "Outro assunto", "Conteúdo totalmente diferente", ["global"])
    assert result["is_duplicate"] is False
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd backend && python -m pytest tests/test_memory_links.py -v 2>&1 | head -10
```
Expected: `ModuleNotFoundError: No module named 'app.memory.links'`

- [ ] **Step 3: Create links.py**

Create `backend/app/memory/links.py`:

```python
from __future__ import annotations

from typing import Dict, List, Any

from sqlalchemy.orm import Session

from app.db.models import MemoryLinkModel, MemoryEmbeddingModel, MemoryModel
from app.domain.utils import generate_id
from app.memory.embeddings import cosine_similarity, get_embedding_for_memory, json_to_vector
from app.memory.search import _apply_scope_filter

DUPLICATE_THRESHOLD = 0.90
RELATED_THRESHOLD = 0.75


def create_link(
    db: Session,
    source_memory_id: str,
    target_memory_id: str,
    relation_type: str,
    strength: float = 1.0,
) -> MemoryLinkModel:
    link = MemoryLinkModel(
        id=generate_id("link"),
        source_memory_id=source_memory_id,
        target_memory_id=target_memory_id,
        relation_type=relation_type,
        strength=strength,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_links(db: Session, memory_id: str) -> List[MemoryLinkModel]:
    return db.query(MemoryLinkModel).filter(
        (MemoryLinkModel.source_memory_id == memory_id) |
        (MemoryLinkModel.target_memory_id == memory_id)
    ).all()


async def check_duplicate(
    db: Session,
    title: str,
    content: str,
    scopes: List[str],
    ollama_url: str = "http://localhost:11434",
) -> Dict[str, Any]:
    """
    Check if a similar memory already exists.
    Returns {"is_duplicate": bool, "duplicate_id": str|None, "related_ids": list[str]}
    """
    query_text = f"{title} {content}"
    query_embedding = await get_embedding_for_memory(query_text, base_url=ollama_url)
    if query_embedding is None:
        return {"is_duplicate": False, "duplicate_id": None, "related_ids": []}

    q = db.query(MemoryModel, MemoryEmbeddingModel).join(
        MemoryEmbeddingModel, MemoryModel.id == MemoryEmbeddingModel.memory_id
    ).filter(MemoryModel.deleted_at == None)
    q = _apply_scope_filter(q, scopes)
    rows = q.all()

    duplicate_id = None
    related_ids = []

    for memory, embedding in rows:
        try:
            vec = json_to_vector(embedding.embedding_vector)
            sim = cosine_similarity(query_embedding, vec)
        except Exception:
            continue

        if sim >= DUPLICATE_THRESHOLD:
            duplicate_id = memory.id
            break
        elif sim >= RELATED_THRESHOLD:
            related_ids.append(memory.id)

    return {
        "is_duplicate": duplicate_id is not None,
        "duplicate_id": duplicate_id,
        "related_ids": related_ids,
    }
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_memory_links.py -v
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/links.py backend/tests/test_memory_links.py
git commit -m "feat(memory): memory links and deduplication"
```

---

## Task 8: Memory Service

**Files:**
- Create: `backend/app/memory/service.py`

- [ ] **Step 1: Write failing tests for service**

Create `backend/tests/test_memory_crud.py`:

```python
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
            title="Workflow do time", content="O time usa revisão em pares.",
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
            title="Teste", content="Conteúdo de teste.",
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
            title="Sem embedding", content="Conteúdo.",
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
            title="Original", content="Conteúdo original.",
            tags=[], confidence=0.5, importance=0.5, source={}
        )
        mem = await svc.create_memory(mem_in)
        updated = await svc.update_memory(mem.id, {"content": "Novo conteúdo."})
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
            title="Para deletar", content="Conteúdo.",
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd backend && python -m pytest tests/test_memory_crud.py -v 2>&1 | head -10
```
Expected: `ModuleNotFoundError: No module named 'app.memory.service'`

- [ ] **Step 3: Create service.py**

Create `backend/app/memory/service.py`:

```python
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import MemoryModel, MemoryEmbeddingModel
from app.domain.enums import MemoryScope
from app.domain.schemas import Memory, MemoryCreate, MemorySearchRequest, MemorySearchResponse
from app.domain.utils import generate_id
from app.memory.embeddings import (
    EMBEDDING_MODEL, DEFAULT_OLLAMA_URL,
    get_embedding_for_memory, vector_to_json,
)
from app.memory.search import search_text, search_semantic, search_hybrid

MAX_MEMORIES_PER_PROMPT = 8
MAX_MEMORY_CHARS_PER_ITEM = 800
MAX_TOTAL_MEMORY_CHARS = 4000


class MemoryService:
    def __init__(
        self,
        db: Session,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        self.db = db
        self.ollama_url = ollama_url
        self.embedding_model = embedding_model

    # ── Internal helpers ──────────────────────────────────────────────────

    def _db_to_schema(self, db_mem: MemoryModel) -> Memory:
        tags = db_mem.tags if isinstance(db_mem.tags, list) else (json.loads(db_mem.tags) if db_mem.tags else [])
        source = db_mem.source if isinstance(db_mem.source, dict) else (json.loads(db_mem.source) if db_mem.source else {})
        return Memory(
            id=db_mem.id,
            scope=db_mem.scope,
            scope_id=db_mem.scope_id,
            type=db_mem.type,
            title=db_mem.title,
            content=db_mem.content,
            tags=tags,
            confidence=db_mem.confidence or 1.0,
            importance=db_mem.importance or 1.0,
            source=source,
            created_at=db_mem.created_at,
            updated_at=db_mem.updated_at,
            last_used_at=db_mem.last_used_at,
            usage_count=db_mem.usage_count or 0,
            deleted_at=db_mem.deleted_at,
            embedding_status=db_mem.embedding_status or "pending",
        )

    async def _generate_and_store_embedding(self, memory_id: str, text: str) -> bool:
        """Try to generate and store embedding. Returns True on success."""
        vec = await get_embedding_for_memory(text, model=self.embedding_model, base_url=self.ollama_url)
        db_mem = self.db.query(MemoryModel).filter(MemoryModel.id == memory_id).first()
        if not db_mem:
            return False

        if vec is None:
            db_mem.embedding_status = "failed"
            self.db.commit()
            return False

        existing = self.db.query(MemoryEmbeddingModel).filter(
            MemoryEmbeddingModel.memory_id == memory_id
        ).first()
        if existing:
            existing.embedding_vector = vector_to_json(vec)
            existing.embedding_model = self.embedding_model
        else:
            emb = MemoryEmbeddingModel(
                id=generate_id("emb"),
                memory_id=memory_id,
                embedding_model=self.embedding_model,
                embedding_vector=vector_to_json(vec),
            )
            self.db.add(emb)

        db_mem.embedding_status = "done"
        self.db.commit()
        return True

    # ── CRUD ─────────────────────────────────────────────────────────────

    async def create_memory(self, memory_in: MemoryCreate) -> Memory:
        mem_id = generate_id("memory")
        db_mem = MemoryModel(
            id=mem_id,
            scope=memory_in.scope,
            scope_id=memory_in.scope_id,
            type=memory_in.type,
            title=memory_in.title,
            content=memory_in.content,
            tags=memory_in.tags,
            confidence=memory_in.confidence,
            importance=memory_in.importance,
            source=memory_in.source,
            usage_count=0,
            embedding_status="pending",
        )
        self.db.add(db_mem)
        self.db.commit()
        self.db.refresh(db_mem)

        embedding_text = f"{memory_in.title} {memory_in.content}"
        await self._generate_and_store_embedding(mem_id, embedding_text)
        self.db.refresh(db_mem)
        return self._db_to_schema(db_mem)

    async def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> Optional[Memory]:
        db_mem = self.db.query(MemoryModel).filter(
            MemoryModel.id == memory_id, MemoryModel.deleted_at == None
        ).first()
        if not db_mem:
            return None

        content_changed = False
        for field, value in updates.items():
            if field in ("title", "content", "tags", "confidence", "importance"):
                setattr(db_mem, field, value)
                if field in ("title", "content"):
                    content_changed = True

        db_mem.updated_at = datetime.utcnow()
        self.db.commit()

        if content_changed:
            text = f"{db_mem.title} {db_mem.content}"
            await self._generate_and_store_embedding(memory_id, text)

        self.db.refresh(db_mem)
        return self._db_to_schema(db_mem)

    async def delete_memory(self, memory_id: str) -> bool:
        db_mem = self.db.query(MemoryModel).filter(MemoryModel.id == memory_id).first()
        if not db_mem:
            return False
        db_mem.deleted_at = datetime.utcnow()
        self.db.commit()
        return True

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        db_mem = self.db.query(MemoryModel).filter(
            MemoryModel.id == memory_id, MemoryModel.deleted_at == None
        ).first()
        return self._db_to_schema(db_mem) if db_mem else None

    def list_memories(
        self,
        scope: Optional[str] = None,
        scope_id: Optional[str] = None,
        type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Memory]:
        q = self.db.query(MemoryModel).filter(MemoryModel.deleted_at == None)
        if scope:
            q = q.filter(MemoryModel.scope == scope)
        if scope_id is not None:
            q = q.filter(MemoryModel.scope_id == scope_id)
        if type:
            q = q.filter(MemoryModel.type == type)
        rows = q.offset(skip).limit(limit).all()
        return [self._db_to_schema(r) for r in rows]

    # ── Search ────────────────────────────────────────────────────────────

    async def search(self, request: MemorySearchRequest) -> MemorySearchResponse:
        mode = request.mode
        if mode == "text":
            results = search_text(self.db, request.query, request.scopes, request.limit)
        elif mode == "semantic":
            results = await search_semantic(self.db, request.query, request.scopes, request.limit, self.ollama_url)
        else:
            results = await search_hybrid(self.db, request.query, request.scopes, request.limit, self.ollama_url)
        return MemorySearchResponse(results=results)

    # ── Usage recording ───────────────────────────────────────────────────

    def record_usage(self, memory_id: str, execution_id: str, agent_id: str, score: float = 0.0) -> None:
        from app.db.models import MemoryUsageModel
        db_mem = self.db.query(MemoryModel).filter(MemoryModel.id == memory_id).first()
        if not db_mem:
            return
        usage = MemoryUsageModel(
            id=generate_id("musage"),
            memory_id=memory_id,
            execution_id=execution_id,
            agent_id=agent_id,
            score=score,
        )
        self.db.add(usage)
        db_mem.usage_count = (db_mem.usage_count or 0) + 1
        db_mem.last_used_at = datetime.utcnow()
        self.db.commit()

    # ── Prompt formatting ─────────────────────────────────────────────────

    def format_memories_for_prompt(self, results: list) -> str:
        """Format search results into a prompt section. Respects size limits."""
        lines = []
        total_chars = 0

        for r in results[:MAX_MEMORIES_PER_PROMPT]:
            scope_label = r.scope if not r.scope_id else f"{r.scope}:{r.scope_id}"
            content = r.content[:MAX_MEMORY_CHARS_PER_ITEM]
            entry = f"[Memória: {r.type} | {scope_label} | score {r.score:.2f}]\n{content}"

            if total_chars + len(entry) > MAX_TOTAL_MEMORY_CHARS:
                break

            lines.append(entry)
            total_chars += len(entry)

        if not lines:
            return ""

        return "[RELEVANT MEMORIES]\n\n" + "\n\n".join(lines)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_memory_crud.py -v
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/service.py backend/tests/test_memory_crud.py
git commit -m "feat(memory): MemoryService with CRUD, embedding, and search"
```

---

## Task 9: Memory Tools

**Files:**
- Create: `backend/app/tools/core/memory.py`
- Modify: `backend/app/tools/capabilities.py`
- Modify: `backend/app/tools/registry.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_memory_tools.py`:

```python
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
    with patch("app.tools.core.memory.get_embedding_for_memory", AsyncMock(return_value=None)):
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd backend && python -m pytest tests/test_memory_tools.py -v 2>&1 | head -10
```
Expected: `ModuleNotFoundError: No module named 'app.tools.core.memory'`

- [ ] **Step 3: Create memory.py tool**

Create `backend/app/tools/core/memory.py`:

```python
from typing import Any, Dict

from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError
from app.memory.embeddings import get_embedding_for_memory
from app.memory.service import MemoryService
from app.domain.schemas import MemoryCreate, MemorySearchRequest
from app.domain.enums import MemoryScope, MemoryType


class MemorySearchTool(BaseTool):
    name = "memory.search"
    description = "Search agent memories by text, semantic similarity, or hybrid mode"
    capability = "memory"
    critical = False
    source = "core"
    input_schema = {
        "query": {"type": "string", "description": "Search query"},
        "scopes": {"type": "array", "items": {"type": "string"}, "description": "Scopes: global, agent:<id>, team:<id>"},
        "mode": {"type": "string", "description": "text | semantic | hybrid", "default": "hybrid"},
        "limit": {"type": "integer", "default": 10},
    }
    output_schema = {
        "results": {"type": "array"},
        "count": {"type": "integer"},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        query = arguments.get("query", "").strip()
        if not query:
            raise ToolError("memory.search requires 'query'", code="MISSING_ARGUMENT")

        scopes = arguments.get("scopes", ["global"])
        mode = arguments.get("mode", "hybrid")
        limit = int(arguments.get("limit", 10))

        svc = MemoryService(context.db)
        request = MemorySearchRequest(query=query, scopes=scopes, mode=mode, limit=limit)
        response = await svc.search(request)

        return {
            "results": [r.model_dump() for r in response.results],
            "count": len(response.results),
        }


class MemoryCreateTool(BaseTool):
    name = "memory.create"
    description = "Create a new memory entry (global, agent, or team scope)"
    capability = "memory"
    critical = False
    source = "core"
    input_schema = {
        "title": {"type": "string", "description": "Short descriptive title"},
        "content": {"type": "string", "description": "Memory content"},
        "scope": {"type": "string", "description": "global | agent | team", "default": "global"},
        "scope_id": {"type": "string", "description": "Agent or team ID (if scope is agent/team)", "nullable": True},
        "type": {"type": "string", "description": "preference | decision | lesson | workflow | ...", "default": "preference"},
        "tags": {"type": "array", "items": {"type": "string"}, "default": []},
        "confidence": {"type": "number", "default": 0.8},
        "importance": {"type": "number", "default": 0.7},
    }
    output_schema = {
        "memory_id": {"type": "string"},
        "status": {"type": "string"},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        title = arguments.get("title", "").strip()
        content = arguments.get("content", "").strip()
        if not title:
            raise ToolError("memory.create requires 'title'", code="MISSING_ARGUMENT")
        if not content:
            raise ToolError("memory.create requires 'content'", code="MISSING_ARGUMENT")

        scope_str = arguments.get("scope", "global")
        try:
            scope = MemoryScope(scope_str)
        except ValueError:
            scope = MemoryScope.GLOBAL

        type_str = arguments.get("type", "preference")
        try:
            mem_type = MemoryType(type_str)
        except ValueError:
            mem_type = MemoryType.PREFERENCE

        mem_in = MemoryCreate(
            scope=scope,
            scope_id=arguments.get("scope_id"),
            type=mem_type,
            title=title,
            content=content,
            tags=arguments.get("tags", []),
            confidence=float(arguments.get("confidence", 0.8)),
            importance=float(arguments.get("importance", 0.7)),
            source={
                "type": "agent_observation",
                "execution_id": context.execution_id,
                "agent_id": context.agent_id,
            },
        )
        svc = MemoryService(context.db)
        mem = await svc.create_memory(mem_in)
        return {"memory_id": mem.id, "status": "created"}
```

- [ ] **Step 4: Add memory capability to capabilities.py**

In `backend/app/tools/capabilities.py`, add to `CAPABILITIES` dict:
```python
    "memory": [
        "memory.search",
        "memory.create",
    ],
```

- [ ] **Step 5: Register memory tools in registry.py**

In `backend/app/tools/registry.py`, update `register_core_tools()` to add at the end:
```python
    from app.tools.core.memory import MemorySearchTool, MemoryCreateTool
    memory_tools = [MemorySearchTool(), MemoryCreateTool()]
    for tool in memory_tools:
        if not tool_registry.exists(tool.name):
            tool_registry.register(tool)
```

- [ ] **Step 6: Run tests**

```bash
cd backend && python -m pytest tests/test_memory_tools.py -v
```
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/tools/core/memory.py backend/app/tools/capabilities.py backend/app/tools/registry.py backend/tests/test_memory_tools.py
git commit -m "feat(memory): memory.search and memory.create tools"
```

---

## Task 10: Update API Router

**Files:**
- Modify: `backend/app/api/routers/memories.py`

- [ ] **Step 1: Rewrite memories router**

Replace the content of `backend/app/api/routers/memories.py` with:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.domain import schemas
from app.domain.schemas import (
    Memory, MemoryCreate, MemoryUpdate,
    MemoryLinkCreate, MemoryLink,
    MemorySearchRequest, MemorySearchResponse,
)
from app.domain.utils import generate_id
from app.memory.service import MemoryService
from app.memory.links import create_link, get_links

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=List[Memory])
async def list_memories(
    scope: Optional[str] = Query(None),
    scope_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    svc = MemoryService(db)
    return svc.list_memories(scope=scope, scope_id=scope_id, type=type, skip=skip, limit=limit)


@router.post("", response_model=Memory)
async def create_memory(obj_in: MemoryCreate, db: Session = Depends(get_db)):
    svc = MemoryService(db)
    return await svc.create_memory(obj_in)


@router.get("/{memory_id}", response_model=Memory)
def get_memory(memory_id: str, db: Session = Depends(get_db)):
    svc = MemoryService(db)
    mem = svc.get_memory(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    return mem


@router.put("/{memory_id}", response_model=Memory)
async def update_memory(memory_id: str, obj_in: MemoryUpdate, db: Session = Depends(get_db)):
    svc = MemoryService(db)
    updated = await svc.update_memory(memory_id, obj_in.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Memory not found")
    return updated


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, db: Session = Depends(get_db)):
    svc = MemoryService(db)
    deleted = await svc.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(request: MemorySearchRequest, db: Session = Depends(get_db)):
    svc = MemoryService(db)
    return await svc.search(request)


@router.post("/{memory_id}/links", response_model=dict)
def create_memory_link(memory_id: str, link_in: MemoryLinkCreate, db: Session = Depends(get_db)):
    svc = MemoryService(db)
    if not svc.get_memory(memory_id):
        raise HTTPException(status_code=404, detail="Source memory not found")
    if not svc.get_memory(link_in.target_memory_id):
        raise HTTPException(status_code=404, detail="Target memory not found")
    link = create_link(db, memory_id, link_in.target_memory_id, link_in.relation_type, link_in.strength)
    return {"id": link.id, "source_memory_id": link.source_memory_id,
            "target_memory_id": link.target_memory_id, "relation_type": link.relation_type,
            "strength": link.strength}


@router.get("/{memory_id}/links", response_model=List[dict])
def get_memory_links(memory_id: str, db: Session = Depends(get_db)):
    links = get_links(db, memory_id)
    return [{"id": l.id, "source_memory_id": l.source_memory_id,
             "target_memory_id": l.target_memory_id, "relation_type": l.relation_type,
             "strength": l.strength} for l in links]
```

- [ ] **Step 2: Run existing tests to verify no regressions**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: previously passing tests still pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routers/memories.py
git commit -m "feat(memory): update memories router with search, links, filtering, soft-delete"
```

---

## Task 11: Runtime Integration

**Files:**
- Modify: `backend/app/runtime/prompt_builder.py`
- Modify: `backend/app/runtime/agent_runtime.py`

- [ ] **Step 1: Write failing runtime tests**

Create `backend/tests/test_memory_runtime.py`:

```python
"""Tests for memory injection in Agent Runtime."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, MemoryModel
from app.domain.schemas import Agent, Execution, Provider, ModelConfig, MemoryConfig
from app.domain.enums import ExecutionType, ExecutionStatus, ApprovalMode, EventType, ProviderType
from app.runtime.agent_runtime import AgentRuntime


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


def _make_agent(agent_id="agent_001", use_global=True, use_agent_memory=True):
    return Agent(
        id=agent_id,
        name="Test Agent",
        model_config=ModelConfig(provider_id="prov_001", model="llama3"),
        memory_config=MemoryConfig(use_global=use_global, use_agent_memory=use_agent_memory),
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )


def _make_execution(agent_id="agent_001"):
    return Execution(
        id="exec_001", type=ExecutionType.AGENT, target_id=agent_id,
        user_input="Qual é minha preferência de resposta?",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )


def _make_provider():
    return Provider(id="prov_001", type=ProviderType.OLLAMA, name="Ollama")


@pytest.mark.asyncio
async def test_runtime_injects_memories_into_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Prefere Python", "Usa Python para scripts e automações")

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))
    mock_provider.stream_chat = AsyncMock(return_value=iter([]))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.memory.search.get_embedding_for_memory", AsyncMock(return_value=None)):
        mock_registry.get.return_value = mock_provider
        runtime = AgentRuntime(db_session=db)
        agent = _make_agent()
        execution = _make_execution()
        provider = _make_provider()

        events = []
        async for event in runtime.run(agent, execution, provider, stream=False):
            events.append(event)

    memory_events = [e for e in events if "memory" in e.type]
    assert len(memory_events) >= 1

    prompt_events = [e for e in events if e.type == "prompt_built"]
    assert len(prompt_events) == 1


@pytest.mark.asyncio
async def test_runtime_continues_when_memory_search_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))
    mock_provider.stream_chat = AsyncMock(return_value=iter([]))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.runtime.agent_runtime.MemoryService") as MockMemorySvc:
        MockMemorySvc.return_value.search = AsyncMock(side_effect=Exception("DB error"))
        MockMemorySvc.return_value.format_memories_for_prompt = MagicMock(return_value="")
        MockMemorySvc.return_value.record_usage = MagicMock()
        mock_registry.get.return_value = mock_provider
        runtime = AgentRuntime(db_session=db)
        agent = _make_agent()
        execution = _make_execution()
        provider = _make_provider()

        events = []
        async for event in runtime.run(agent, execution, provider, stream=False):
            events.append(event)

    # Should still complete despite memory failure
    assert any("completed" in e.type or "error" in e.type for e in events)


@pytest.mark.asyncio
async def test_memory_scopes_respect_agent_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()

    captured_scopes = []

    async def fake_search(request):
        captured_scopes.extend(request.scopes)
        return MagicMock(results=[])

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.runtime.agent_runtime.MemoryService") as MockMemorySvc:
        svc_instance = MagicMock()
        svc_instance.search = AsyncMock(side_effect=fake_search)
        svc_instance.format_memories_for_prompt = MagicMock(return_value="")
        svc_instance.record_usage = MagicMock()
        MockMemorySvc.return_value = svc_instance
        mock_registry.get.return_value = mock_provider

        runtime = AgentRuntime(db_session=db)
        agent = _make_agent("agent_001", use_global=True, use_agent_memory=True)
        execution = _make_execution()
        provider = _make_provider()

        async for _ in runtime.run(agent, execution, provider, stream=False):
            pass

    assert "global" in captured_scopes
    assert "agent:agent_001" in captured_scopes


@pytest.mark.asyncio
async def test_memory_usage_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()

    usage_calls = []

    async def fake_search(request):
        from app.domain.schemas import MemorySearchResult, MemorySearchResponse
        result = MemorySearchResult(
            memory_id="m1", score=0.9, scope="global", scope_id=None,
            type="preference", title="T", content="C", tags=[],
            confidence=0.8, importance=0.7, has_embedding=False,
        )
        return MemorySearchResponse(results=[result])

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.runtime.agent_runtime.MemoryService") as MockMemorySvc:
        svc_instance = MagicMock()
        svc_instance.search = AsyncMock(side_effect=fake_search)
        svc_instance.format_memories_for_prompt = MagicMock(return_value="[RELEVANT MEMORIES]\n\nT: C")
        svc_instance.record_usage = MagicMock(side_effect=lambda *a, **kw: usage_calls.append(a))
        MockMemorySvc.return_value = svc_instance
        mock_registry.get.return_value = mock_provider

        runtime = AgentRuntime(db_session=db)
        agent = _make_agent()
        execution = _make_execution()
        provider = _make_provider()

        async for _ in runtime.run(agent, execution, provider, stream=False):
            pass

    assert len(usage_calls) >= 1
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && python -m pytest tests/test_memory_runtime.py::test_runtime_injects_memories_into_prompt -v 2>&1 | head -20
```
Expected: test fails (no memory injection yet)

- [ ] **Step 3: Update prompt_builder.py**

In `backend/app/runtime/prompt_builder.py`:

Add a new parameter to `__init__`:
```python
def __init__(self, agent: Agent, execution: Execution, available_tools: List[ToolDefinition] = None, memory_context: str = ""):
    self.agent = agent
    self.execution = execution
    self.available_tools = available_tools or []
    self.memory_context = memory_context
```

Add a new method before `build_system_prompt`:
```python
def _get_memory_context(self) -> str:
    return self.memory_context
```

Update `build_system_prompt` to include memory context:
```python
def build_system_prompt(self) -> str:
    parts = [
        self._get_system_rules(),
        self._get_agent_system_prompt(),
        self._get_memory_context(),
        self._get_operation_mode(),
        self._get_execution_context(),
        self._get_tools_instructions(),
    ]
    return "\n".join(filter(None, parts))
```

- [ ] **Step 4: Update agent_runtime.py**

In `backend/app/runtime/agent_runtime.py`, add import at the top:
```python
from app.memory.service import MemoryService
from app.domain.schemas import MemorySearchRequest
```

In the `run()` method, replace the `if initial_messages is not None:` block with:

```python
            if initial_messages is not None:
                messages = initial_messages
            else:
                # Memory lookup
                memory_context = ""
                try:
                    memory_svc = MemoryService(self.db)
                    scopes = []
                    if agent.memory_config.use_global:
                        scopes.append("global")
                    if agent.memory_config.use_agent_memory:
                        scopes.append(f"agent:{agent_id}")

                    if scopes:
                        yield self._make_event(
                            execution_id, EventType.MEMORY_LOOKUP, "runtime", agent_id,
                            {"scopes": scopes, "query": execution.user_input}
                        )
                        search_req = MemorySearchRequest(
                            query=execution.user_input,
                            scopes=scopes,
                            mode="hybrid",
                            limit=8,
                        )
                        search_resp = await memory_svc.search(search_req)
                        memory_context = memory_svc.format_memories_for_prompt(search_resp.results)

                        yield self._make_event(
                            execution_id, EventType.MEMORY_LOOKUP_RESULT, "runtime", agent_id,
                            {"count": len(search_resp.results), "has_context": bool(memory_context)}
                        )

                        for result in search_resp.results:
                            memory_svc.record_usage(result.memory_id, execution_id, agent_id, result.score)

                        if search_resp.results:
                            yield self._make_event(
                                execution_id, EventType.MEMORY_USAGE_RECORDED, "runtime", agent_id,
                                {"memory_ids": [r.memory_id for r in search_resp.results]}
                            )
                except Exception:
                    pass  # Memory failure must never crash execution

                builder = PromptBuilder(agent, execution, available_tools, memory_context=memory_context)
                messages = builder.build_messages()
                yield self._make_event(
                    execution_id, EventType.PROMPT_BUILT, "runtime", agent_id,
                    {"messages": messages, "available_tools": [t.name for t in available_tools]}
                )
```

- [ ] **Step 5: Run runtime tests**

```bash
cd backend && python -m pytest tests/test_memory_runtime.py -v
```
Expected: all tests pass

- [ ] **Step 6: Run full test suite to check regressions**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all previously passing tests still pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/runtime/prompt_builder.py backend/app/runtime/agent_runtime.py backend/tests/test_memory_runtime.py
git commit -m "feat(memory): inject memories into Agent Runtime prompt"
```

---

## Task 12: Frontend — API Client + Types

**Files:**
- Create: `apps/frontend/src/api/memories.ts`
- Modify: `apps/frontend/src/types/domain.ts`

- [ ] **Step 1: Add Memory types to domain.ts**

In `apps/frontend/src/types/domain.ts`, add:

```typescript
export type MemoryScope = 'global' | 'agent' | 'team' | 'workspace'
export type MemoryType =
  | 'profile' | 'preference' | 'project' | 'file_reference'
  | 'task_history' | 'decision' | 'lesson' | 'error_pattern'
  | 'workflow' | 'system_note'

export interface Memory {
  id: string
  scope: MemoryScope
  scope_id: string | null
  type: MemoryType
  title: string
  content: string
  tags: string[]
  confidence: number
  importance: number
  source: Record<string, unknown>
  created_at: string
  updated_at: string
  last_used_at: string | null
  usage_count: number
  deleted_at: string | null
  embedding_status: 'pending' | 'done' | 'failed'
}

export interface MemoryCreate {
  scope: MemoryScope
  scope_id?: string | null
  type: MemoryType
  title: string
  content: string
  tags?: string[]
  confidence?: number
  importance?: number
  source?: Record<string, unknown>
}

export interface MemoryUpdate {
  title?: string
  content?: string
  tags?: string[]
  confidence?: number
  importance?: number
}

export interface MemorySearchRequest {
  query: string
  scopes?: string[]
  mode?: 'text' | 'semantic' | 'hybrid'
  limit?: number
}

export interface MemorySearchResult {
  memory_id: string
  score: number
  scope: string
  scope_id: string | null
  type: string
  title: string
  content: string
  tags: string[]
  confidence: number
  importance: number
  has_embedding: boolean
}

export interface MemorySearchResponse {
  results: MemorySearchResult[]
}

export interface MemoryLinkCreate {
  target_memory_id: string
  relation_type: string
  strength?: number
}
```

- [ ] **Step 2: Create memories API client**

Create `apps/frontend/src/api/memories.ts`:

```typescript
import { apiClient } from './client'
import type {
  Memory, MemoryCreate, MemoryUpdate,
  MemorySearchRequest, MemorySearchResponse,
  MemoryLinkCreate,
} from '../types/domain'

export const memoriesApi = {
  list: (params?: { scope?: string; scope_id?: string; type?: string }) =>
    apiClient.get<Memory[]>('/memories', { params }),

  get: (id: string) =>
    apiClient.get<Memory>(`/memories/${id}`),

  create: (data: MemoryCreate) =>
    apiClient.post<Memory>('/memories', data),

  update: (id: string, data: MemoryUpdate) =>
    apiClient.put<Memory>(`/memories/${id}`, data),

  delete: (id: string) =>
    apiClient.delete<{ status: string }>(`/memories/${id}`),

  search: (request: MemorySearchRequest) =>
    apiClient.post<MemorySearchResponse>('/memories/search', request),

  createLink: (memoryId: string, link: MemoryLinkCreate) =>
    apiClient.post<{ id: string }>(`/memories/${memoryId}/links`, link),

  getLinks: (memoryId: string) =>
    apiClient.get<{ id: string; source_memory_id: string; target_memory_id: string; relation_type: string; strength: number }[]>(
      `/memories/${memoryId}/links`
    ),
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/frontend/src/types/domain.ts apps/frontend/src/api/memories.ts
git commit -m "feat(memory): frontend types and API client"
```

---

## Task 13: Frontend — Memory View

**Files:**
- Create: `apps/frontend/src/views/Memory.tsx`
- Modify: `apps/frontend/src/App.tsx`
- Modify: `apps/frontend/src/components/Sidebar.tsx`
- Modify: `apps/frontend/src/views/ExecutionDetail.tsx`

- [ ] **Step 1: Create Memory.tsx**

Create `apps/frontend/src/views/Memory.tsx`:

```tsx
import { useState, useEffect, useCallback } from 'react'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { memoriesApi } from '../api/memories'
import type { Memory, MemoryCreate, MemorySearchResult, MemoryScope, MemoryType } from '../types/domain'

const SCOPES: MemoryScope[] = ['global', 'agent', 'team', 'workspace']
const TYPES: MemoryType[] = [
  'profile', 'preference', 'project', 'file_reference',
  'task_history', 'decision', 'lesson', 'error_pattern', 'workflow', 'system_note',
]

const EMBEDDING_BADGE: Record<string, string> = {
  done: 'bg-green-500/20 text-green-300',
  failed: 'bg-red-500/20 text-red-300',
  pending: 'bg-yellow-500/20 text-yellow-300',
}

export function Memory() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterScope, setFilterScope] = useState('')
  const [filterType, setFilterType] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMode, setSearchMode] = useState<'text' | 'semantic' | 'hybrid'>('hybrid')
  const [searchResults, setSearchResults] = useState<MemorySearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)

  const [form, setForm] = useState<Partial<MemoryCreate>>({
    scope: 'global', type: 'preference', title: '', content: '',
    tags: [], confidence: 0.8, importance: 0.7, source: {},
  })

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {}
      if (filterScope) params.scope = filterScope
      if (filterType) params.type = filterType
      const data = await memoriesApi.list(params)
      setMemories(data)
    } catch {
      setError('Failed to load memories')
    } finally {
      setLoading(false)
    }
  }, [filterScope, filterType])

  useEffect(() => { load() }, [load])

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const resp = await memoriesApi.search({
        query: searchQuery,
        scopes: filterScope ? [filterScope] : ['global'],
        mode: searchMode,
        limit: 20,
      })
      setSearchResults(resp.results)
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleCreate = async () => {
    if (!form.title || !form.content) return
    try {
      await memoriesApi.create(form as MemoryCreate)
      setShowForm(false)
      setForm({ scope: 'global', type: 'preference', title: '', content: '', tags: [], confidence: 0.8, importance: 0.7, source: {} })
      load()
    } catch {
      setError('Failed to create memory')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this memory?')) return
    try {
      await memoriesApi.delete(id)
      load()
    } catch {
      setError('Failed to delete memory')
    }
  }

  const displayList = searchResults !== null
    ? searchResults.map(r => memories.find(m => m.id === r.memory_id)).filter(Boolean) as Memory[]
    : memories

  if (loading) return <LoadingState message="Loading memories..." />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div className="flex flex-col h-full">
      <TopBar title="Memory" subtitle={`${memories.length} memories`} />
      <div className="flex-1 overflow-auto p-4 space-y-4">

        {/* Filters + Search */}
        <div className="flex flex-wrap gap-2 items-end">
          <select
            value={filterScope}
            onChange={e => { setFilterScope(e.target.value); setSearchResults(null) }}
            className="bg-slate-800 text-slate-200 rounded px-2 py-1 text-sm border border-slate-700"
          >
            <option value="">All scopes</option>
            {SCOPES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          <select
            value={filterType}
            onChange={e => { setFilterType(e.target.value); setSearchResults(null) }}
            className="bg-slate-800 text-slate-200 rounded px-2 py-1 text-sm border border-slate-700"
          >
            <option value="">All types</option>
            {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>

          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="Search memories..."
            className="flex-1 min-w-40 bg-slate-800 text-slate-200 rounded px-3 py-1 text-sm border border-slate-700"
          />

          <select
            value={searchMode}
            onChange={e => setSearchMode(e.target.value as 'text' | 'semantic' | 'hybrid')}
            className="bg-slate-800 text-slate-200 rounded px-2 py-1 text-sm border border-slate-700"
          >
            <option value="hybrid">Hybrid</option>
            <option value="text">Text</option>
            <option value="semantic">Semantic</option>
          </select>

          <button
            onClick={handleSearch}
            disabled={searching}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-3 py-1 text-sm"
          >
            {searching ? 'Searching...' : 'Search'}
          </button>

          {searchResults !== null && (
            <button
              onClick={() => setSearchResults(null)}
              className="text-slate-400 hover:text-slate-200 text-sm"
            >
              Clear
            </button>
          )}

          <button
            onClick={() => setShowForm(true)}
            className="ml-auto bg-green-600 hover:bg-green-700 text-white rounded px-3 py-1 text-sm"
          >
            + New Memory
          </button>
        </div>

        {/* Create Form */}
        {showForm && (
          <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 space-y-3">
            <h3 className="text-slate-100 font-medium text-sm">New Memory</h3>
            <div className="grid grid-cols-2 gap-3">
              <input
                placeholder="Title"
                value={form.title ?? ''}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                className="col-span-2 bg-slate-900 text-slate-200 rounded px-3 py-1.5 text-sm border border-slate-700"
              />
              <textarea
                placeholder="Content"
                value={form.content ?? ''}
                onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                rows={3}
                className="col-span-2 bg-slate-900 text-slate-200 rounded px-3 py-1.5 text-sm border border-slate-700 resize-none"
              />
              <select
                value={form.scope ?? 'global'}
                onChange={e => setForm(f => ({ ...f, scope: e.target.value as MemoryScope }))}
                className="bg-slate-900 text-slate-200 rounded px-2 py-1.5 text-sm border border-slate-700"
              >
                {SCOPES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <select
                value={form.type ?? 'preference'}
                onChange={e => setForm(f => ({ ...f, type: e.target.value as MemoryType }))}
                className="bg-slate-900 text-slate-200 rounded px-2 py-1.5 text-sm border border-slate-700"
              >
                {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <input
                placeholder="scope_id (if agent/team)"
                value={form.scope_id ?? ''}
                onChange={e => setForm(f => ({ ...f, scope_id: e.target.value || null }))}
                className="bg-slate-900 text-slate-200 rounded px-3 py-1.5 text-sm border border-slate-700"
              />
              <input
                placeholder="tags (comma-separated)"
                value={(form.tags ?? []).join(', ')}
                onChange={e => setForm(f => ({ ...f, tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) }))}
                className="bg-slate-900 text-slate-200 rounded px-3 py-1.5 text-sm border border-slate-700"
              />
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Confidence: {form.confidence}
                <input type="range" min="0" max="1" step="0.1"
                  value={form.confidence ?? 0.8}
                  onChange={e => setForm(f => ({ ...f, confidence: parseFloat(e.target.value) }))}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Importance: {form.importance}
                <input type="range" min="0" max="1" step="0.1"
                  value={form.importance ?? 0.7}
                  onChange={e => setForm(f => ({ ...f, importance: parseFloat(e.target.value) }))}
                />
              </label>
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-200 text-sm px-3 py-1">Cancel</button>
              <button onClick={handleCreate} className="bg-green-600 hover:bg-green-700 text-white rounded px-3 py-1 text-sm">Save</button>
            </div>
          </div>
        )}

        {/* Memory List */}
        {searchResults !== null && (
          <p className="text-slate-400 text-xs">
            Search results: {searchResults.length} found
            {searchResults.length > 0 && ` (mode: ${searchMode})`}
          </p>
        )}

        <div className="space-y-2">
          {displayList.length === 0 && (
            <div className="text-center text-slate-500 py-12 text-sm">No memories found.</div>
          )}
          {displayList.map(mem => {
            const searchResult = searchResults?.find(r => r.memory_id === mem.id)
            return (
              <div key={mem.id} className="bg-slate-800 rounded-lg p-4 border border-slate-700 hover:border-slate-600 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-slate-100 font-medium text-sm">{mem.title}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300">{mem.scope}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300">{mem.type}</span>
                      {mem.scope_id && <span className="text-xs text-slate-500">{mem.scope_id}</span>}
                      <span className={`text-xs px-1.5 py-0.5 rounded ${EMBEDDING_BADGE[mem.embedding_status] ?? ''}`}>
                        {mem.embedding_status === 'done' ? 'embedded' : mem.embedding_status}
                      </span>
                      {searchResult && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">
                          score {searchResult.score.toFixed(2)}
                        </span>
                      )}
                    </div>
                    <p className="text-slate-400 text-sm line-clamp-2">{mem.content}</p>
                    {mem.tags.length > 0 && (
                      <div className="flex gap-1 mt-1.5 flex-wrap">
                        {mem.tags.map(tag => (
                          <span key={tag} className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">#{tag}</span>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-3 mt-1.5 text-xs text-slate-600">
                      <span>confidence {mem.confidence.toFixed(1)}</span>
                      <span>importance {mem.importance.toFixed(1)}</span>
                      <span>used {mem.usage_count}×</span>
                      {mem.source && (mem.source as Record<string, unknown>).type && (
                        <span>source: {String((mem.source as Record<string, unknown>).type)}</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(mem.id)}
                    className="text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded hover:bg-red-500/10 shrink-0"
                  >
                    Delete
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add Memory route to App.tsx**

In `apps/frontend/src/App.tsx`, add import:
```tsx
import { Memory } from './views/Memory'
```

Add route after the tools route:
```tsx
          <Route path="memory" element={<Memory />} />
```

- [ ] **Step 3: Add Memory to Sidebar**

In `apps/frontend/src/components/Sidebar.tsx`, add to `NAV_ITEMS`:
```tsx
  { path: '/memory', label: 'Memory' },
```
Add it between `Tools` and `Settings`.

Also update the footer version:
```tsx
        <p className="text-xs text-slate-600">v0.1.0 — Phase 9</p>
```

- [ ] **Step 4: Update ExecutionDetail event labels**

In `apps/frontend/src/views/ExecutionDetail.tsx`, add to `EVENT_LABELS`:
```typescript
  memory_lookup: 'Memory lookup',
  memory_lookup_result: 'Memories found',
  memory_created: 'Memory created',
  memory_updated: 'Memory updated',
  memory_deleted: 'Memory deleted',
  memory_embedding_generated: 'Embedding generated',
  memory_embedding_failed: 'Embedding failed',
  memory_usage_recorded: 'Memory usage recorded',
```

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/views/Memory.tsx apps/frontend/src/App.tsx apps/frontend/src/components/Sidebar.tsx apps/frontend/src/views/ExecutionDetail.tsx
git commit -m "feat(memory): Memory view, route, sidebar link, timeline labels"
```

---

## Task 14: Frontend Tests

**Files:**
- Create: `apps/frontend/src/__tests__/Memory.test.tsx`

- [ ] **Step 1: Write test**

Create `apps/frontend/src/__tests__/Memory.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { Memory } from '../views/Memory'
import { memoriesApi } from '../api/memories'

vi.mock('../api/memories', () => ({
  memoriesApi: {
    list: vi.fn(),
    search: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockMemory = {
  id: 'mem_001',
  scope: 'global' as const,
  scope_id: null,
  type: 'preference' as const,
  title: 'Prefere Python',
  content: 'Usa Python para automações',
  tags: ['python'],
  confidence: 0.9,
  importance: 0.8,
  source: {},
  created_at: '2026-06-18T00:00:00',
  updated_at: '2026-06-18T00:00:00',
  last_used_at: null,
  usage_count: 0,
  deleted_at: null,
  embedding_status: 'done' as const,
}

describe('Memory view', () => {
  beforeEach(() => {
    vi.mocked(memoriesApi.list).mockResolvedValue([mockMemory])
    vi.mocked(memoriesApi.search).mockResolvedValue({ results: [] })
  })

  it('renders memory list', async () => {
    render(<MemoryRouter><Memory /></MemoryRouter>)
    await waitFor(() => screen.getByText('Prefere Python'))
    expect(screen.getByText('Prefere Python')).toBeInTheDocument()
  })

  it('calls list API on mount', async () => {
    render(<MemoryRouter><Memory /></MemoryRouter>)
    await waitFor(() => expect(memoriesApi.list).toHaveBeenCalled())
  })

  it('calls search API when search button is clicked', async () => {
    const { getByPlaceholderText, getByText } = render(<MemoryRouter><Memory /></MemoryRouter>)
    await waitFor(() => screen.getByText('Prefere Python'))
    const input = getByPlaceholderText('Search memories...')
    input.dispatchEvent(new Event('input', { bubbles: true }))
    // Update value via fireEvent
    const { fireEvent } = await import('@testing-library/react')
    fireEvent.change(input, { target: { value: 'python' } })
    fireEvent.click(getByText('Search'))
    await waitFor(() => expect(memoriesApi.search).toHaveBeenCalledWith(
      expect.objectContaining({ query: 'python' })
    ))
  })
})
```

- [ ] **Step 2: Run frontend tests**

```bash
cd apps/frontend && npm run test -- --reporter=verbose 2>&1 | tail -30
```
Expected: Memory tests pass, no regressions in other tests

- [ ] **Step 3: Commit**

```bash
git add apps/frontend/src/__tests__/Memory.test.tsx
git commit -m "test(memory): Memory view frontend tests"
```

---

## Task 15: Full Test Suite Verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```
Expected: 103+ tests passing, 0 failures

- [ ] **Step 2: Run all frontend tests**

```bash
cd apps/frontend && npm run test 2>&1 | tail -20
```
Expected: all tests passing

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat(phase9): complete Memory System implementation"
```

---

## Self-Review: Spec Coverage

| Requirement | Task |
|---|---|
| Memory service with CRUD | Task 8 |
| Scopes: global, agent, team | Tasks 1, 8 |
| Workspace scope (structure) | Tasks 1, 3 |
| Memory types (10 types) | Task 3 (enums already exist) |
| Embeddings via Ollama | Tasks 5, 8 |
| Text search | Task 6 |
| Semantic search | Task 6 |
| Hybrid search | Task 6 |
| Deduplication basic | Task 7 |
| Memory links | Task 7, 10 |
| Usage recording | Tasks 8, 11 |
| Agent Runtime injection | Task 11 |
| Memory limits in prompt | Task 8 (format_memories_for_prompt) |
| Timeline events | Tasks 3, 11 |
| Audit logs for memory | Not explicit in runtime (events cover it) |
| Memory page frontend | Tasks 12, 13 |
| memory.search tool | Task 9 |
| memory.create tool | Task 9 |
| Embedding failure is graceful | Tasks 5, 8 |
| Scope isolation | Tasks 6, runtime |
| Soft delete | Tasks 1, 8, 10 |
| DB migration | Task 2 |

**Gaps identified and resolved:**
- Soft delete covered in Task 1 (deleted_at column) + Task 8 (service) + Task 10 (router)
- Audit logs for memory: the memory events in EventType and the `MEMORY_CREATED`/`MEMORY_DELETED` event types cover audit trail requirements; full audit_log table entries can be added in Phase 10 if stricter audit is needed
- Team memory config: `agent.memory_config.use_team_memory` and `team_id` lookup not implemented (agent doesn't have a direct team_id at execution time) — this is deferred per spec ("use avançado para depois")
