from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.repositories.registry import provider_repo
from app.domain import schemas
from app.domain.enums import ProviderType
from app.domain.utils import generate_id
from app.setup import settings_store

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_COMPLETED_KEY = "onboarding_completed"


class OpenRouterKey(BaseModel):
    api_key: str


@router.get("/state")
def get_state(db: Session = Depends(get_db)) -> dict:
    completed = settings_store.get(db, _COMPLETED_KEY, "false") == "true"
    has_providers = len(provider_repo.get_multi(db, limit=1)) > 0
    return {"completed": completed, "has_providers": has_providers}


@router.post("/complete")
def complete(db: Session = Depends(get_db)) -> dict:
    settings_store.set(db, _COMPLETED_KEY, "true")
    return {"completed": True}


@router.post("/provider/ollama", response_model=schemas.Provider)
def create_ollama_provider(db: Session = Depends(get_db)):
    for p in provider_repo.get_multi(db, limit=100):
        if p.type == ProviderType.OLLAMA.value:
            return schemas.Provider.model_validate(p)
    obj = schemas.ProviderCreate(
        type=ProviderType.OLLAMA, name="Ollama (local)",
        base_url="http://localhost:11434", enabled=True, config={},
    )
    created = provider_repo.create(db, obj_in=obj, id=generate_id("provider"))
    return schemas.Provider.model_validate(created)


@router.post("/provider/openrouter", response_model=schemas.Provider)
def create_openrouter_provider(body: OpenRouterKey, db: Session = Depends(get_db)):
    obj = schemas.ProviderCreate(
        type=ProviderType.OPENROUTER, name="OpenRouter",
        base_url=None, enabled=True, config={"api_key": body.api_key},
    )
    created = provider_repo.create(db, obj_in=obj, id=generate_id("provider"))
    return schemas.Provider.model_validate(created)
