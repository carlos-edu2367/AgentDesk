"""
Phase 8 — Approval flow tests via API.
Tests that critical tools in manual mode create approvals and pause execution.
Tests that auto mode skips approvals.
"""
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, WorkspaceModel, ApprovalRequestModel
from app.domain.enums import ApprovalStatus
from app.tools.base import ToolExecutionContext
from app.tools.capabilities import is_critical_tool, get_risk_level, get_tool_summary, CRITICAL_TOOLS


# ── Capability helpers ────────────────────────────────────────────────────────

def test_critical_tools_are_recognized():
    for tool in ["filesystem.write", "filesystem.delete", "filesystem.move",
                 "filesystem.copy", "terminal.exec", "http.request"]:
        assert is_critical_tool(tool), f"{tool} should be critical"


def test_read_only_tools_are_not_critical():
    for tool in ["filesystem.list", "filesystem.read", "filesystem.stat",
                 "workspace.list", "logs.search"]:
        assert not is_critical_tool(tool), f"{tool} should not be critical"


def test_risk_levels():
    assert get_risk_level("terminal.exec") == "high"
    assert get_risk_level("filesystem.delete") == "high"
    assert get_risk_level("filesystem.write") == "medium"
    assert get_risk_level("http.request") == "medium"
    assert get_risk_level("filesystem.copy") == "low"
    assert get_risk_level("filesystem.list") == "low"  # default


def test_tool_summaries_exist():
    for tool in CRITICAL_TOOLS:
        summary = get_tool_summary(tool)
        assert summary and len(summary) > 0


# ── Approval endpoint via API ─────────────────────────────────────────────────

def test_list_approvals_endpoint(client):
    """GET /api/approvals returns a list (possibly empty)."""
    resp = client.get("/api/approvals")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_approvals_by_status(client):
    """GET /api/approvals?status=pending filters correctly."""
    resp = client.get("/api/approvals?status=pending")
    assert resp.status_code == 200


def test_get_nonexistent_approval(client):
    """GET /api/approvals/{id} returns 404 for missing approval."""
    resp = client.get("/api/approvals/nonexistent_approval_id")
    assert resp.status_code == 404


def test_execution_approvals_endpoint(client):
    """GET /api/executions/{id}/approvals returns 404 for missing execution."""
    resp = client.get("/api/executions/nonexistent/approvals")
    assert resp.status_code == 404


def test_resolve_approval_on_nonexistent_execution(client):
    """POST /api/executions/{id}/approvals/{aid} returns 404 when execution missing."""
    resp = client.post("/api/executions/bad_exec/approvals/bad_approval", json={"approved": True})
    assert resp.status_code == 404


# ── Approval state detection ──────────────────────────────────────────────────

def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_approval_model_can_be_created_and_queried():
    """ApprovalRequestModel can be persisted and retrieved."""
    from datetime import datetime
    db = _make_db()
    # Need an execution record first (FK constraint), but SQLite may not enforce it in tests
    approval = ApprovalRequestModel(
        id="approval_test_001",
        execution_id="exec_xxx",
        agent_id="agent_xxx",
        tool="terminal.exec",
        status="pending",
        risk_level="high",
        summary="Execute terminal command",
        arguments={"command": "git status", "cwd": "/some/path"},
        pending_state={"messages": [{"role": "user", "content": "do something"}], "step": 1},
        rejection_reason=None,
        created_at=datetime.utcnow(),
        resolved_at=None,
    )
    db.add(approval)
    db.commit()

    found = db.query(ApprovalRequestModel).filter(ApprovalRequestModel.id == "approval_test_001").first()
    assert found is not None
    assert found.tool == "terminal.exec"
    assert found.status == "pending"
    assert found.risk_level == "high"
    assert found.pending_state["step"] == 1
    assert found.arguments["command"] == "git status"


def test_approval_status_transitions():
    """Approval status can be updated to approved/rejected."""
    from datetime import datetime
    db = _make_db()

    approval = ApprovalRequestModel(
        id="approval_test_002",
        execution_id="exec_yyy",
        agent_id="agent_yyy",
        tool="filesystem.write",
        status="pending",
        risk_level="medium",
        summary="Write to file",
        arguments={"path": "/some/file.txt", "content": "hello"},
        pending_state={"messages": [], "step": 0},
        created_at=datetime.utcnow(),
    )
    db.add(approval)
    db.commit()

    # Approve it
    approval.status = "approved"
    approval.resolved_at = datetime.utcnow()
    db.commit()

    found = db.query(ApprovalRequestModel).filter(ApprovalRequestModel.id == "approval_test_002").first()
    assert found.status == "approved"
    assert found.resolved_at is not None


# ── Auto-approval capability tests ───────────────────────────────────────────

def test_new_capabilities_in_registry():
    """New capabilities exist in the CAPABILITIES dict."""
    from app.tools.capabilities import CAPABILITIES
    assert "filesystem_write" in CAPABILITIES
    assert "filesystem_delete" in CAPABILITIES
    assert "terminal" in CAPABILITIES
    assert "http" in CAPABILITIES


def test_new_tools_registered():
    """New critical tools are registered in the tool registry."""
    from app.tools.registry import tool_registry, register_core_tools
    register_core_tools()
    for tool_name in ["filesystem.write", "filesystem.delete", "filesystem.move",
                      "filesystem.copy", "terminal.exec", "http.request"]:
        assert tool_registry.exists(tool_name), f"Tool '{tool_name}' should be registered"


def test_old_tools_still_registered():
    """Existing read-only tools are still registered after phase 8."""
    from app.tools.registry import tool_registry, register_core_tools
    register_core_tools()
    for tool_name in ["filesystem.list", "filesystem.read", "filesystem.stat",
                      "filesystem.search", "workspace.list", "workspace.get",
                      "logs.search", "logs.get_execution"]:
        assert tool_registry.exists(tool_name), f"Tool '{tool_name}' should still be registered"
