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
