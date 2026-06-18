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
