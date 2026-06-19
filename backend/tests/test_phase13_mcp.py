import asyncio
import sys
from pathlib import Path

import pytest

from app.db.models import AgentModel, AuditLogModel, MCPServerModel
from app.domain.enums import ApprovalMode, ExecutionStatus, ExecutionType, ProviderType
from app.domain.schemas import Agent, Execution, ModelConfig, Provider
from app.permissions.gate import check_tool_permission
from app.runtime.agent_runtime import AgentRuntime
from app.tools.base import ToolExecutionContext
from app.tools.errors import ToolDeniedError, ToolError
from app.tools.registry import tool_registry


MOCK_SERVER = Path(__file__).parent / "mocks" / "mock_mcp_server.py"


def _mcp_payload(**overrides):
    payload = {
        "id": "filesystem",
        "name": "Filesystem MCP",
        "enabled": True,
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(MOCK_SERVER)],
        "env": {"API_KEY": "super-secret-token"},
    }
    payload.update(overrides)
    return payload


def test_mcp_crud_enable_disable_and_transport_validation(client):
    created = client.post("/api/mcp", json=_mcp_payload())

    assert created.status_code == 200
    assert created.json()["id"] == "filesystem"
    assert created.json()["transport"] == "stdio"

    listed = client.get("/api/mcp").json()
    assert [server["id"] for server in listed] == ["filesystem"]

    updated = client.put("/api/mcp/filesystem", json={"name": "Updated MCP", "args": ["--version"]})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated MCP"

    disabled = client.post("/api/mcp/filesystem/disable")
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    enabled = client.post("/api/mcp/filesystem/enable")
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True

    invalid = client.post("/api/mcp", json=_mcp_payload(id="bad", transport="http"))
    assert invalid.status_code == 422

    removed = client.delete("/api/mcp/filesystem")
    assert removed.status_code == 200
    assert client.get("/api/mcp/filesystem").status_code == 404


def test_mcp_test_connection_populates_tools_cache_registers_tools_and_masks_env(client):
    client.post("/api/mcp", json=_mcp_payload())

    response = client.post("/api/mcp/filesystem/test")

    assert response.status_code == 200
    data = response.json()
    assert data["server_id"] == "filesystem"
    assert data["status"] == "ok"
    assert data["tools"][0]["name"] == "mcp.filesystem.echo"
    assert data["tools"][0]["original_name"] == "echo"
    assert tool_registry.exists("mcp.filesystem.echo")

    server = client.get("/api/mcp/filesystem").json()
    assert server["tools_cache_json"][0]["name"] == "mcp.filesystem.echo"
    assert server["last_connected_at"] is not None
    assert server["last_error"] in ("", None)

    caps = client.get("/api/tools/capabilities").json()
    assert any(cap["name"] == "mcp" and "mcp.filesystem.echo" in cap["tools"] for cap in caps)
    assert any(cap["name"] == "mcp.filesystem" and "mcp.filesystem.echo" in cap["tools"] for cap in caps)

    db = _db(client)
    logs = db.query(AuditLogModel).filter(AuditLogModel.event_type == "mcp_server_tested").all()
    assert logs
    assert "super-secret-token" not in str(logs[-1].data)
    assert "***" in str(logs[-1].data)


def test_mcp_test_connection_failure_updates_last_error(client):
    client.post("/api/mcp", json=_mcp_payload(id="broken", command="command-that-does-not-exist"))

    response = client.post("/api/mcp/broken/test")

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert response.json()["error"]["code"] == "MCP_CONNECTION_FAILED"
    server = client.get("/api/mcp/broken").json()
    assert server["last_error"]


def test_agent_mcp_association_and_permission_rules(client):
    client.post("/api/mcp", json=_mcp_payload())
    client.post("/api/mcp/filesystem/test")
    provider = client.post("/api/providers", json={"type": "ollama", "name": "Ollama"}).json()
    agent = client.post("/api/agents", json={
        "name": "Agent",
        "model_config": {"provider_id": provider["id"], "model": "mock"},
        "capabilities": ["mcp.filesystem"],
    }).json()

    assert client.post(f"/api/agents/{agent['id']}/mcp/filesystem").status_code == 200
    assert client.get(f"/api/agents/{agent['id']}/mcp").json()[0]["id"] == "filesystem"

    check_tool_permission("mcp.filesystem.echo", ["mcp.filesystem"], [], [])
    check_tool_permission("mcp.filesystem.echo", ["mcp"], [], [])
    with pytest.raises(ToolDeniedError):
        check_tool_permission("mcp.filesystem.echo", ["mcp.filesystem"], [], ["mcp.filesystem.echo"])

    assert client.delete(f"/api/agents/{agent['id']}/mcp/filesystem").status_code == 200
    assert client.get(f"/api/agents/{agent['id']}/mcp").json() == []


def test_mcp_tool_execution_requires_enabled_server_and_agent_association(client):
    client.post("/api/mcp", json=_mcp_payload())
    client.post("/api/mcp/filesystem/test")
    db = _db(client)
    db.add(AgentModel(
        id="agent_test",
        name="Agent",
        model_config={"provider_id": "provider_1", "model": "mock"},
        capabilities=["mcp.filesystem"],
        mcp_servers=[],
    ))
    db.commit()

    context = ToolExecutionContext("exec_test", "agent_test", [], db, approval_mode="auto")

    with pytest.raises(ToolError) as not_associated:
        asyncio.run(tool_registry.get("mcp.filesystem.echo").execute({"message": "hello"}, context))
    assert not_associated.value.code == "MCP_SERVER_NOT_ASSOCIATED"

    agent = db.query(AgentModel).filter(AgentModel.id == "agent_test").first()
    agent.mcp_servers = ["filesystem"]
    db.add(agent)
    db.commit()

    result = asyncio.run(tool_registry.get("mcp.filesystem.echo").execute({"message": "hello"}, context))
    assert result["content"][0]["type"] == "text"
    assert "hello" in result["content"][0]["text"]

    server = db.query(MCPServerModel).filter(MCPServerModel.id == "filesystem").first()
    server.enabled = False
    db.add(server)
    db.commit()

    with pytest.raises(ToolError) as disabled:
        asyncio.run(tool_registry.get("mcp.filesystem.echo").execute({}, context))
    assert disabled.value.code == "MCP_SERVER_DISABLED"


@pytest.mark.asyncio
async def test_mcp_critical_tool_manual_approval_and_auto_execution(client, monkeypatch):
    client.post("/api/mcp", json=_mcp_payload())
    client.post("/api/mcp/filesystem/test")

    class ProviderMock:
        async def chat(self, request):
            return type("Response", (), {
                "content": '{"type":"tool_call","tool":"mcp.filesystem.echo","arguments":{"message":"hello"}}'
            })

    monkeypatch.setattr("app.runtime.agent_runtime.provider_registry.get", lambda provider: ProviderMock())

    db = _db(client)
    db.add(AgentModel(
        id="agent_1",
        name="Agent",
        model_config={"provider_id": "provider_1", "model": "mock"},
        capabilities=["mcp.filesystem"],
        mcp_servers=["filesystem"],
    ))
    db.commit()

    agent = Agent(
        id="agent_1",
        name="Agent",
        model_config=ModelConfig(provider_id="provider_1", model="mock"),
        capabilities=["mcp.filesystem"],
        mcp_servers=["filesystem"],
        memory_config={"use_global": False, "use_agent_memory": False, "use_team_memory": False},
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )
    provider = Provider(id="provider_1", type=ProviderType.OLLAMA, name="Mock")

    manual = _execution(ApprovalMode.MANUAL)
    events = [event async for event in AgentRuntime(db).run(agent, manual, provider, stream=False)]
    assert any(event.type.value == "approval_requested" for event in events)

    auto = _execution(ApprovalMode.AUTO)
    events = [event async for event in AgentRuntime(db).run(agent, auto, provider, stream=False)]
    assert any(event.type.value == "mcp_tool_call_requested" for event in events)
    assert any(event.type.value == "mcp_tool_completed" for event in events)


def _db(client):
    override = next(iter(client.app.dependency_overrides.values()))
    return next(override())


def _execution(mode):
    from datetime import datetime

    return Execution(
        id="exec_1",
        type=ExecutionType.AGENT,
        target_id="agent_1",
        user_input="echo",
        status=ExecutionStatus.RUNNING,
        approval_mode=mode,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
