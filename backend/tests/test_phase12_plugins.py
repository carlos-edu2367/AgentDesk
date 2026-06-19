import asyncio
import json
import sys
from pathlib import Path

import pytest

from app.db.models import AgentModel, AuditLogModel, PluginModel, SkillModel
from app.domain.enums import ApprovalMode, ExecutionStatus, ExecutionType, ProviderType
from app.domain.schemas import Agent, Execution, ModelConfig, Provider
from app.permissions.gate import check_tool_permission
from app.runtime.agent_runtime import AgentRuntime
from app.tools.base import ToolExecutionContext
from app.tools.errors import ToolDeniedError, ToolError
from app.tools.registry import tool_registry


def _write_sample_plugin(root: Path, *, critical: bool = False, stdout: str | None = None, sleep: float = 0.0):
    plugin_dir = root / "sample-plugin"
    (plugin_dir / "tools").mkdir(parents=True)
    (plugin_dir / "skills").mkdir()
    tool_body = stdout
    if tool_body is None:
        tool_body = (
            "import json, sys, time\n"
            f"time.sleep({sleep})\n"
            "payload = json.loads(sys.stdin.read())\n"
            "print(json.dumps({'status': 'success', 'result': {'echo': payload.get('arguments', {})}}))\n"
        )
    (plugin_dir / "tools" / "echo.py").write_text(tool_body, encoding="utf-8")
    (plugin_dir / "skills" / "sample.skill.json").write_text(json.dumps({
        "id": "skill_plugin_sample",
        "name": "Plugin Sample",
        "version": "0.1.0",
        "description": "A plugin-provided skill.",
        "tags": ["plugin"],
        "prompt": "Use the plugin sample behavior.",
        "examples": [],
    }), encoding="utf-8")
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "id": "plugin_sample",
        "name": "Sample Plugin",
        "version": "0.1.0",
        "description": "Sample plugin for tests.",
        "author": "tests",
        "agentdesk_version": ">=0.1.0",
        "enabled_by_default": False,
        "permissions": ["sample"],
        "skills": ["skills/sample.skill.json"],
        "tools": [{
            "name": "sample.echo",
            "description": "Echoes arguments.",
            "entrypoint": "tools/echo.py",
            "runtime": "python",
            "capability": "sample",
            "critical": critical,
            "input_schema": {"type": "object"},
        }],
    }), encoding="utf-8")
    return plugin_dir


def test_import_valid_plugin_registers_db_tools_and_skill(client, tmp_path):
    plugin_dir = _write_sample_plugin(tmp_path)

    response = client.post("/api/plugins/import", json={"path": str(plugin_dir)})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "plugin_sample"
    assert data["enabled"] is False
    assert data["tools"] == ["sample.echo"]
    assert data["skills"] == ["skill_plugin_sample"]

    plugins = client.get("/api/plugins").json()
    assert [plugin["id"] for plugin in plugins] == ["plugin_sample"]
    assert client.get("/api/plugins/plugin_sample/tools").json()[0]["name"] == "sample.echo"
    assert client.get("/api/plugins/plugin_sample/skills").json()[0]["id"] == "skill_plugin_sample"


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda p: (p / "plugin.json").unlink(), "plugin.json"),
        (lambda p: _patch_manifest(p, {"id": None}), "id"),
        (lambda p: _patch_manifest(p, {"name": ""}), "name"),
        (lambda p: _patch_manifest(p, {"tools": [{"name": "echo", "description": "bad", "entrypoint": "tools/echo.py", "runtime": "python", "capability": "sample"}]}), "namespace"),
        (lambda p: _patch_manifest(p, {"tools": [{"name": "filesystem.read", "description": "bad", "entrypoint": "tools/echo.py", "runtime": "python", "capability": "sample"}]}), "reserved"),
        (lambda p: _patch_manifest(p, {"tools": [{"name": "sample.echo", "description": "bad", "entrypoint": "tools/missing.py", "runtime": "python", "capability": "sample"}]}), "entrypoint"),
        (lambda p: _patch_manifest(p, {"tools": [{"name": "sample.echo", "description": "bad", "entrypoint": "../outside.py", "runtime": "python", "capability": "sample"}]}), "outside"),
        (lambda p: _patch_manifest(p, {"tools": [
            {"name": "sample.echo", "description": "one", "entrypoint": "tools/echo.py", "runtime": "python", "capability": "sample"},
            {"name": "sample.echo", "description": "two", "entrypoint": "tools/echo.py", "runtime": "python", "capability": "sample"},
        ]}), "duplicate"),
        (lambda p: _patch_manifest(p, {"tools": [{"name": "terminal.exec", "description": "bad", "entrypoint": "tools/echo.py", "runtime": "python", "capability": "sample"}]}), "core"),
    ],
)
def test_import_rejects_invalid_manifest(client, tmp_path, mutate, expected):
    plugin_dir = _write_sample_plugin(tmp_path)
    mutate(plugin_dir)

    response = client.post("/api/plugins/import", json={"path": str(plugin_dir)})

    assert response.status_code == 400
    assert expected.lower() in response.json()["detail"].lower()


def _patch_manifest(plugin_dir: Path, patch: dict):
    manifest_path = plugin_dir / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(patch)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_enable_registers_tool_capability_and_disable_blocks_execution(client, tmp_path):
    plugin_dir = _write_sample_plugin(tmp_path)
    client.post("/api/plugins/import", json={"path": str(plugin_dir)})

    enabled = client.post("/api/plugins/plugin_sample/enable")

    assert enabled.status_code == 200
    assert tool_registry.exists("sample.echo")
    assert any(cap["name"] == "sample" and "sample.echo" in cap["tools"] for cap in client.get("/api/tools/capabilities").json())
    check_tool_permission("sample.echo", ["sample"], [], [])

    disabled = client.post("/api/plugins/plugin_sample/disable")
    assert disabled.status_code == 200
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(tool_registry.get("sample.echo").execute({"message": "x"}, _context(client)))
    assert exc_info.value.code == "PLUGIN_DISABLED"


def test_runner_executes_python_tool_with_json_stdin_and_stdout(client, tmp_path):
    plugin_dir = _write_sample_plugin(tmp_path)
    client.post("/api/plugins/import", json={"path": str(plugin_dir)})
    client.post("/api/plugins/plugin_sample/enable")

    result = asyncio.run(tool_registry.get("sample.echo").execute({"message": "hello"}, _context(client)))

    assert result["echo"] == {"message": "hello"}
    assert client.get("/api/plugins/plugin_sample").json()["enabled"] is True


def test_runner_invalid_stdout_stderr_timeout_and_disabled(client, tmp_path):
    invalid_dir = _write_sample_plugin(tmp_path / "invalid", stdout="import sys\nsys.stderr.write('secret-stderr')\nprint('not json')\n")
    client.post("/api/plugins/import", json={"path": str(invalid_dir)})
    client.post("/api/plugins/plugin_sample/enable")

    with pytest.raises(ToolError) as invalid_exc:
        asyncio.run(tool_registry.get("sample.echo").execute({}, _context(client)))
    assert invalid_exc.value.code == "PLUGIN_INVALID_STDOUT"
    assert "secret-stderr" in invalid_exc.value.details.get("stderr_preview", "")

    client.delete("/api/plugins/plugin_sample")
    slow_dir = _write_sample_plugin(tmp_path / "slow", sleep=2)
    client.post("/api/plugins/import", json={"path": str(slow_dir)})
    client.post("/api/plugins/plugin_sample/enable")

    with pytest.raises(ToolError) as timeout_exc:
        asyncio.run(tool_registry.get("sample.echo").execute({"timeout_seconds": 1}, _context(client)))
    assert timeout_exc.value.code == "PLUGIN_TOOL_TIMEOUT"


def test_agent_plugin_association_and_permission_rules(client, tmp_path):
    plugin_dir = _write_sample_plugin(tmp_path)
    client.post("/api/plugins/import", json={"path": str(plugin_dir)})
    client.post("/api/plugins/plugin_sample/enable")
    provider = client.post("/api/providers", json={"type": "ollama", "name": "Ollama"}).json()
    agent = client.post("/api/agents", json={
        "name": "Agent",
        "model_config": {"provider_id": provider["id"], "model": "mock"},
        "capabilities": ["sample"],
    }).json()

    assert client.post(f"/api/agents/{agent['id']}/plugins/plugin_sample").status_code == 200
    assert client.get(f"/api/agents/{agent['id']}/plugins").json()[0]["id"] == "plugin_sample"

    check_tool_permission("sample.echo", ["sample"], [], [])
    with pytest.raises(ToolDeniedError):
        check_tool_permission("sample.echo", [], [], [])
    with pytest.raises(ToolDeniedError):
        check_tool_permission("sample.echo", ["sample"], [], ["sample.echo"])

    replaced = client.put(f"/api/agents/{agent['id']}/plugins", json={"plugin_ids": []})
    assert replaced.status_code == 200
    assert client.get(f"/api/agents/{agent['id']}/plugins").json() == []


@pytest.mark.asyncio
async def test_plugin_critical_tool_manual_approval_and_auto_execution(client, tmp_path, monkeypatch):
    plugin_dir = _write_sample_plugin(tmp_path, critical=True)
    client.post("/api/plugins/import", json={"path": str(plugin_dir)})
    client.post("/api/plugins/plugin_sample/enable")

    class ProviderMock:
        async def chat(self, request):
            return type("Response", (), {"content": json.dumps({"type": "tool_call", "tool": "sample.echo", "arguments": {"x": 1}})})

    monkeypatch.setattr("app.runtime.agent_runtime.provider_registry.get", lambda provider: ProviderMock())

    db = _db(client)
    agent = _agent(approval_capabilities=["sample"])
    provider = Provider(id="provider_1", type=ProviderType.OLLAMA, name="Mock")
    manual = _execution(ApprovalMode.MANUAL)
    events = [event async for event in AgentRuntime(db).run(agent, manual, provider, stream=False)]
    assert any(event.type.value == "approval_requested" for event in events)

    auto = _execution(ApprovalMode.AUTO)
    events = [event async for event in AgentRuntime(db).run(agent, auto, provider, stream=False)]
    assert any(event.type.value == "plugin_tool_completed" for event in events)


def test_plugin_skill_injection_depends_on_plugin_enabled(client, tmp_path):
    plugin_dir = _write_sample_plugin(tmp_path)
    client.post("/api/plugins/import", json={"path": str(plugin_dir)})
    client.post("/api/plugins/plugin_sample/enable")
    db = _db(client)
    agent = AgentModel(
        id="agent_test",
        name="Agent",
        model_config={"provider_id": "provider_1", "model": "mock"},
        skills=["skill_plugin_sample"],
        plugins=["plugin_sample"],
    )
    db.add(agent)
    db.commit()

    from app.skills.service import SkillService

    enabled_text = SkillService(db).format_skills_for_prompt(agent.skills, []).text
    assert "Plugin Sample" in enabled_text

    client.post("/api/plugins/plugin_sample/disable")
    disabled_text = SkillService(db).format_skills_for_prompt(agent.skills, []).text
    assert "Plugin Sample" not in disabled_text


def _context(client):
    return ToolExecutionContext(
        execution_id="exec_test",
        agent_id="agent_test",
        workspace_ids=[],
        db=_db(client),
        approval_mode="auto",
    )


def _db(client):
    override = next(iter(client.app.dependency_overrides.values()))
    return next(override())


def _agent(approval_capabilities=None):
    from datetime import datetime

    return Agent(
        id="agent_1",
        name="Agent",
        model_config=ModelConfig(provider_id="provider_1", model="mock"),
        capabilities=approval_capabilities or [],
        plugins=["plugin_sample"],
        memory_config={"use_global": False, "use_agent_memory": False, "use_team_memory": False},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


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
