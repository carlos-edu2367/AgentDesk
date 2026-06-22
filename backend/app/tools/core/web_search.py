import re
from html import unescape
from typing import Any, Dict, List
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

WEB_SEARCH_TIMEOUT = 15.0
MAX_WEB_RESULTS = 10
SNIPPET_MAX_CHARS = 400

DDG_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"
_USER_AGENT = "Mozilla/5.0 (compatible; AgentDesk/1.0)"

_RESULT_ANCHOR_RE = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(fragment: str) -> str:
    return unescape(_TAG_RE.sub("", fragment)).strip()


def _clean_url(href: str) -> str:
    """DuckDuckGo wraps result links in a redirect (/l/?uddg=<encoded>). Unwrap it."""
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            qs = parse_qs(parsed.query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])
    except Exception:
        pass
    return href


def parse_ddg_html(html: str, max_results: int) -> List[Dict[str, str]]:
    """Parses DuckDuckGo HTML results into [{title, url, snippet}]. Pure function."""
    anchors = _RESULT_ANCHOR_RE.findall(html)
    snippets = [_strip_html(s)[:SNIPPET_MAX_CHARS] for s in _SNIPPET_RE.findall(html)]

    results: List[Dict[str, str]] = []
    for i, (href, title_html) in enumerate(anchors):
        title = _strip_html(title_html)
        if not title:
            continue
        results.append({
            "title": title,
            "url": _clean_url(href),
            "snippet": snippets[i] if i < len(snippets) else "",
        })
        if len(results) >= max_results:
            break
    return results


class WebSearchTool(BaseTool):
    name = "web.search"
    description = (
        "Searches the web (via DuckDuckGo) and returns a list of results with "
        "title, url, and snippet. Use it to find documentation, error messages, or "
        "current information. For fetching a specific known URL, use http.request."
    )
    capability = "web"
    critical = True
    source = "core"
    input_schema = {
        "query": {"type": "string", "description": "Search query.", "required": True},
        "max_results": {"type": "integer", "description": "Maximum results (max 10).", "default": 5},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        query = (arguments.get("query") or "").strip()
        max_results = min(int(arguments.get("max_results", 5)), MAX_WEB_RESULTS)

        if not query:
            raise ToolError("MISSING_QUERY", "Argument 'query' is required")

        try:
            async with httpx.AsyncClient(timeout=WEB_SEARCH_TIMEOUT, follow_redirects=True) as client:
                response = await client.post(
                    DDG_HTML_ENDPOINT,
                    data={"q": query},
                    headers={"User-Agent": _USER_AGENT},
                )
        except httpx.TimeoutException as exc:
            raise ToolError("WEB_SEARCH_TIMEOUT", f"Search timed out after {WEB_SEARCH_TIMEOUT}s") from exc
        except httpx.RequestError as exc:
            raise ToolError("WEB_SEARCH_ERROR", f"Search request failed: {exc}") from exc

        if response.status_code != 200:
            raise ToolError("WEB_SEARCH_ERROR", f"Search returned HTTP {response.status_code}")

        results = parse_ddg_html(response.text, max_results)
        return {
            "query": query,
            "count": len(results),
            "results": results,
        }
