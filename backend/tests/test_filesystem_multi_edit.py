"""Tests for filesystem.multi_edit — several atomic edits to one file."""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, WorkspaceModel
from app.tools.base import ToolExecutionContext
from app.tools.core.filesystem_edit import FilesystemMultiEditTool
from app.tools.errors import ToolError


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _ws(db, ws_id, path, write=True):
    db.add(WorkspaceModel(id=ws_id, name=ws_id, paths=[path],
                          permissions={"read": True, "write": write, "delete": False, "execute": False}))
    db.commit()


def _ctx(db, ws_ids):
    return ToolExecutionContext(execution_id="e", agent_id="a", workspace_ids=ws_ids, db=db, approval_mode="auto")


def test_multi_edit_applies_all_in_order(tmp_path):
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    f = tmp_path / "a.txt"
    f.write_text("alpha beta gamma", encoding="utf-8")

    result = asyncio.run(FilesystemMultiEditTool().execute({
        "path": str(f),
        "edits": [
            {"old_string": "alpha", "new_string": "ALPHA"},
            {"old_string": "gamma", "new_string": "GAMMA"},
        ],
    }, _ctx(db, ["ws1"])))

    assert result["edits_applied"] == 2
    assert result["total_replacements"] == 2
    assert f.read_text(encoding="utf-8") == "ALPHA beta GAMMA"


def test_multi_edit_is_atomic_on_failure(tmp_path):
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    f = tmp_path / "a.txt"
    f.write_text("alpha beta", encoding="utf-8")

    with pytest.raises(ToolError) as exc:
        asyncio.run(FilesystemMultiEditTool().execute({
            "path": str(f),
            "edits": [
                {"old_string": "alpha", "new_string": "ALPHA"},
                {"old_string": "MISSING", "new_string": "x"},  # fails
            ],
        }, _ctx(db, ["ws1"])))

    assert exc.value.code == "STRING_NOT_FOUND"
    # Nothing written — file unchanged.
    assert f.read_text(encoding="utf-8") == "alpha beta"


def test_multi_edit_sequential_dependency(tmp_path):
    """Second edit operates on the result of the first."""
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    f = tmp_path / "a.txt"
    f.write_text("foo", encoding="utf-8")

    result = asyncio.run(FilesystemMultiEditTool().execute({
        "path": str(f),
        "edits": [
            {"old_string": "foo", "new_string": "bar"},
            {"old_string": "bar", "new_string": "baz"},
        ],
    }, _ctx(db, ["ws1"])))

    assert result["total_replacements"] == 2
    assert f.read_text(encoding="utf-8") == "baz"


def test_multi_edit_replace_all_in_one_edit(tmp_path):
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    f = tmp_path / "a.txt"
    f.write_text("x x x", encoding="utf-8")

    result = asyncio.run(FilesystemMultiEditTool().execute({
        "path": str(f),
        "edits": [{"old_string": "x", "new_string": "y", "replace_all": True}],
    }, _ctx(db, ["ws1"])))

    assert result["replacements_per_edit"] == [3]
    assert f.read_text(encoding="utf-8") == "y y y"


def test_multi_edit_empty_edits_rejected(tmp_path):
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")

    with pytest.raises(ToolError) as exc:
        asyncio.run(FilesystemMultiEditTool().execute(
            {"path": str(f), "edits": []}, _ctx(db, ["ws1"])))
    assert exc.value.code == "MISSING_EDITS"
