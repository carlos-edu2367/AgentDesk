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
    ApiKeyMissingError,
    ApiKeyInvalidError,
    RateLimitedError,
    EmbeddingUnavailableError
)

class OpenRouterProvider(ModelProvider):
    def __init__(self, provider_id: str, base_url: str = "https://openrouter.ai/api/v1", config: Dict[str, Any] = None):
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.config = config or {}
        self.api_key = self.config.get("api_key")
        self.timeout = self.config.get("timeout", 60.0)
        
        if not self.api_key:
            raise ApiKeyMissingError()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:3000", # Can be configured
            "X-Title": "AgentDesk",
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, headers=self._get_headers(), **kwargs)
                response.raise_for_status()
                return response
        except httpx.TimeoutException as e:
            raise RequestTimeoutError(details={"url": url})
        except httpx.ConnectError as e:
            raise ProviderUnavailableError(details={"url": url})
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 401:
                raise ApiKeyInvalidError()
            elif status == 404:
                raise ModelNotFoundError(details={"url": url})
            elif status == 429:
                raise RateLimitedError()
            else:
                err_details = "Unknown Error"
                try:
                    err_json = e.response.json()
                    err_details = err_json.get("error", {}).get("message", err_details)
                except Exception:
                    pass
                raise UnknownProviderError(message=f"HTTP Error: {status}", details={"error": err_details})
        except Exception as e:
            raise UnknownProviderError(details={"error": "An unexpected error occurred."})

    async def health_check(self) -> ProviderHealth:
        try:
            response = await self._request("GET", "/models")
            data = response.json()
            return ProviderHealth(status=True, details={"models_count": len(data.get("data", []))})
        except Exception as e:
            return ProviderHealth(status=False, details={"error": str(e)})

    async def list_models(self) -> List[ModelInfo]:
        response = await self._request("GET", "/models")
        data = response.json()
        models = []
        for m in data.get("data", []):
            models.append(ModelInfo(
                id=m["id"],
                name=m["name"],
                context_window=m.get("context_length", 8192)
            ))
        return models

    def _prepare_payload(self, request: ChatRequest, stream: bool = False) -> Dict[str, Any]:
        return {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "stream": stream
        }

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload = self._prepare_payload(request, stream=False)
        response = await self._request("POST", "/chat/completions", json=payload)
        data = response.json()
        
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        
        usage_data = data.get("usage", {})
        usage = ChatUsage(
            prompt_tokens=usage_data.get("prompt_tokens"),
            completion_tokens=usage_data.get("completion_tokens"),
            total_tokens=usage_data.get("total_tokens")
        )
        
        return ChatResponse(
            provider_id=self.provider_id,
            model=request.model,
            content=content,
            usage=usage,
            raw=data
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[ModelChunk, None]:
        payload = self._prepare_payload(request, stream=True)
        url = f"{self.base_url}/chat/completions"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=self._get_headers(), json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        
                        data_str = line[len("data: "):]
                        if data_str.strip() == "[DONE]":
                            yield ModelChunk(
                                provider_id=self.provider_id,
                                model=request.model,
                                content_delta="",
                                done=True
                            )
                            break
                            
                        try:
                            data = json.loads(data_str)
                            choice = data.get("choices", [{}])[0]
                            delta_obj = choice.get("delta", {})
                            delta = delta_obj.get("content", "") or ""
                            reasoning = delta_obj.get("reasoning", "") or ""

                            yield ModelChunk(
                                provider_id=self.provider_id,
                                model=request.model,
                                content_delta=delta,
                                reasoning_delta=reasoning,
                                done=False
                            )
                        except json.JSONDecodeError:
                            continue
        except httpx.TimeoutException:
            raise RequestTimeoutError(details={"url": url})
        except httpx.ConnectError:
            raise ProviderUnavailableError(details={"url": url})
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 401:
                raise ApiKeyInvalidError()
            elif status == 404:
                raise ModelNotFoundError(details={"url": url})
            elif status == 429:
                raise RateLimitedError()
            else:
                raise UnknownProviderError(message=f"HTTP Error: {status}")
        except Exception:
            raise UnknownProviderError(details={"error": "An unexpected error occurred during streaming."})

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        # OpenRouter doesn't natively support a universal embeddings endpoint like this.
        # It's better to delegate embeddings to Ollama or OpenAI directly.
        raise EmbeddingUnavailableError(message="Embeddings not natively supported by this OpenRouter provider implementation.")
