import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.repositories.registry import agent_repo, execution_event_repo, provider_repo
from app.domain import schemas
from app.domain.enums import ApprovalMode, EventType, ExecutionStatus, ExecutionType, ProviderType
from app.permissions.gate import check_tool_permission
from app.runtime.agent_runtime import AgentRuntime
from app.runtime.parser import OutputParser
from app.tools.errors import ToolDeniedError
from app.tools.registry import register_core_tools, tool_registry


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _provider_create(text: str):
    return schemas.ProviderCreate(
        type=ProviderType.OLLAMA,
        name="Mock Provider",
        enabled=True,
        config={"mock_response_text": text, "mock_chunks": [text]},
    )


def _agent_create(name: str, **kwargs):
    data = {
        "name": name,
        "model_config": schemas.ModelConfig(provider_id="prov_1", model="mock"),
    }
    data.update(kwargs)
    return schemas.AgentCreate(**data)


def test_agent_and_team_control_capabilities_register_tools():
    register_core_tools()

    for tool_name in ["agent.list", "agent.call", "team.list", "team.execute"]:
        assert tool_registry.exists(tool_name)

    check_tool_permission("agent.call", ["agent_control"], [], [])
    check_tool_permission("team.execute", ["team_control"], [], [])

    with pytest.raises(ToolDeniedError):
        check_tool_permission("agent.call", ["agent_control"], [], ["agent.call"])


def test_parser_accepts_subagent_call_as_agent_call():
    parsed = OutputParser().parse(
        '{"type":"subagent_call","target_agent_id":"agent_researcher","task":"Research X"}'
    )

    assert parsed.is_tool_call
    assert parsed.tool_name == "agent.call"
    assert parsed.arguments == {
        "target_agent_id": "agent_researcher",
        "task": "Research X",
        "context": {},
    }


@pytest.mark.asyncio
async def test_agent_call_respects_allowed_agent_ids():
    register_core_tools()
    db = _make_db()
    provider_repo.create(db, obj_in=_provider_create('{"type":"final_answer","content":"sub result"}'), id="prov_1")
    agent_repo.create(
        db,
        obj_in=_agent_create(
            "Caller",
            capabilities=["agent_control"],
            subagents=schemas.AgentSubagentsConfig(can_call=True, allowed_agent_ids=["agent_allowed"]),
        ),
        id="agent_caller",
    )
    agent_repo.create(db, obj_in=_agent_create("Blocked"), id="agent_blocked")

    tool = tool_registry.get("agent.call")
    with pytest.raises(ToolDeniedError):
        await tool.execute(
            {"target_agent_id": "agent_blocked", "task": "Do child work"},
            context=MagicMock(
                execution_id="exec_1",
                agent_id="agent_caller",
                workspace_ids=[],
                db=db,
                approval_mode="manual",
                extra={"subagent_depth": 0, "max_subagent_depth": 5},
            ),
        )


@pytest.mark.asyncio
async def test_agent_call_respects_max_subagent_depth():
    register_core_tools()
    db = _make_db()
    provider_repo.create(db, obj_in=_provider_create('{"type":"final_answer","content":"sub result"}'), id="prov_1")
    agent_repo.create(
        db,
        obj_in=_agent_create(
            "Caller",
            capabilities=["agent_control"],
            subagents=schemas.AgentSubagentsConfig(can_call=True, allowed_agent_ids=["*"]),
        ),
        id="agent_caller",
    )
    agent_repo.create(db, obj_in=_agent_create("Child"), id="agent_child")

    tool = tool_registry.get("agent.call")
    with pytest.raises(ToolDeniedError):
        await tool.execute(
            {"target_agent_id": "agent_child", "task": "Do child work"},
            context=MagicMock(
                execution_id="exec_1",
                agent_id="agent_caller",
                workspace_ids=[],
                db=db,
                approval_mode="manual",
                extra={"subagent_depth": 5, "max_subagent_depth": 5},
            ),
        )


@pytest.mark.asyncio
async def test_agent_call_tool_runs_subagent_and_saves_events(monkeypatch):
    register_core_tools()
    db = _make_db()
    provider_repo.create(db, obj_in=_provider_create('{"type":"final_answer","content":"sub result"}'), id="prov_1")
    caller = agent_repo.create(
        db,
        obj_in=_agent_create(
            "Caller",
            capabilities=["agent_control"],
            subagents=schemas.AgentSubagentsConfig(can_call=True, allowed_agent_ids=["agent_child"]),
        ),
        id="agent_caller",
    )
    agent_repo.create(db, obj_in=_agent_create("Child"), id="agent_child")

    monkeypatch.setattr(
        "app.tools.core.agent_tools.AgentRuntime.run",
        lambda *args, **kwargs: _one_event("exec_1", "agent_child", "sub result"),
    )

    tool = tool_registry.get("agent.call")
    result = await tool.execute(
        {"target_agent_id": "agent_child", "task": "Do child work"},
        context=MagicMock(
            execution_id="exec_1",
            agent_id=caller.id,
            workspace_ids=[],
            db=db,
            approval_mode="manual",
            extra={"subagent_depth": 0, "max_subagent_depth": 5},
        ),
    )

    assert result["target_agent_id"] == "agent_child"
    assert result["result"] == "sub result"
    events = execution_event_repo.get_multi(db)
    event_types = [e.type for e in events]
    assert EventType.SUBAGENT_CALL_REQUESTED in event_types
    assert EventType.SUBAGENT_STARTED in event_types
    assert EventType.AGENT_COMPLETED in event_types
    assert EventType.SUBAGENT_COMPLETED in event_types


async def _one_event(execution_id: str, agent_id: str, result: str):
    yield schemas.ExecutionEventCreate(
        execution_id=execution_id,
        type=EventType.AGENT_COMPLETED,
        source="runtime",
        source_id=agent_id,
        content={"result": result},
    )


@pytest.mark.asyncio
async def test_runtime_uses_team_memory_scope_for_team_execution():
    agent = schemas.Agent(
        id="agent_leader",
        name="Leader",
        model_config=schemas.ModelConfig(provider_id="prov_1", model="mock"),
        memory_config=schemas.MemoryConfig(use_global=True, use_agent_memory=True, use_team_memory=True),
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )
    execution = schemas.Execution(
        id="exec_1",
        type=ExecutionType.TEAM,
        target_id="team_1",
        user_input="Team request",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        workspace_ids=[],
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )
    provider = schemas.Provider(id="prov_1", type=ProviderType.OLLAMA, name="Mock")
    captured_scopes = []

    async def fake_search(request):
        captured_scopes.extend(request.scopes)
        return schemas.MemorySearchResponse(results=[])

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.runtime.agent_runtime.MemoryService") as MockMemorySvc:
        svc = MagicMock()
        svc.search = AsyncMock(side_effect=fake_search)
        svc.format_memories_for_prompt = MagicMock(return_value="")
        svc.record_usage = MagicMock()
        MockMemorySvc.return_value = svc
        mock_registry.get.return_value = mock_provider

        runtime = AgentRuntime(db_session=MagicMock())
        async for _ in runtime.run(
            agent,
            execution,
            provider,
            stream=False,
            runtime_options={"team_id": "team_1", "include_team_memory": True},
        ):
            pass

    assert "global" in captured_scopes
    assert "agent:agent_leader" in captured_scopes
    assert "team:team_1" in captured_scopes
