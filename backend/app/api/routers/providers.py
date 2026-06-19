from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.domain import schemas
from app.db.repositories.registry import provider_repo
from app.domain.utils import generate_id
from app.providers import (
    provider_registry,
    ProviderHealth,
    ModelInfo,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ProviderError
)
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/providers", tags=["providers"])

def mask_provider(provider: schemas.Provider) -> schemas.Provider:
    if provider and provider.config and "api_key" in provider.config:
        key = provider.config["api_key"]
        if isinstance(key, str) and len(key) > 6:
            provider.config["api_key"] = f"sk-...{key[-4:]}"
    return provider

@router.get("", response_model=List[schemas.Provider])
def list_providers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    providers = provider_repo.get_multi(db, skip=skip, limit=limit)
    return [mask_provider(schemas.Provider.model_validate(p)) for p in providers]

@router.post("", response_model=schemas.Provider)
def create_provider(provider_in: schemas.ProviderCreate, db: Session = Depends(get_db)):
    new_id = generate_id("provider")
    p = provider_repo.create(db, obj_in=provider_in, id=new_id)
    return mask_provider(schemas.Provider.model_validate(p))

@router.get("/{provider_id}", response_model=schemas.Provider)
def get_provider(provider_id: str, db: Session = Depends(get_db)):
    p = provider_repo.get(db, id=provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    return mask_provider(schemas.Provider.model_validate(p))

@router.put("/{provider_id}", response_model=schemas.Provider)
def update_provider(provider_id: str, provider_in: schemas.ProviderUpdate, db: Session = Depends(get_db)):
    p = provider_repo.get(db, id=provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    p_updated = provider_repo.update(db, db_obj=p, obj_in=provider_in)
    return mask_provider(schemas.Provider.model_validate(p_updated))

@router.delete("/{provider_id}")
def delete_provider(provider_id: str, db: Session = Depends(get_db)):
    p = provider_repo.remove(db, id=provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"status": "deleted"}

def _get_provider_instance(provider_id: str, db: Session):
    p = provider_repo.get(db, id=provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    domain_provider = schemas.Provider.model_validate(p)
    try:
        return provider_registry.get(domain_provider)
    except ProviderError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message, "details": e.details})

@router.post("/{provider_id}/health", response_model=ProviderHealth)
async def provider_health(provider_id: str, db: Session = Depends(get_db)):
    provider = _get_provider_instance(provider_id, db)
    try:
        return await provider.health_check()
    except ProviderError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message, "details": e.details})

@router.get("/{provider_id}/models", response_model=List[ModelInfo])
async def list_provider_models(provider_id: str, db: Session = Depends(get_db)):
    provider = _get_provider_instance(provider_id, db)
    try:
        return await provider.list_models()
    except ProviderError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message, "details": e.details})

@router.post("/{provider_id}/chat")
async def provider_chat(provider_id: str, request: ChatRequest, db: Session = Depends(get_db)):
    provider = _get_provider_instance(provider_id, db)
    try:
        if request.stream:
            async def generate():
                async for chunk in provider.stream_chat(request):
                    yield chunk.model_dump_json() + "\n"
            return StreamingResponse(generate(), media_type="application/x-ndjson")
        else:
            return await provider.chat(request)
    except ProviderError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message, "details": e.details})

@router.post("/{provider_id}/embeddings", response_model=EmbeddingResponse)
async def provider_embeddings(provider_id: str, request: EmbeddingRequest, db: Session = Depends(get_db)):
    provider = _get_provider_instance(provider_id, db)
    try:
        return await provider.embed(request)
    except ProviderError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message, "details": e.details})

