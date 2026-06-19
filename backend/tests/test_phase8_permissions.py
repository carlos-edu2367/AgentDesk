"""
Phase 8 — Permission and workspace tests for critical tools.
Uses asyncio.run() for async tool execution — no pytest-asyncio required.
"""
import asyncio
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, WorkspaceModel
from app.tools.base import ToolExecutionContext
from app.tools.core.filesystem_write import (
    FilesystemWriteTool,
    FilesystemDeleteTool,
    FilesystemMoveTool,
    FilesystemCopyTool,
)
from app.tools.errors import ToolError, PathOutOfWorkspaceError
from app.permissions.gate import check_tool_permission
from app.tools.errors import ToolDeniedError, ToolNotFoundError


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _create_workspace(db, ws_id: str, path: str, read=True, write=False, delete=False, execute=False):
    ws = WorkspaceModel(
        id=ws_id,
        name=f"ws-{ws_id}",
        paths=[path],
        permissions={"read": read, "write": write, "delete": delete, "execute": execute},
    )
    db.add(ws)
    db.commit()
    return ws


def _ctx(db, ws_ids, approval_mode="manual"):
    return ToolExecutionContext(
        execution_id="exec_test",
        agent_id="agent_test",
        workspace_ids=ws_ids,
        db=db,
        approval_mode=approval_mode,
    )


# ── Permission Gate tests ─────────────────────────────────────────────────────

def test_agent_with_filesystem_write_capability_is_allowed():
    check_tool_permission("filesystem.write", ["filesystem_write"], [], [])


def test_agent_without_capability_is_denied():
    with pytest.raises(ToolDeniedError):
        check_tool_permission("filesystem.write", [], [], [])


def test_agent_without_filesystem_delete_capability_is_denied():
    with pytest.raises(ToolDeniedError):
        check_tool_permission("filesystem.delete", [], [], [])


def test_agent_with_filesystem_delete_capability_is_allowed():
    check_tool_permission("filesystem.delete", ["filesystem_delete"], [], [])


def test_blocked_tools_override_capability():
    with pytest.raises(ToolDeniedError):
        check_tool_permission("filesystem.write", ["filesystem_write"], [], ["filesystem.write"])


def test_explicit_tools_grant_access():
    check_tool_permission("filesystem.write", [], ["filesystem.write"], [])


def test_terminal_capability_allows_exec():
    check_tool_permission("terminal.exec", ["terminal"], [], [])


def test_http_capability_allows_request():
    check_tool_permission("http.request", ["http"], [], [])


def test_unknown_tool_raises_not_found():
    with pytest.raises(ToolNotFoundError):
        check_tool_permission("nonexistent.tool", ["filesystem_write"], [], [])


# ── filesystem.write workspace permission tests ───────────────────────────────

def test_write_allowed_when_workspace_has_write_permission(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemWriteTool()
    target = tmp_path / "output.txt"
    result = asyncio.run(tool.execute({"path": str(target), "content": "hello"}, ctx))
    assert result["bytes_written"] == 5
    assert target.read_text() == "hello"


def test_write_denied_when_workspace_has_no_write_permission(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=False)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemWriteTool()
    target = tmp_path / "output.txt"
    with pytest.raises((ToolError, PathOutOfWorkspaceError)):
        asyncio.run(tool.execute({"path": str(target), "content": "hello"}, ctx))


def test_write_denied_when_path_outside_workspace(tmp_path):
    db = _make_db()
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    _create_workspace(db, "ws1", str(ws_dir), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemWriteTool()
    outside = tmp_path / "outside.txt"
    with pytest.raises((ToolError, PathOutOfWorkspaceError)):
        asyncio.run(tool.execute({"path": str(outside), "content": "oops"}, ctx))


def test_write_mode_create_only_fails_if_file_exists(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemWriteTool()
    target = tmp_path / "existing.txt"
    target.write_text("original")
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool.execute({"path": str(target), "content": "new", "mode": "create_only"}, ctx))
    assert "exists" in exc_info.value.message.lower() or "FILE_EXISTS" in exc_info.value.code


def test_write_mode_append(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemWriteTool()
    target = tmp_path / "log.txt"
    target.write_text("line1\n")
    asyncio.run(tool.execute({"path": str(target), "content": "line2\n", "mode": "append"}, ctx))
    assert target.read_text() == "line1\nline2\n"


# ── filesystem.delete workspace permission tests ──────────────────────────────

def test_delete_allowed_when_workspace_has_delete_permission(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True, delete=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemDeleteTool()
    target = tmp_path / "todelete.txt"
    target.write_text("bye")
    result = asyncio.run(tool.execute({"path": str(target)}, ctx))
    assert result["deleted"] is True
    assert not target.exists()


def test_delete_denied_when_workspace_has_no_delete_permission(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True, delete=False)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemDeleteTool()
    target = tmp_path / "todelete.txt"
    target.write_text("bye")
    with pytest.raises((ToolError, PathOutOfWorkspaceError)):
        asyncio.run(tool.execute({"path": str(target)}, ctx))


def test_delete_directory_requires_recursive(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, delete=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemDeleteTool()
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool.execute({"path": str(subdir), "recursive": False}, ctx))
    assert "directory" in exc_info.value.message.lower()


def test_delete_cannot_delete_workspace_root(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, delete=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemDeleteTool()
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool.execute({"path": str(tmp_path), "recursive": True}, ctx))
    assert "root" in exc_info.value.message.lower() or "CANNOT_DELETE_ROOT" in exc_info.value.code


# ── filesystem.move workspace permission tests ────────────────────────────────

def test_move_requires_both_paths_in_workspace(tmp_path):
    db = _make_db()
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    _create_workspace(db, "ws1", str(ws_dir), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemMoveTool()
    source = ws_dir / "source.txt"
    source.write_text("data")
    outside = tmp_path / "outside.txt"
    with pytest.raises((ToolError, PathOutOfWorkspaceError)):
        asyncio.run(tool.execute({
            "source_path": str(source),
            "target_path": str(outside),
        }, ctx))


def test_move_works_within_workspace(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemMoveTool()
    source = tmp_path / "a.txt"
    target = tmp_path / "b.txt"
    source.write_text("data")
    result = asyncio.run(tool.execute({
        "source_path": str(source),
        "target_path": str(target),
    }, ctx))
    assert result["moved"] is True
    assert not source.exists()
    assert target.exists()


# ── filesystem.copy workspace permission tests ────────────────────────────────

def test_copy_requires_both_paths_in_workspace(tmp_path):
    db = _make_db()
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    _create_workspace(db, "ws1", str(ws_dir), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemCopyTool()
    source = ws_dir / "source.txt"
    source.write_text("data")
    outside = tmp_path / "outside.txt"
    with pytest.raises((ToolError, PathOutOfWorkspaceError)):
        asyncio.run(tool.execute({
            "source_path": str(source),
            "target_path": str(outside),
        }, ctx))


def test_copy_works_within_workspace(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemCopyTool()
    source = tmp_path / "orig.txt"
    target = tmp_path / "copy.txt"
    source.write_text("hello")
    result = asyncio.run(tool.execute({
        "source_path": str(source),
        "target_path": str(target),
    }, ctx))
    assert result["copied"] is True
    assert source.exists()
    assert target.read_text() == "hello"


def test_copy_no_overwrite_without_flag(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), read=True, write=True)
    ctx = _ctx(db, ["ws1"])
    tool = FilesystemCopyTool()
    source = tmp_path / "orig.txt"
    target = tmp_path / "copy.txt"
    source.write_text("hello")
    target.write_text("existing")
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool.execute({
            "source_path": str(source),
            "target_path": str(target),
            "overwrite": False,
        }, ctx))
    assert "exists" in exc_info.value.message.lower()
