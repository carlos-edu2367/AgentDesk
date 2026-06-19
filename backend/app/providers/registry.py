from typing import Dict, Type, Any
from app.domain.enums import ProviderType
from app.domain.schemas import Provider as DomainProvider
from .base import ModelProvider
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider
from .errors import UnknownProviderError

class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[ProviderType, Type[ModelProvider]] = {
            ProviderType.OLLAMA: OllamaProvider,
            ProviderType.OPENROUTER: OpenRouterProvider,
        }
        # To cache instantiated providers by their ID to avoid recreating them for every request
        self._instances: Dict[str, ModelProvider] = {}

    def register(self, provider_type: ProviderType, provider_class: Type[ModelProvider]):
        """Register a new provider class."""
        self._providers[provider_type] = provider_class

    def get(self, provider_config: DomainProvider) -> ModelProvider:
        """Get or instantiate a provider based on its configuration."""
        if not provider_config.enabled:
            raise UnknownProviderError(message=f"Provider {provider_config.id} is disabled.")

        if provider_config.id in self._instances:
            # Note: in a real production system, we might want to recreate the instance 
            # if the config has changed. For the MVP, we just cache it or we can recreate every time.
            # Let's recreate every time to ensure fresh config is used, since config can be updated via CRUD.
            pass

        provider_class = self._providers.get(provider_config.type)
        if not provider_class:
            raise UnknownProviderError(message=f"Unknown provider type: {provider_config.type}")

        # The Ollama and OpenRouter constructors expect (provider_id, base_url, config)
        instance = provider_class(
            provider_id=provider_config.id,
            base_url=provider_config.base_url,
            config=provider_config.config
        )
        
        self._instances[provider_config.id] = instance
        return instance

provider_registry = ProviderRegistry()
