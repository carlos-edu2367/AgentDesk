import asyncio
from typing import List, AsyncGenerator
from app.providers.base import ModelProvider
from app.providers.schemas import (
    ProviderHealth, ModelInfo, ChatRequest, ChatResponse,
    ChatUsage, ModelChunk, EmbeddingRequest, EmbeddingResponse
)
from app.providers.errors import ProviderError

class MockProvider(ModelProvider):
    def __init__(self, provider_id: str, base_url: str = "", config: dict = None):
        self.provider_id = provider_id
        self.config = config or {}
        self.mock_response_text = self.config.get("mock_response_text", "This is a mock response.")
        self.mock_error = self.config.get("mock_error", None)
        self.mock_chunks = self.config.get("mock_chunks", ["This ", "is ", "a ", "mock ", "response."])

    async def health_check(self) -> ProviderHealth:
        if self.mock_error:
            return ProviderHealth(status=False, details={"error": "Mocked error"})
        return ProviderHealth(status=True, details={"models_count": 1})

    async def list_models(self) -> List[ModelInfo]:
        return [ModelInfo(id="mock-model", name="Mock Model")]

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if self.mock_error:
            raise ProviderError("MOCK_ERROR", self.mock_error)
        
        return ChatResponse(
            provider_id=self.provider_id,
            model=request.model,
            content=self.mock_response_text,
            usage=ChatUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[ModelChunk, None]:
        if self.mock_error:
            raise ProviderError("MOCK_ERROR", self.mock_error)
            
        for chunk in self.mock_chunks:
            yield ModelChunk(
                provider_id=self.provider_id,
                model=request.model,
                content_delta=chunk,
                done=False
            )
            await asyncio.sleep(0.01)
            
        yield ModelChunk(
            provider_id=self.provider_id,
            model=request.model,
            content_delta="",
            done=True,
            usage=ChatUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        return EmbeddingResponse(model=request.model, embedding=[0.0, 0.0, 0.0])
