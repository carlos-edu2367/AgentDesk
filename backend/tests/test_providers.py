import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.providers.ollama import OllamaProvider
from app.providers.openrouter import OpenRouterProvider
from app.providers.schemas import (
    ChatRequest, ChatMessage, EmbeddingRequest
)
from app.providers.errors import (
    ProviderUnavailableError,
    ModelNotFoundError,
    ApiKeyMissingError,
    ApiKeyInvalidError,
    RateLimitedError
)

@pytest.fixture
def chat_request():
    return ChatRequest(
        provider_id="test",
        model="test-model",
        messages=[ChatMessage(role="user", content="hello")]
    )

@pytest.mark.asyncio
async def test_ollama_health_check_success():
    provider = OllamaProvider(provider_id="ollama_local")
    
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "qwen3:8b"}]}
    
    provider._request = AsyncMock(return_value=mock_response)
    
    health = await provider.health_check()
    assert health.status is True
    assert health.details["models_count"] == 1

@pytest.mark.asyncio
async def test_ollama_health_check_fail():
    provider = OllamaProvider(provider_id="ollama_local")
    provider._request = AsyncMock(side_effect=ProviderUnavailableError())
    
    health = await provider.health_check()
    assert health.status is False
    assert "error" in health.details

@pytest.mark.asyncio
async def test_ollama_list_models():
    provider = OllamaProvider(provider_id="ollama_local")
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "qwen3:8b"}]}
    provider._request = AsyncMock(return_value=mock_response)
    
    models = await provider.list_models()
    assert len(models) == 1
    assert models[0].id == "qwen3:8b"

@pytest.mark.asyncio
async def test_ollama_chat(chat_request):
    provider = OllamaProvider(provider_id="ollama_local")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "ok"},
        "prompt_eval_count": 10,
        "eval_count": 5
    }
    provider._request = AsyncMock(return_value=mock_response)
    
    resp = await provider.chat(chat_request)
    assert resp.content == "ok"
    assert resp.usage.total_tokens == 15

@pytest.mark.asyncio
async def test_ollama_embeddings():
    provider = OllamaProvider(provider_id="ollama_local")
    mock_response = MagicMock()
    mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
    provider._request = AsyncMock(return_value=mock_response)
    
    req = EmbeddingRequest(model="nomic", input="test")
    resp = await provider.embed(req)
    assert resp.embedding == [0.1, 0.2, 0.3]

@pytest.mark.asyncio
async def test_openrouter_missing_api_key():
    with pytest.raises(ApiKeyMissingError):
        OpenRouterProvider(provider_id="or", config={})

@pytest.mark.asyncio
async def test_openrouter_chat(chat_request):
    provider = OpenRouterProvider(provider_id="or", config={"api_key": "sk-123"})
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "hello"}}],
        "usage": {"total_tokens": 10}
    }
    provider._request = AsyncMock(return_value=mock_response)
    
    resp = await provider.chat(chat_request)
    assert resp.content == "hello"
    assert resp.usage.total_tokens == 10

@pytest.mark.asyncio
async def test_openrouter_rate_limit(chat_request):
    provider = OpenRouterProvider(provider_id="or", config={"api_key": "sk-123"})
    provider._request = AsyncMock(side_effect=RateLimitedError())
    
    with pytest.raises(RateLimitedError):
        await provider.chat(chat_request)

@pytest.mark.asyncio
async def test_registry_unknown_provider():
    from app.providers.registry import ProviderRegistry
    from app.domain.enums import ProviderType
    from app.domain.schemas import Provider as DomainProvider
    from app.providers.errors import UnknownProviderError
    
    registry = ProviderRegistry()
    # Bypass schema validation to exercise ProviderRegistry's defensive branch.
    invalid_provider = DomainProvider.model_construct(
        id="invalid", type="invalid_type", name="Invalid", enabled=True,
        base_url=None, config={}
    )
    with pytest.raises(UnknownProviderError, match="Unknown provider type"):
        registry.get(invalid_provider)

@pytest.mark.asyncio
async def test_registry_disabled_provider():
    from app.providers.registry import ProviderRegistry
    from app.domain.enums import ProviderType
    from app.domain.schemas import Provider as DomainProvider
    from app.providers.errors import UnknownProviderError
    
    registry = ProviderRegistry()
    disabled_provider = DomainProvider(
        id="disabled", type=ProviderType.OLLAMA, name="Disabled", enabled=False
    )
    with pytest.raises(UnknownProviderError, match="is disabled"):
        registry.get(disabled_provider)

@pytest.mark.asyncio
async def test_ollama_stream_chat_mock(chat_request):
    from app.providers.schemas import ModelChunk
    
    provider = OllamaProvider(provider_id="ollama_local")
    
    async def mock_aiter_lines():
        yield '{"message": {"content": "hel"}, "done": false}'
        yield '{"message": {"content": "lo"}, "done": false}'
        yield '{"done": true, "prompt_eval_count": 5, "eval_count": 2}'
    
    class MockResponse:
        def raise_for_status(self): pass
        async def aiter_lines(self):
            async for line in mock_aiter_lines():
                yield line
                
    class MockStreamContext:
        async def __aenter__(self):
            return MockResponse()
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockAsyncClient:
        def stream(self, *args, **kwargs):
            return MockStreamContext()
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc_val, exc_tb): pass

    with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
        chunks = []
        async for chunk in provider.stream_chat(chat_request):
            chunks.append(chunk)
            
        assert len(chunks) == 3
        assert chunks[0].content_delta == "hel"
        assert chunks[1].content_delta == "lo"
        assert chunks[2].done is True
        assert chunks[2].usage is not None
        assert chunks[2].usage.total_tokens == 7
