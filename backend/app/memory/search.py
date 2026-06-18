from __future__ import annotations

import json
from typing import List

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
    """Full-text search across title, content, tags."""
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

    scores: dict = {}
    for r in text_results:
        scores[r.memory_id] = scores.get(r.memory_id, 0.0) + 0.4 * r.score
    for r in semantic_results:
        scores[r.memory_id] = scores.get(r.memory_id, 0.0) + 0.6 * r.score

    all_memories: dict = {}
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
