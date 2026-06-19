"""
Phase 8 — Terminal and HTTP tool tests.
"""
import asyncio
import os
import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, WorkspaceModel
from app.tools.base import ToolExecutionContext
from app.tools.core.terminal import TerminalExecTool
from app.tools.core.http_tool import HttpRequestTool, _mask_sensitive_headers
from app.tools.errors import ToolError


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _create_workspace(db, ws_id, path, execute=False, read=True, write=False, delete=False):
    ws = WorkspaceModel(
        id=ws_id,
        name=f"ws-{ws_id}",
        paths=[path],
        permissions={"read": read, "write": write, "delete": delete, "execute": execute},
    )
    db.add(ws)
    db.commit()
    return ws


def _ctx(db, ws_ids, approval_mode="auto"):
    return ToolExecutionContext(
        execution_id="exec_test",
        agent_id="agent_test",
        workspace_ids=ws_ids,
        db=db,
        approval_mode=approval_mode,
    )


# ── terminal.exec tests ───────────────────────────────────────────────────────

def test_terminal_exec_basic(tmp_path):
    """terminal.exec returns stdout/stderr/exit_code."""
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), execute=True)
    ctx = _ctx(db, ["ws1"])
    tool = TerminalExecTool()

    if os.name == "nt":
        cmd = "echo hello"
    else:
        cmd = "echo hello"

    result = asyncio.run(tool.execute({
        "command": cmd,
        "cwd": str(tmp_path),
        "timeout_seconds": 10,
    }, ctx))

    assert "hello" in result["stdout"]
    assert result["exit_code"] == 0
    assert result["duration_ms"] >= 0


def test_terminal_exec_blocked_outside_workspace(tmp_path):
    """terminal.exec fails if cwd is outside workspace."""
    db = _make_db()
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _create_workspace(db, "ws1", str(ws_dir), execute=True)
    ctx = _ctx(db, ["ws1"])
    tool = TerminalExecTool()

    with pytest.raises((ToolError, Exception)):
        asyncio.run(tool.execute({
            "command": "echo hi",
            "cwd": str(outside),
        }, ctx))


def test_terminal_exec_requires_execute_permission(tmp_path):
    """terminal.exec fails if workspace doesn't have execute=True."""
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), execute=False)
    ctx = _ctx(db, ["ws1"])
    tool = TerminalExecTool()

    with pytest.raises((ToolError, Exception)):
        asyncio.run(tool.execute({
            "command": "echo hi",
            "cwd": str(tmp_path),
        }, ctx))


def test_terminal_exec_requires_cwd():
    """terminal.exec fails without cwd."""
    db = _make_db()
    ctx = _ctx(db, [])
    tool = TerminalExecTool()

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool.execute({"command": "echo hi"}, ctx))
    assert "cwd" in exc_info.value.message.lower()


def test_terminal_exec_requires_command(tmp_path):
    """terminal.exec fails without command."""
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), execute=True)
    ctx = _ctx(db, ["ws1"])
    tool = TerminalExecTool()

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool.execute({"cwd": str(tmp_path)}, ctx))
    assert "command" in exc_info.value.message.lower()


def test_terminal_exec_stdout_truncated(tmp_path):
    """Long stdout is truncated in result."""
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), execute=True)
    ctx = _ctx(db, ["ws1"])
    tool = TerminalExecTool()

    if os.name == "nt":
        # Generate large output on Windows
        cmd = "python -c \"print('x' * 10000)\""
    else:
        cmd = "python3 -c \"print('x' * 10000)\""

    try:
        result = asyncio.run(tool.execute({
            "command": cmd,
            "cwd": str(tmp_path),
            "timeout_seconds": 15,
        }, ctx))
        # stdout should be at most 4000 bytes
        assert len(result["stdout"]) <= 4000 + 100  # some tolerance
    except ToolError:
        pytest.skip("Python not available in PATH for this test")


# ── http.request tests ────────────────────────────────────────────────────────

def test_http_request_invalid_method():
    """http.request rejects invalid HTTP methods."""
    db = _make_db()
    ctx = _ctx(db, [])
    tool = HttpRequestTool()

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool.execute({
            "method": "HACK",
            "url": "https://example.com",
        }, ctx))
    assert "method" in exc_info.value.message.lower()


def test_http_request_missing_url():
    """http.request fails without URL."""
    db = _make_db()
    ctx = _ctx(db, [])
    tool = HttpRequestTool()

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool.execute({"method": "GET"}, ctx))
    assert "url" in exc_info.value.message.lower()


def test_http_sensitive_headers_masked():
    """Sensitive headers are masked in audit logs."""
    headers = {
        "Authorization": "Bearer secret-token",
        "X-Api-Key": "my-key",
        "Content-Type": "application/json",
        "User-Agent": "AgentDesk/1.0",
    }
    masked = _mask_sensitive_headers(headers)
    assert masked["Authorization"] == "***"
    assert masked["X-Api-Key"] == "***"
    assert masked["Content-Type"] == "application/json"
    assert masked["User-Agent"] == "AgentDesk/1.0"


def test_http_request_with_mock():
    """http.request returns status_code, headers, body."""
    db = _make_db()
    ctx = _ctx(db, [])
    tool = HttpRequestTool()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"ok": true}'

    async def mock_request(*args, **kwargs):
        return mock_response

    with patch("app.tools.core.http_tool.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = asyncio.run(tool.execute({
            "method": "GET",
            "url": "https://example.com",
        }, ctx))

    assert result["status_code"] == 200
    assert result["body"] == '{"ok": true}'
    assert not result["body_truncated"]


def test_http_request_body_truncation():
    """http.request truncates large body in response."""
    db = _make_db()
    ctx = _ctx(db, [])
    tool = HttpRequestTool()

    large_body = "x" * 250_000

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.text = large_body

    with patch("app.tools.core.http_tool.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = asyncio.run(tool.execute({
            "method": "GET",
            "url": "https://example.com",
        }, ctx))

    assert len(result["body"]) == 200_000
    assert result["body_truncated"] is True


# ── General security tests ────────────────────────────────────────────────────

def test_write_preview_is_truncated(tmp_path):
    """filesystem.write does not store full content in result, only preview."""
    from app.tools.core.filesystem_write import FilesystemWriteTool
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemWriteTool()
    big_content = "z" * 10_000
    target = tmp_path / "big.txt"
    result = asyncio.run(tool.execute({
        "path": str(target),
        "content": big_content,
    }, ctx))
    assert len(result["preview"]) <= 2_000
    assert result["content_truncated_in_preview"] is True


def test_nonexistent_tool_raises_not_found():
    """Trying to use a non-registered tool raises ToolNotFoundError."""
    from app.tools.errors import ToolNotFoundError
    from app.tools.registry import tool_registry
    with pytest.raises(ToolNotFoundError):
        tool_registry.get("fake.tool.that.does.not.exist")
