"""Tests for filesystem.grep — content search by regex (so the agent can locate
code without reading whole files into context)."""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, WorkspaceModel
from app.tools.base import ToolExecutionContext
from app.tools.core.filesystem_grep import FilesystemGrepTool
from app.tools.errors import ToolError, PathOutOfWorkspaceError


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _create_workspace(db, ws_id, path, read=True, write=False, delete=False, execute=False):
    ws = WorkspaceModel(
        id=ws_id, name=f"ws-{ws_id}", paths=[path],
        permissions={"read": read, "write": write, "delete": delete, "execute": execute},
    )
    db.add(ws); db.commit()
    return ws


def _ctx(db, ws_ids):
    return ToolExecutionContext(
        execution_id="exec_test", agent_id="agent_test",
        workspace_ids=ws_ids, db=db, approval_mode="auto",
    )


def test_grep_finds_matching_lines_with_line_numbers(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path))
    (tmp_path / "main.js").write_text("const a = 1;\nclass Game {}\nconst b = 2;\n", encoding="utf-8")

    result = asyncio.run(FilesystemGrepTool().execute(
        {"path": str(tmp_path), "pattern": r"class\s+\w+"},
        _ctx(db, ["ws1"]),
    ))

    assert result["count"] == 1
    m = result["results"][0]
    assert m["line"] == 2
    assert "class Game" in m["text"]
    assert m["path"].endswith("main.js")


def test_grep_glob_filters_files(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path))
    (tmp_path / "a.js").write_text("TODO fix\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("TODO fix\n", encoding="utf-8")

    result = asyncio.run(FilesystemGrepTool().execute(
        {"path": str(tmp_path), "pattern": "TODO", "glob": "*.js"},
        _ctx(db, ["ws1"]),
    ))

    assert result["count"] == 1
    assert result["results"][0]["path"].endswith("a.js")


def test_grep_case_insensitive(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path))
    (tmp_path / "a.txt").write_text("Hello World\n", encoding="utf-8")

    result = asyncio.run(FilesystemGrepTool().execute(
        {"path": str(tmp_path), "pattern": "hello", "case_insensitive": True},
        _ctx(db, ["ws1"]),
    ))
    assert result["count"] == 1


def test_grep_invalid_regex(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path))
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")

    with pytest.raises(ToolError) as exc:
        asyncio.run(FilesystemGrepTool().execute(
            {"path": str(tmp_path), "pattern": "([unclosed"},
            _ctx(db, ["ws1"]),
        ))
    assert exc.value.code == "INVALID_PATTERN"


def test_grep_truncates_at_max_results(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path))
    (tmp_path / "a.txt").write_text("\n".join("match" for _ in range(10)), encoding="utf-8")

    result = asyncio.run(FilesystemGrepTool().execute(
        {"path": str(tmp_path), "pattern": "match", "max_results": 3},
        _ctx(db, ["ws1"]),
    ))
    assert result["count"] == 3
    assert result["truncated"] is True


def test_grep_skips_binary_files(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path))
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01\x02\xff\xfe")
    (tmp_path / "a.txt").write_text("needle\n", encoding="utf-8")

    result = asyncio.run(FilesystemGrepTool().execute(
        {"path": str(tmp_path), "pattern": "needle"},
        _ctx(db, ["ws1"]),
    ))
    assert result["count"] == 1
    assert result["results"][0]["path"].endswith("a.txt")


def test_grep_missing_dir(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path))
    with pytest.raises(ToolError) as exc:
        asyncio.run(FilesystemGrepTool().execute(
            {"path": str(tmp_path / "nope"), "pattern": "x"},
            _ctx(db, ["ws1"]),
        ))
    assert exc.value.code == "PATH_NOT_FOUND"


def test_grep_rejects_path_outside_workspace(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path / "sub"))
    (tmp_path / "sub").mkdir()
    with pytest.raises(PathOutOfWorkspaceError):
        asyncio.run(FilesystemGrepTool().execute(
            {"path": str(tmp_path), "pattern": "x"},
            _ctx(db, ["ws1"]),
        ))
