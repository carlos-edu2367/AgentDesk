"""Tests for filesystem.edit — exact-string replacement (avoids rewriting whole
files, which is what triggers max_tokens truncation)."""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, WorkspaceModel
from app.tools.base import ToolExecutionContext
from app.tools.core.filesystem_edit import FilesystemEditTool
from app.tools.errors import ToolError, PathOutOfWorkspaceError


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _create_workspace(db, ws_id, path, read=True, write=True, delete=False, execute=False):
    ws = WorkspaceModel(
        id=ws_id,
        name=f"ws-{ws_id}",
        paths=[path],
        permissions={"read": read, "write": write, "delete": delete, "execute": execute},
    )
    db.add(ws)
    db.commit()
    return ws


def _ctx(db, ws_ids):
    return ToolExecutionContext(
        execution_id="exec_test", agent_id="agent_test",
        workspace_ids=ws_ids, db=db, approval_mode="auto",
    )


def test_edit_replaces_unique_string(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), write=True)
    f = tmp_path / "main.js"
    f.write_text("const x = 1;\nconst y = 2;\n", encoding="utf-8")

    result = asyncio.run(FilesystemEditTool().execute(
        {"path": str(f), "old_string": "const y = 2;", "new_string": "const y = 42;"},
        _ctx(db, ["ws1"]),
    ))

    assert result["replacements"] == 1
    assert f.read_text(encoding="utf-8") == "const x = 1;\nconst y = 42;\n"


def test_edit_string_not_found(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), write=True)
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")

    with pytest.raises(ToolError) as exc:
        asyncio.run(FilesystemEditTool().execute(
            {"path": str(f), "old_string": "missing", "new_string": "x"},
            _ctx(db, ["ws1"]),
        ))
    assert exc.value.code == "STRING_NOT_FOUND"


def test_edit_string_not_unique_requires_replace_all(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), write=True)
    f = tmp_path / "a.txt"
    f.write_text("foo foo foo", encoding="utf-8")

    with pytest.raises(ToolError) as exc:
        asyncio.run(FilesystemEditTool().execute(
            {"path": str(f), "old_string": "foo", "new_string": "bar"},
            _ctx(db, ["ws1"]),
        ))
    assert exc.value.code == "STRING_NOT_UNIQUE"


def test_edit_replace_all(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), write=True)
    f = tmp_path / "a.txt"
    f.write_text("foo foo foo", encoding="utf-8")

    result = asyncio.run(FilesystemEditTool().execute(
        {"path": str(f), "old_string": "foo", "new_string": "bar", "replace_all": True},
        _ctx(db, ["ws1"]),
    ))
    assert result["replacements"] == 3
    assert f.read_text(encoding="utf-8") == "bar bar bar"


def test_edit_no_change_when_identical(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), write=True)
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")

    with pytest.raises(ToolError) as exc:
        asyncio.run(FilesystemEditTool().execute(
            {"path": str(f), "old_string": "x", "new_string": "x"},
            _ctx(db, ["ws1"]),
        ))
    assert exc.value.code == "NO_CHANGE"


def test_edit_requires_write_permission(tmp_path):
    db = _make_db()
    # read-only workspace → no writable paths → path rejected.
    _create_workspace(db, "ws1", str(tmp_path), write=False)
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")

    with pytest.raises(PathOutOfWorkspaceError):
        asyncio.run(FilesystemEditTool().execute(
            {"path": str(f), "old_string": "hello", "new_string": "bye"},
            _ctx(db, ["ws1"]),
        ))


def test_edit_missing_file(tmp_path):
    db = _make_db()
    _create_workspace(db, "ws1", str(tmp_path), write=True)

    with pytest.raises(ToolError) as exc:
        asyncio.run(FilesystemEditTool().execute(
            {"path": str(tmp_path / "nope.txt"), "old_string": "a", "new_string": "b"},
            _ctx(db, ["ws1"]),
        ))
    assert exc.value.code == "PATH_NOT_FOUND"
