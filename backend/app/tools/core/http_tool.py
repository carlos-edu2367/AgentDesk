import time
from typing import Any, Dict, Set

import httpx

from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

HTTP_DEFAULT_TIMEOUT = 30.0
HTTP_MAX_TIMEOUT = 60.0
HTTP_MAX_BODY_BYTES = 200_000

ALLOWED_METHODS: Set[str] = {"GET", "POST", "PUT", "PATCH", "DELETE"}

SENSITIVE_HEADER_NAMES: Set[str] = {
    "authorization", "x-api-key", "api-key", "apikey", "token",
    "secret", "password", "bearer", "x-auth-token", "x-access-token",
    "x-secret-key", "x-token",
}


def _mask_sensitive_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Returns a copy with sensitive header values replaced by ***."""
    return {
        k: "***" if k.lower() in SENSITIVE_HEADER_NAMES else v
        for k, v in headers.items()
    }


def _safe_response_headers(headers: httpx.Headers) -> Dict[str, str]:
    """Converts response headers to dict, masking sensitive values."""
    result: Dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADER_NAMES:
            result[k] = "***"
        else:
            result[k] = v
    return result


class HttpRequestTool(BaseTool):
    name = "http.request"
    description = "Makes an HTTP request to an external URL. Requires http capability."
    capability = "http"
    critical = True
    source = "core"
    input_schema = {
        "method": {"type": "string", "description": "HTTP method: GET, POST, PUT, PATCH, DELETE.", "default": "GET"},
        "url": {"type": "string", "description": "Target URL.", "required": True},
        "headers": {"type": "object", "description": "Request headers.", "default": {}},
        "body": {"type": "any", "description": "Request body (JSON or string).", "default": None},
        "timeout_seconds": {"type": "number", "description": "Request timeout in seconds (max 60).", "default": 30},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        method = str(arguments.get("method", "GET")).upper()
        url = arguments.get("url", "")
        headers: Dict[str, str] = dict(arguments.get("headers") or {})
        body = arguments.get("body", None)
        timeout_seconds = min(float(arguments.get("timeout_seconds", HTTP_DEFAULT_TIMEOUT)), HTTP_MAX_TIMEOUT)

        if method not in ALLOWED_METHODS:
            raise ToolError("INVALID_METHOD", f"Method '{method}' is not allowed. Use: {', '.join(sorted(ALLOWED_METHODS))}")
        if not url:
            raise ToolError("MISSING_URL", "Argument 'url' is required")

        safe_request_headers = _mask_sensitive_headers(headers)

        start_ms = int(time.monotonic() * 1000)
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
                if body is not None and isinstance(body, (dict, list)):
                    response = await client.request(method, url, headers=headers, json=body)
                elif body is not None:
                    response = await client.request(method, url, headers=headers, content=str(body))
                else:
                    response = await client.request(method, url, headers=headers)
        except httpx.TimeoutException as exc:
            raise ToolError("HTTP_TIMEOUT", f"Request timed out after {timeout_seconds}s") from exc
        except httpx.InvalidURL as exc:
            raise ToolError("INVALID_URL", f"Invalid URL: {url}") from exc
        except httpx.RequestError as exc:
            raise ToolError("HTTP_ERROR", f"Request failed: {exc}") from exc

        duration_ms = int(time.monotonic() * 1000) - start_ms

        raw_body = response.text
        body_truncated = len(raw_body) > HTTP_MAX_BODY_BYTES
        body_preview = raw_body[:HTTP_MAX_BODY_BYTES]

        return {
            "status_code": response.status_code,
            "headers": _safe_response_headers(response.headers),
            "body": body_preview,
            "body_truncated": body_truncated,
            "duration_ms": duration_ms,
            "request": {
                "method": method,
                "url": url,
                "headers": safe_request_headers,
            },
        }
