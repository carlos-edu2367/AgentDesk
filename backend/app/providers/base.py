from abc import ABC, abstractmethod
from typing import List, AsyncGenerator
from .schemas import (
    ProviderHealth,
    ModelInfo,
    ChatRequest,
    ChatResponse,
    ModelChunk,
    EmbeddingRequest,
    EmbeddingResponse
)

class ModelProvider(ABC):
    """Abstract base class for all Model Providers."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check if the provider is available and healthy."""
        pass

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """List available models for this provider."""
        pass

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Execute a synchronous chat completion."""
        pass

    @abstractmethod
    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[ModelChunk, None]:
        """Execute a streaming chat completion."""
        pass

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings for the given input."""
        pass
