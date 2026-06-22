from datetime import datetime, timedelta

from app.db.models import (
    ApprovalRequestModel,
    AuditLogModel,
    ExecutionEventModel,
    ExecutionModel,
)


def _seed_execution(db, execution_id="execution_phase14", status="completed", created_at=None):
    now = created_at or datetime.utcnow()
    execution = ExecutionModel(
        id=execution_id,
        type="agent",
        target_id="agent_alpha",
        user_input="Run with Authorization: Bearer abc123456789",
        status=status,
        approval_mode="auto",
        workspace_ids=[],
        created_at=now,
        updated_at=now,
        completed_at=now if status in {"completed", "failed", "cancelled"} else None,
        result="Final token sk-or-v1-abc123456789",
    )
    db.add(execution)
    db.add(ExecutionEventModel(
        id=f"event_{execution_id}_tool",
        execution_id=execution_id,
        type="tool_executed",
        source="tool",
        source_id="terminal.exec",
        content={
            "tool": "terminal.exec",
            "arguments": {"Authorization": "Bearer abc123456789"},
            "result_preview": "x" * 5000,
        },
        created_at=now,
    ))
    db.add(ExecutionEventModel(
        id=f"event_{execution_id}_memory",
        execution_id=execution_id,
        type="memory_usage_recorded",
        source="runtime",
        source_id="agent_alpha",
        content={"memory_ids": ["mem_1"]},
        created_at=now,
    ))
    db.add(ApprovalRequestModel(
        id=f"approval_{execution_id}",
        execution_id=execution_id,
        agent_id="agent_alpha",
        tool="terminal.exec",
        status="approved",
        risk_level="high",
        summary="Approved terminal",
        arguments={"token": "abc123456789"},
        pending_state={},
        created_at=now,
        resolved_at=now,
    ))
    db.add(AuditLogModel(
        id=f"audit_{execution_id}",
        execution_id=execution_id,
        agent_id="agent_alpha",
        event_type="tool_executed",
        risk_level="high",
        summary="Executed terminal.exec",
        data={
            "tool": "terminal.exec",
            "source": "core",
            "status": "success",
            "approval_mode": "auto",
            "api_key": "plain-secret-value",
        },
        created_at=now,
    ))
    db.add(AuditLogModel(
        id=f"audit_auto_{execution_id}",
        execution_id=execution_id,
        agent_id="agent_alpha",
        event_type="approval_auto_granted",
        risk_level="high",
        summary="Auto-approved terminal.exec",
        data={"tool": "terminal.exec", "approval_mode": "auto"},
        created_at=now,
    ))
    db.commit()
    return execution


def _db(client):
    override = next(iter(client.app.dependency_overrides.values()))
    return next(override())


def test_audit_api_lists_gets_filters_searches_and_paginates(client):
    db = _db(client)
    # Startup seeds builtin skills, which emits a skill_seeded audit entry.
    # Remove it so totals reflect only this test's execution data.
    db.query(AuditLogModel).filter(AuditLogModel.event_type == "skill_seeded").delete()
    db.commit()
    _seed_execution(db)

    listed = client.get("/api/audit").json()
    assert listed["total"] == 2
    assert listed["items"][0]["id"].startswith("audit_")
    assert "plain-secret-value" not in str(listed)

    audit_id = listed["items"][0]["id"]
    fetched = client.get(f"/api/audit/{audit_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == audit_id

    assert client.get("/api/audit?risk_level=high").json()["total"] == 2
    assert client.get("/api/audit?event_type=tool_executed").json()["total"] == 1
    assert client.get("/api/audit?execution_id=execution_phase14").json()["total"] == 2
    assert client.get("/api/audit?agent_id=agent_alpha").json()["total"] == 2
    assert client.get("/api/audit?tool=terminal.exec").json()["total"] == 2
    assert client.get("/api/audit?source=core").json()["total"] == 1
    assert client.get("/api/audit?status=success").json()["total"] == 1
    assert client.get("/api/audit?approval_mode=auto").json()["total"] == 2
    assert client.get("/api/audit?query=terminal").json()["total"] == 2

    page = client.get("/api/audit?limit=1&offset=1").json()
    assert page["total"] == 2
    assert page["limit"] == 1
    assert page["offset"] == 1
    assert len(page["items"]) == 1


def test_execution_detail_aggregates_events_audit_approvals_and_summary(client):
    db = _db(client)
    _seed_execution(db)

    response = client.get("/api/executions/execution_phase14/detail")

    assert response.status_code == 200
    detail = response.json()
    assert detail["execution"]["id"] == "execution_phase14"
    assert len(detail["events"]) == 2
    assert len(detail["audit_logs"]) == 2
    assert len(detail["approvals"]) == 1
    assert detail["artifacts"] == []
    assert detail["summary"]["total_events"] == 2
    assert detail["summary"]["total_audit_logs"] == 2
    assert detail["summary"]["tools_used"] == ["terminal.exec"]
    assert detail["summary"]["agents_involved"] == ["agent_alpha"]
    assert detail["summary"]["memories_used"] == ["mem_1"]
    assert detail["summary"]["approval_mode"] == "auto"
    assert detail["summary"]["critical_actions_count"] == 2
    assert detail["summary"]["auto_approved_count"] == 1
    assert detail["summary"]["manual_approved_count"] == 1


def test_execution_export_json_and_markdown_mask_and_truncate(client):
    db = _db(client)
    _seed_execution(db)

    json_response = client.post("/api/executions/execution_phase14/export", json={"format": "json"})
    assert json_response.status_code == 200
    json_payload = json_response.json()
    assert json_payload["format"] == "json"
    assert json_payload["path"].endswith(".json")
    assert "plain-secret-value" not in str(json_payload)
    assert "sk-or-v1-abc123456789" not in str(json_payload)
    assert "[truncated]" in str(json_payload)
    assert "events" in json_payload["content"]
    assert "audit_logs" in json_payload["content"]

    md_response = client.post("/api/executions/execution_phase14/export", json={"format": "markdown"})
    assert md_response.status_code == 200
    md_payload = md_response.json()
    assert md_payload["format"] == "markdown"
    assert md_payload["path"].endswith(".md")
    assert "# AgentDesk Execution Report" in md_payload["content"]
    assert "## Timeline" in md_payload["content"]
    assert "## Audit Logs" in md_payload["content"]
    assert "plain-secret-value" not in md_payload["content"]
    assert "sk-or-v1-abc123456789" not in md_payload["content"]
    assert "[truncated]" in md_payload["content"]


def test_cleanup_dry_run_real_and_running_safety(client):
    db = _db(client)
    old = datetime.utcnow() - timedelta(days=120)
    _seed_execution(db, execution_id="execution_old", status="completed", created_at=old)
    _seed_execution(db, execution_id="execution_running", status="running", created_at=old)

    dry_run = client.post("/api/logs/cleanup", json={
        "older_than_days": 90,
        "include_audit_logs": False,
        "include_execution_events": True,
        "dry_run": True,
    }).json()
    assert dry_run["dry_run"] is True
    assert dry_run["would_delete"]["execution_events"] == 2
    assert dry_run["would_delete"]["audit_logs"] == 0

    assert db.query(ExecutionEventModel).filter(ExecutionEventModel.execution_id == "execution_old").count() == 2

    real = client.post("/api/logs/cleanup", json={
        "older_than_days": 90,
        "include_audit_logs": False,
        "include_execution_events": True,
        "dry_run": False,
    }).json()
    assert real["dry_run"] is False
    assert real["deleted"]["execution_events"] == 2
    assert db.query(ExecutionEventModel).filter(ExecutionEventModel.execution_id == "execution_old").count() == 0
    assert db.query(ExecutionEventModel).filter(ExecutionEventModel.execution_id == "execution_running").count() == 2
    assert db.query(AuditLogModel).filter(AuditLogModel.execution_id == "execution_old").count() == 2
    assert db.query(AuditLogModel).filter(AuditLogModel.event_type == "logs_cleanup_executed").count() == 1


def test_mask_secrets_handles_nested_values_and_common_patterns():
    from app.domain.utils import mask_secrets

    masked = mask_secrets({
        "api_key": "abcdef1234567890",
        "headers": {
            "Authorization": "Bearer abc123456789",
            "Cookie": "sessionid=abcdef123456",
        },
        "nested": [
            "sk-or-v1-abc123456789",
            {"password": "super-password"},
        ],
    })

    text = str(masked)
    assert "abcdef1234567890" not in text
    assert "abc123456789" not in text
    assert "sessionid=abcdef123456" not in text
    assert "sk-or-v1-abc123456789" not in text
    assert "super-password" not in text
    assert "***" in text
