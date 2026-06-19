from __future__ import annotations

import re
from typing import Any

from app.domain.utils import mask_secrets


SECRET_KEY_PARTS = ("TOKEN", "API_KEY", "SECRET", "PASSWORD", "AUTH", "BEARER")
MAX_PREVIEW_CHARS = 4000


def normalize_part(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    normalized = re.sub(r"[^a-z0-9_]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def mcp_tool_name(server_id: str, tool_name: str) -> str:
    return f"mcp.{normalize_part(server_id)}.{normalize_part(tool_name)}"


def preview(value: str, max_chars: int = MAX_PREVIEW_CHARS) -> str:
    return value[:max_chars]


def _is_secret_key(key: str) -> bool:
    upper = key.upper()
    return any(part in upper for part in SECRET_KEY_PARTS)


def _looks_like_secret(value: str) -> bool:
    upper = value.upper()
    return any(part in upper for part in ("TOKEN", "BEARER ")) or len(value) > 80


def _mask_scalar(value: Any) -> str:
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:2]}***{text[-4:]}"
