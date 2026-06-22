import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models import SkillModel
from app.domain.enums import ApprovalMode, EventType, ExecutionStatus, ExecutionType, ProviderType
from app.domain.schemas import Agent, Execution, ModelConfig, Provider
from app.runtime.agent_runtime import AgentRuntime


def _skill_payload(skill_id: str = "skill_report_writer", prompt: str = "Write clear reports."):
    return {
        "id": skill_id,
        "name": "Report Writer",
        "version": "0.1.0",
        "description": "Helps write reports.",
        "tags": ["writing", "reports"],
        "prompt": prompt,
        "examples": [],
    }


def _provider():
    return Provider(id="provider_1", type=ProviderType.OLLAMA, name="Mock Provider")


def _execution(execution_type=ExecutionType.AGENT, target_id="agent_1"):
    return Execution(
        id="exec_1",
        type=execution_type,
        target_id=target_id,
        user_input="Create a report",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )


def _agent(agent_id="agent_1", skills=None):
    return Agent(
        id=agent_id,
        name="Agent",
        model_config=ModelConfig(provider_id="provider_1", model="mock"),
        skills=skills or [],
        memory_config={"use_global": False, "use_agent_memory": False, "use_team_memory": True},
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )


def test_skill_crud_validates_prompt_and_id(client):
    response = client.post("/api/skills", json=_skill_payload())
    assert response.status_code == 200
    created = response.json()
    assert created["id"] == "skill_report_writer"
    assert created["prompt"] == "Write clear reports."

    list_response = client.get("/api/skills")
    assert list_response.status_code == 200
    listed = list_response.json()
    # The created custom skill is present alongside the seeded builtin skills.
    assert "skill_report_writer" in [skill["id"] for skill in listed]
    created_row = next(s for s in listed if s["id"] == "skill_report_writer")
    assert created_row["origin"] == "custom"
    assert any(s["origin"] == "builtin" for s in listed)

    update_response = client.put("/api/skills/skill_report_writer", json={"prompt": "Use summary, findings, risks."})
    assert update_response.status_code == 200
    assert update_response.json()["prompt"] == "Use summary, findings, risks."

    assert client.post("/api/skills", json=_skill_payload("invalid id")).status_code == 422
    assert client.post("/api/skills", json=_skill_payload("skill_empty", "   ")).status_code == 422

    delete_response = client.delete("/api/skills/skill_report_writer")
    assert delete_response.status_code == 200
    assert client.get("/api/skills/skill_report_writer").status_code == 404


def test_skill_import_export_and_no_overwrite_without_flag(client):
    response = client.post("/api/skills/import", json={"skill": _skill_payload()})
    assert response.status_code == 200
    assert response.json()["id"] == "skill_report_writer"

    duplicate = client.post("/api/skills/import", json={"skill": _skill_payload(prompt="Changed")})
    assert duplicate.status_code == 409

    overwrite = client.post("/api/skills/import?overwrite=true", json={"skill": _skill_payload(prompt="Changed")})
    assert overwrite.status_code == 200
    assert overwrite.json()["prompt"] == "Changed"

    exported = client.get("/api/skills/skill_report_writer/export")
    assert exported.status_code == 200
    assert exported.json() == {**_skill_payload(prompt="Changed"), "origin": "custom"}

    invalid = client.post("/api/skills/import", json={"skill": {"id": "skill_bad"}})
    assert invalid.status_code == 422


def test_skill_agent_and_team_associations(client):
    skill = client.post("/api/skills", json=_skill_payload()).json()
    provider = client.post("/api/providers", json={"type": "ollama", "name": "Ollama"}).json()
    agent = client.post("/api/agents", json={
        "name": "Agent",
        "model_config": {"provider_id": provider["id"], "model": "mock"},
    }).json()
    team = client.post("/api/teams", json={
        "name": "Team",
        "leader_agent_id": agent["id"],
        "member_agent_ids": [],
    }).json()

    assign_agent = client.post(f"/api/agents/{agent['id']}/skills/{skill['id']}")
    assert assign_agent.status_code == 200
    assert client.get(f"/api/agents/{agent['id']}/skills").json()[0]["id"] == skill["id"]

    replace_agent = client.put(f"/api/agents/{agent['id']}/skills", json={"skill_ids": []})
    assert replace_agent.status_code == 200
    assert client.get(f"/api/agents/{agent['id']}/skills").json() == []

    assign_team = client.post(f"/api/teams/{team['id']}/skills/{skill['id']}")
    assert assign_team.status_code == 200
    assert client.get(f"/api/teams/{team['id']}/skills").json()[0]["id"] == skill["id"]

    remove_team = client.delete(f"/api/teams/{team['id']}/skills/{skill['id']}")
    assert remove_team.status_code == 200
    assert client.get(f"/api/teams/{team['id']}/skills").json() == []


@pytest.mark.asyncio
async def test_runtime_injects_agent_and_team_skills_without_duplicates(client):
    from app.db.database import SessionLocal

    client.post("/api/skills", json=_skill_payload("skill_shared", "Shared behavior."))
    client.post("/api/skills", json=_skill_payload("skill_agent", "Agent behavior."))
    db = SessionLocal()
    try:
        db.add(SkillModel(id="skill_team", name="Team Skill", version="0.1.0", description="", tags=[], prompt="Team behavior.", examples=[]))
        db.commit()

        mock_provider = AsyncMock()
        mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))

        with patch("app.runtime.agent_runtime.provider_registry") as mock_registry:
            mock_registry.get.return_value = mock_provider
            runtime = AgentRuntime(db_session=db)
            agent = _agent(skills=["skill_agent", "skill_shared"])
            execution = _execution(ExecutionType.TEAM, "team_1")

            events = []
            async for event in runtime.run(
                agent,
                execution,
                _provider(),
                stream=False,
                runtime_options={"team_id": "team_1", "team_skill_ids": ["skill_shared", "skill_team"]},
            ):
                events.append(event)
    finally:
        db.close()

    prompt = next(e for e in events if e.type == EventType.PROMPT_BUILT).content["messages"][0]["content"]
    assert prompt.count("[ACTIVE SKILL: Report Writer | skill_shared]") == 1
    assert "[ACTIVE SKILL: Report Writer | skill_agent]" in prompt
    assert "[ACTIVE SKILL: Team Skill" in prompt
    assert any(e.type == EventType.SKILLS_LOADED for e in events)
    assert any(e.type == EventType.SKILL_INJECTED for e in events)


@pytest.mark.asyncio
async def test_runtime_truncates_skill_context(client):
    from app.db.database import SessionLocal

    long_prompt = "x" * 100
    for idx in range(12):
        client.post("/api/skills", json=_skill_payload(f"skill_{idx}", long_prompt))

    db = SessionLocal()
    try:
        mock_provider = AsyncMock()
        mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))

        with patch("app.runtime.agent_runtime.provider_registry") as mock_registry:
            mock_registry.get.return_value = mock_provider
            runtime = AgentRuntime(db_session=db)
            agent = _agent(skills=[f"skill_{idx}" for idx in range(12)])

            events = []
            async for event in runtime.run(agent, _execution(), _provider(), stream=False):
                events.append(event)
    finally:
        db.close()

    prompt = next(e for e in events if e.type == EventType.PROMPT_BUILT).content["messages"][0]["content"]
    assert prompt.count("[ACTIVE SKILL:") == 10
    assert prompt.count("[ACTIVE SKILL:") <= 10
    assert any(e.type == EventType.SKILLS_TRUNCATED for e in events)
