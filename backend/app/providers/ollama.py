import json
import httpx
from typing import List, AsyncGenerator, Dict, Any

from .base import ModelProvider
from .schemas import (
    ProviderHealth,
    ModelInfo,
    ChatRequest,
    ChatResponse,
    ChatUsage,
    ModelChunk,
    EmbeddingRequest,
    EmbeddingResponse
)
from .errors import (
    ProviderUnavailableError,
    ModelNotFoundError,
    RequestTimeoutError,
    UnknownProviderError,
    EmbeddingUnavailableError
)

class OllamaProvider(ModelProvider):
    def __init__(self, provider_id: str, base_url: str = "http://localhost:11434", config: Dict[str, Any] = None):
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.config = config or {}
        self.timeout = self.config.get("timeout", 60.0)

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
        except httpx.TimeoutException as e:
            raise RequestTimeoutError(details={"url": url, "error": str(e)})
        except httpx.ConnectError as e:
            raise ProviderUnavailableError(details={"url": url, "error": str(e)})
        except httpx.HTTPStatusError as e:
            # Try to extract Ollama error
            err_details = e.response.text
            try:
                err_json = e.response.json()
                if "error" in err_json:
                    err_details = err_json["error"]
            except Exception:
                pass
            if e.response.status_code == 404:
                raise ModelNotFoundError(details={"url": url, "error": err_details})
            raise UnknownProviderError(message=f"HTTP Error: {e.response.status_code}", details={"error": err_details})
        except Exception as e:
            raise UnknownProviderError(details={"error": str(e)})

    async def health_check(self) -> ProviderHealth:
        try:
            response = await self._request("GET", "/api/tags")
            data = response.json()
            return ProviderHealth(status=True, details={"models_count": len(data.get("models", []))})
        except Exception as e:
            return ProviderHealth(status=False, details={"error": str(e)})

    async def list_models(self) -> List[ModelInfo]:
        response = await self._request("GET", "/api/tags")
        data = response.json()
        models = []
        for m in data.get("models", []):
            models.append(ModelInfo(
                id=m["name"],
                name=m["name"],
                context_window=8192 # default local context window assumption
            ))
        return models

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_ctx": request.context_window,
                "num_predict": request.max_tokens
            },
            "stream": False
        }
        
        response = await self._request("POST", "/api/chat", json=payload)
        data = response.json()
        
        message = data.get("message", {})
        content = message.get("content", "")
        
        usage = ChatUsage(
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            total_tokens=(data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0)
        )
        
        return ChatResponse(
            provider_id=self.provider_id,
            model=request.model,
            content=content,
            usage=usage,
            raw=data
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[ModelChunk, None]:
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_ctx": request.context_window,
                "num_predict": request.max_tokens
            },
            "stream": True
        }
        
        url = f"{self.base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        message = data.get("message", {})
                        
                        done = data.get("done", False)
                        usage = None
                        if done:
                            usage = ChatUsage(
                                prompt_tokens=data.get("prompt_eval_count"),
                                completion_tokens=data.get("eval_count"),
                                total_tokens=(data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0)
                            )
                        
                        yield ModelChunk(
                            provider_id=self.provider_id,
                            model=request.model,
                            content_delta=message.get("content", ""),
                            done=done,
                            usage=usage
                        )
        except httpx.TimeoutException as e:
            raise RequestTimeoutError(details={"url": url, "error": str(e)})
        except httpx.ConnectError as e:
            raise ProviderUnavailableError(details={"url": url, "error": str(e)})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelNotFoundError(details={"url": url, "error": "Model not found"})
            raise UnknownProviderError(message=f"HTTP Error: {e.response.status_code}")
        except Exception as e:
            raise UnknownProviderError(details={"error": str(e)})

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        payload = {
            "model": request.model,
            "input": request.input
        }
        try:
            response = await self._request("POST", "/api/embed", json=payload)
            data = response.json()
            embeddings = data.get("embeddings", [])
            embedding = embeddings[0] if embeddings else []
            return EmbeddingResponse(
                model=request.model,
                embedding=embedding
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # If embed endpoint not found, try old embeddings endpoint
                if "embed" in e.request.url.path:
                    payload_old = {
                        "model": request.model,
                        "prompt": request.input
                    }
                    try:
                        resp_old = await self._request("POST", "/api/embeddings", json=payload_old)
                        data_old = resp_old.json()
                        return EmbeddingResponse(
                            model=request.model,
                            embedding=data_old.get("embedding", [])
                        )
                    except Exception as old_e:
                        raise EmbeddingUnavailableError(details={"error": str(old_e)})
            raise EmbeddingUnavailableError(details={"error": "Model not found or error generating embedding"})
        except Exception as e:
            raise EmbeddingUnavailableError(details={"error": str(e)})
