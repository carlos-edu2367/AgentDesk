"""Tests for terminal.exec background mode + terminal.poll."""
import asyncio
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, WorkspaceModel
from app.tools.base import ToolExecutionContext
from app.tools.core.terminal import TerminalExecTool, TerminalPollTool
from app.tools.errors import ToolError


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _ws(db, ws_id, path, execute=True):
    db.add(WorkspaceModel(id=ws_id, name=ws_id, paths=[path],
                          permissions={"read": True, "write": True, "delete": False, "execute": execute}))
    db.commit()


def _ctx(db, ws_ids):
    return ToolExecutionContext(execution_id="e", agent_id="a", workspace_ids=ws_ids, db=db, approval_mode="auto")


async def _poll_until_done(ctx, process_id, tries=50):
    poll = TerminalPollTool()
    for _ in range(tries):
        res = await poll.execute({"process_id": process_id}, ctx)
        if res["status"] == "exited":
            return res
        await asyncio.sleep(0.1)
    return res


def test_background_exec_returns_process_id_and_polls_to_completion(tmp_path):
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    ctx = _ctx(db, ["ws1"])

    # Spawn and poll on the SAME event loop — production runs everything on the
    # uvicorn loop, and an asyncio subprocess is only reaped by its own loop.
    async def scenario():
        started = await TerminalExecTool().execute(
            {"command": "echo hello-bg", "cwd": str(tmp_path), "background": True}, ctx,
        )
        final = await _poll_until_done(ctx, started["process_id"])
        return started, final

    started, final = asyncio.run(scenario())
    assert started["background"] is True
    assert started["status"] == "running"
    assert started["process_id"]
    assert final["status"] == "exited"
    assert final["exit_code"] == 0
    assert "hello-bg" in final["stdout"]


def test_poll_unknown_process(tmp_path):
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    with pytest.raises(ToolError) as exc:
        asyncio.run(TerminalPollTool().execute({"process_id": "proc_nope"}, _ctx(db, ["ws1"])))
    assert exc.value.code == "PROCESS_NOT_FOUND"


def test_background_kill(tmp_path):
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    ctx = _ctx(db, ["ws1"])

    # A long-running command we will kill.
    if os.name == "nt":
        cmd = "ping -n 30 127.0.0.1 > nul"
    else:
        cmd = "sleep 30"

    async def scenario():
        started = await TerminalExecTool().execute(
            {"command": cmd, "cwd": str(tmp_path), "background": True}, ctx,
        )
        pid = started["process_id"]
        poll = TerminalPollTool()
        await poll.execute({"process_id": pid, "kill": True}, ctx)
        for _ in range(50):
            res = await poll.execute({"process_id": pid}, ctx)
            if res["status"] == "exited":
                return res
            await asyncio.sleep(0.1)
        return res

    result = asyncio.run(scenario())
    assert result["status"] == "exited"


def test_foreground_still_works(tmp_path):
    """background defaults to False — existing behavior intact."""
    db = _make_db(); _ws(db, "ws1", str(tmp_path))
    result = asyncio.run(TerminalExecTool().execute(
        {"command": "echo fg", "cwd": str(tmp_path)}, _ctx(db, ["ws1"]),
    ))
    assert result["background"] is False
    assert result["exit_code"] == 0
    assert "fg" in result["stdout"]
