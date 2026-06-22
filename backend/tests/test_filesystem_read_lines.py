"""Tests for filesystem.read line-range mode (offset/limit) — lets the agent read
just the slice it needs to match an edit's old_string, without loading the file."""
import asyncio

import pytest
from pathlib import Path

from app.tools.base import ToolExecutionContext
from app.tools.core.filesystem import FilesystemReadTool
from app.tools.errors import ToolError


def _ctx(workspace_paths):
    ctx = ToolExecutionContext(
        execution_id="exec_test", agent_id="agent_test",
        workspace_ids=[], db=None,
    )
    ctx.get_workspace_paths = lambda: workspace_paths
    return ctx


def _write_numbered(tmp_path: Path, n: int) -> Path:
    f = tmp_path / "file.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return f


def test_read_offset_and_limit_returns_window(tmp_path):
    f = _write_numbered(tmp_path, 100)
    result = asyncio.run(FilesystemReadTool().execute(
        {"path": str(f), "offset": 10, "limit": 3}, _ctx([str(tmp_path)]),
    ))
    assert result["content"] == "line10\nline11\nline12"
    assert result["line_offset"] == 10
    assert result["lines_returned"] == 3
    assert result["total_lines"] == 100
    assert result["truncated"] is True  # more lines after the window


def test_read_offset_only_reads_to_end(tmp_path):
    f = _write_numbered(tmp_path, 5)
    result = asyncio.run(FilesystemReadTool().execute(
        {"path": str(f), "offset": 4}, _ctx([str(tmp_path)]),
    ))
    assert result["content"] == "line4\nline5"
    assert result["lines_returned"] == 2
    assert result["truncated"] is False


def test_read_limit_only_reads_from_start(tmp_path):
    f = _write_numbered(tmp_path, 5)
    result = asyncio.run(FilesystemReadTool().execute(
        {"path": str(f), "limit": 2}, _ctx([str(tmp_path)]),
    ))
    assert result["content"] == "line1\nline2"
    assert result["line_offset"] == 1
    assert result["lines_returned"] == 2


def test_read_offset_clamped_to_one(tmp_path):
    f = _write_numbered(tmp_path, 3)
    result = asyncio.run(FilesystemReadTool().execute(
        {"path": str(f), "offset": 0, "limit": 1}, _ctx([str(tmp_path)]),
    ))
    assert result["content"] == "line1"
    assert result["line_offset"] == 1


def test_read_offset_beyond_eof_returns_empty(tmp_path):
    f = _write_numbered(tmp_path, 3)
    result = asyncio.run(FilesystemReadTool().execute(
        {"path": str(f), "offset": 99}, _ctx([str(tmp_path)]),
    ))
    assert result["content"] == ""
    assert result["lines_returned"] == 0
    assert result["truncated"] is False


def test_read_without_offset_limit_is_unchanged(tmp_path):
    """Backward compatibility: plain read returns full content, no line metadata."""
    f = tmp_path / "a.txt"
    f.write_text("Hello World", encoding="utf-8")
    result = asyncio.run(FilesystemReadTool().execute(
        {"path": str(f)}, _ctx([str(tmp_path)]),
    ))
    assert result["content"] == "Hello World"
    assert result["truncated"] is False
    assert "line_offset" not in result
