from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.domain.schemas import (
    Memory, MemoryCreate, MemoryUpdate,
    MemoryLinkCreate,
    MemorySearchRequest, MemorySearchResponse,
)
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


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(request: MemorySearchRequest, db: Session = Depends(get_db)):
    svc = MemoryService(db)
    return await svc.search(request)


@router.post("/reembed")
async def reembed_memories(
    scope: Optional[str] = Query(None),
    scope_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Backfill embeddings for memories whose embedding failed or is pending."""
    svc = MemoryService(db)
    return await svc.reembed_failed(scope=scope, scope_id=scope_id)


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


@router.post("/{memory_id}/links", response_model=dict)
def create_memory_link(memory_id: str, link_in: MemoryLinkCreate, db: Session = Depends(get_db)):
    svc = MemoryService(db)
    if not svc.get_memory(memory_id):
        raise HTTPException(status_code=404, detail="Source memory not found")
    if not svc.get_memory(link_in.target_memory_id):
        raise HTTPException(status_code=404, detail="Target memory not found")
    link = create_link(db, memory_id, link_in.target_memory_id, link_in.relation_type, link_in.strength)
    return {
        "id": link.id,
        "source_memory_id": link.source_memory_id,
        "target_memory_id": link.target_memory_id,
        "relation_type": link.relation_type,
        "strength": link.strength,
    }


@router.get("/{memory_id}/links", response_model=List[dict])
def get_memory_links(memory_id: str, db: Session = Depends(get_db)):
    links = get_links(db, memory_id)
    return [
        {
            "id": lnk.id,
            "source_memory_id": lnk.source_memory_id,
            "target_memory_id": lnk.target_memory_id,
            "relation_type": lnk.relation_type,
            "strength": lnk.strength,
        }
        for lnk in links
    ]
