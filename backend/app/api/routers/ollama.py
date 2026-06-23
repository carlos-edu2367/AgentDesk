import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.setup import hardware, catalog, ollama_manager

router = APIRouter(tags=["ollama"])


class PullRequest(BaseModel):
    model: str


@router.get("/system/hardware")
def get_hardware() -> dict:
    return hardware.detect().to_dict()


@router.get("/ollama/status")
async def get_status() -> dict:
    return await ollama_manager.status()


@router.get("/ollama/recommendations")
def get_recommendations() -> dict:
    hw = hardware.detect()
    return {"hardware": hw.to_dict(), **catalog.recommend(hw)}


def _ndjson(agen) -> StreamingResponse:
    async def gen():
        async for event in agen:
            yield json.dumps(event) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.post("/ollama/install")
def post_install() -> StreamingResponse:
    return _ndjson(ollama_manager.install())


@router.post("/ollama/pull")
def post_pull(req: PullRequest) -> StreamingResponse:
    return _ndjson(ollama_manager.pull(req.model))
