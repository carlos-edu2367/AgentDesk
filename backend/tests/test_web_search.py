"""Tests for web.search — DuckDuckGo HTML parsing (pure) + execute (mocked)."""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.base import ToolExecutionContext
from app.tools.core.web_search import WebSearchTool, parse_ddg_html
from app.tools.errors import ToolError


SAMPLE_HTML = """
<div class="result">
  <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs&rut=abc">
    Example <b>Docs</b>
  </a>
  <a class="result__snippet" href="x">The official <b>docs</b> for Example.</a>
</div>
<div class="result">
  <a rel="nofollow" class="result__a" href="https://direct.example.org/page">Direct Link</a>
  <a class="result__snippet" href="y">A direct result.</a>
</div>
"""


def _ctx():
    return ToolExecutionContext(execution_id="e", agent_id="a", workspace_ids=[], db=None, approval_mode="auto")


def test_parse_unwraps_redirect_and_strips_html():
    results = parse_ddg_html(SAMPLE_HTML, max_results=10)
    assert len(results) == 2
    assert results[0]["title"] == "Example Docs"
    assert results[0]["url"] == "https://example.com/docs"
    assert results[0]["snippet"] == "The official docs for Example."
    assert results[1]["url"] == "https://direct.example.org/page"


def test_parse_respects_max_results():
    results = parse_ddg_html(SAMPLE_HTML, max_results=1)
    assert len(results) == 1


def test_parse_empty_html():
    assert parse_ddg_html("<html><body>no results</body></html>", max_results=5) == []


def test_web_search_missing_query():
    with pytest.raises(ToolError) as exc:
        asyncio.run(WebSearchTool().execute({"query": "  "}, _ctx()))
    assert exc.value.code == "MISSING_QUERY"


def test_web_search_execute_with_mock():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_HTML

    with patch("app.tools.core.web_search.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = asyncio.run(WebSearchTool().execute({"query": "example docs", "max_results": 5}, _ctx()))

    assert result["count"] == 2
    assert result["results"][0]["url"] == "https://example.com/docs"


def test_web_search_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = ""

    with patch("app.tools.core.web_search.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(ToolError) as exc:
            asyncio.run(WebSearchTool().execute({"query": "x"}, _ctx()))
    assert exc.value.code == "WEB_SEARCH_ERROR"
