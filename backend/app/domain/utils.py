import re
import uuid
from typing import Any

def generate_id(prefix: str) -> str:
    """Gera um ID unico com prefixo. Ex: agent_a1b2c3d4"""
    return f"{prefix}_{uuid.uuid4().hex}"


SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "bearer",
    "cookie",
    "set-cookie",
    "x-api-key",
    "openrouter",
)

SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-or-[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"(Authorization\s*:\s*Bearer\s+)([A-Za-z0-9._\-+/=]+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._\-+/=]+)", re.IGNORECASE),
    re.compile(r"(Cookie\s*:\s*)([^;\n\r]+)", re.IGNORECASE),
    re.compile(r"(Set-Cookie\s*:\s*)([^;\n\r]+)", re.IGNORECASE),
)


def mask_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                masked[key] = _mask_any(item)
            else:
                masked[key] = mask_secrets(item)
        return masked
    if isinstance(value, list):
        return [mask_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_secrets(item) for item in value)
    if isinstance(value, str):
        return _mask_string(value)
    return value


def truncate_large_fields(value: Any, max_chars: int = 4000) -> Any:
    if isinstance(value, dict):
        return {key: truncate_large_fields(item, max_chars=max_chars) for key, item in value.items()}
    if isinstance(value, list):
        return [truncate_large_fields(item, max_chars=max_chars) for item in value]
    if isinstance(value, str) and len(value) > max_chars:
        return f"{value[:max_chars]} [truncated]"
    return value


def sanitize_for_output(value: Any, max_chars: int = 4000) -> Any:
    return truncate_large_fields(mask_secrets(value), max_chars=max_chars)


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(re.sub(r"[^a-z0-9]", "", part) in normalized for part in SECRET_KEY_PARTS)


def _mask_any(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _mask_any(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask_any(item) for item in value]
    return _mask_scalar(value)


def _mask_string(value: str) -> str:
    masked = value
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.pattern.startswith("(Authorization") or pattern.pattern.startswith("(Bearer"):
            masked = pattern.sub(lambda match: f"{match.group(1)}{_mask_scalar(match.group(2))}", masked)
        elif pattern.pattern.startswith("(Cookie") or pattern.pattern.startswith("(Set-Cookie"):
            masked = pattern.sub(lambda match: f"{match.group(1)}{_mask_scalar(match.group(2))}", masked)
        else:
            masked = pattern.sub(lambda match: _mask_scalar(match.group(0)), masked)
    if _looks_like_secret(masked):
        return _mask_scalar(masked)
    return masked


def _looks_like_secret(value: str) -> bool:
    lowered = value.lower()
    if any(part in lowered for part in ("sk-or-", "openrouter", "api_key", "apikey", "token=", "secret=", "password=")):
        return True
    return False


def _mask_scalar(value: Any) -> str:
    text = str(value)
    if len(text) <= 8:
        return "***"
    if text.lower().startswith("sk-or-") and len(text) > 12:
        return f"{text[:8]}***{text[-4:]}"
    return f"***{text[-4:]}"
