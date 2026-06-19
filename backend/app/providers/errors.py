class ProviderError(Exception):
    """Base exception for all provider errors."""
    def __init__(self, code: str, message: str, details: dict = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

class ProviderUnavailableError(ProviderError):
    def __init__(self, message: str = "O provider não está disponível.", details: dict = None):
        super().__init__("PROVIDER_UNAVAILABLE", message, details)

class ModelNotFoundError(ProviderError):
    def __init__(self, message: str = "Modelo não encontrado.", details: dict = None):
        super().__init__("MODEL_NOT_FOUND", message, details)

class ApiKeyMissingError(ProviderError):
    def __init__(self, message: str = "API Key ausente.", details: dict = None):
        super().__init__("API_KEY_MISSING", message, details)

class ApiKeyInvalidError(ProviderError):
    def __init__(self, message: str = "API Key inválida.", details: dict = None):
        super().__init__("API_KEY_INVALID", message, details)

class RequestTimeoutError(ProviderError):
    def __init__(self, message: str = "A requisição expirou (timeout).", details: dict = None):
        super().__init__("REQUEST_TIMEOUT", message, details)

class ContextTooLargeError(ProviderError):
    def __init__(self, message: str = "O contexto excedeu o limite máximo suportado.", details: dict = None):
        super().__init__("CONTEXT_TOO_LARGE", message, details)

class RateLimitedError(ProviderError):
    def __init__(self, message: str = "Limite de taxa (rate limit) excedido.", details: dict = None):
        super().__init__("RATE_LIMITED", message, details)

class EmbeddingUnavailableError(ProviderError):
    def __init__(self, message: str = "Embeddings não suportados ou indisponíveis.", details: dict = None):
        super().__init__("EMBEDDING_UNAVAILABLE", message, details)

class UnknownProviderError(ProviderError):
    def __init__(self, message: str = "Erro desconhecido no provider.", details: dict = None):
        super().__init__("UNKNOWN_PROVIDER_ERROR", message, details)
