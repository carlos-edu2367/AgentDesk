from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import MemoryModel, MemoryEmbeddingModel, MemoryUsageModel
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

    async def search(self, request: MemorySearchRequest) -> MemorySearchResponse:
        mode = request.mode
        if mode == "text":
            results = search_text(self.db, request.query, request.scopes, request.limit)
        elif mode == "semantic":
            results = await search_semantic(self.db, request.query, request.scopes, request.limit, self.ollama_url)
        else:
            results = await search_hybrid(self.db, request.query, request.scopes, request.limit, self.ollama_url)
        return MemorySearchResponse(results=results)

    def record_usage(self, memory_id: str, execution_id: str, agent_id: str, score: float = 0.0) -> None:
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

    def format_memories_for_prompt(self, results: list) -> str:
        """Format search results into prompt section. Respects size limits."""
        lines = []
        total_chars = 0

        for r in results[:MAX_MEMORIES_PER_PROMPT]:
            scope_label = r.scope if not r.scope_id else f"{r.scope}:{r.scope_id}"
            content = r.content[:MAX_MEMORY_CHARS_PER_ITEM]
            entry = f"[Memoria: {r.type} | {scope_label} | score {r.score:.2f}]\n{content}"

            if total_chars + len(entry) > MAX_TOTAL_MEMORY_CHARS:
                break

            lines.append(entry)
            total_chars += len(entry)

        if not lines:
            return ""

        return "[RELEVANT MEMORIES]\n\n" + "\n\n".join(lines)
