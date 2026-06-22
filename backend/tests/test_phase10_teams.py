import time

from app.db.repositories.registry import execution_event_repo, execution_repo
from app.domain.enums import EventType, ExecutionStatus, ProviderType
from app.providers import provider_registry
from tests.mocks.mock_provider import MockProvider


def _provider_payload(text: str):
    return {
        "type": "ollama",
        "name": "Mock Provider",
        "enabled": True,
        "config": {"mock_response_text": text, "mock_chunks": [text]},
    }


def _agent_payload(name: str, provider_id: str, capabilities=None, subagents=None):
    return {
        "name": name,
        "model_config": {"provider_id": provider_id, "model": "mock"},
        "capabilities": capabilities or [],
        "subagents": subagents or {"can_call": True, "allowed_agent_ids": ["*"]},
        "memory_config": {"use_global": True, "use_agent_memory": True, "use_team_memory": True},
    }


def test_execute_team_via_api_runs_leader_managed_flow(client):
    provider_registry.register(ProviderType.OLLAMA, MockProvider)
    provider_resp = client.post("/api/providers", json=_provider_payload(
        '{"type":"final_answer","content":"placeholder"}'
    ))
    provider_id = provider_resp.json()["id"]

    client.post("/api/agents", json=_agent_payload(
        "Leader",
        provider_id,
        capabilities=["agent_control"],
        subagents={"can_call": True, "allowed_agent_ids": ["agent_member"]},
    ))
    # The generated ID is not predictable, so create deterministic records via API update pattern is not available.
    # Use direct DB IDs through the response bodies instead.
    leader_id = client.get("/api/agents").json()[0]["id"]

    provider_member_resp = client.post("/api/providers", json=_provider_payload(
        '{"type":"final_answer","content":"member result"}'
    ))
    member_provider_id = provider_member_resp.json()["id"]
    member_resp = client.post("/api/agents", json=_agent_payload("Member", member_provider_id))
    member_id = member_resp.json()["id"]

    client.put(f"/api/providers/{provider_id}", json={
        "config": {
            "mock_response_text": f'{{"type":"subagent_call","target_agent_id":"{member_id}","task":"Research the request"}}',
            "mock_chunks": [f'{{"type":"subagent_call","target_agent_id":"{member_id}","task":"Research the request"}}'],
        }
    })

    client.put(f"/api/agents/{leader_id}", json={
        "subagents": {"can_call": True, "allowed_agent_ids": [member_id]},
        "capabilities": ["agent_control"],
    })

    team_resp = client.post("/api/teams", json={
        "name": "Research Team",
        "leader_agent_id": leader_id,
        "member_agent_ids": [member_id],
        "execution_strategy": "leader_managed",
        "memory_config": {"use_global": True, "use_team_memory": True, "allow_member_memories": True},
    })
    team_id = team_resp.json()["id"]

    exec_resp = client.post("/api/executions/team", json={
        "team_id": team_id,
        "message": "Create a report",
        "approval_mode": "auto",
        "stream": False,
    })
    assert exec_resp.status_code == 200
    execution_id = exec_resp.json()["execution_id"]
    time.sleep(1)

    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        execution = execution_repo.get(db, id=execution_id)
        assert execution.status == ExecutionStatus.COMPLETED
        # Query the full event set for this execution: a leader can now run many
        # delegation steps, so a fixed 200-row cap could truncate the final
        # finalize/complete events.
        events = [
            e.type
            for e in db.query(execution_event_repo.model)
            .filter(execution_event_repo.model.execution_id == execution_id)
            .order_by(execution_event_repo.model.created_at.asc())
            .all()
        ]
    finally:
        db.close()

    assert EventType.TEAM_STARTED in events
    assert EventType.LEADER_STARTED in events
    assert EventType.SUBAGENT_CALL_REQUESTED in events
    assert EventType.MEMBER_COMPLETED in events
    assert EventType.LEADER_FINALIZED in events
    assert EventType.TEAM_COMPLETED in events
