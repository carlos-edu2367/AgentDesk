"""Regression tests for the team-flow fixes:

1. Subagent/member events are streamed live (published to the event_bus), not
   only persisted to the DB — so the UI can show what each member is doing.
2. A failure inside a tool (e.g. a member's provider timing out) does not kill
   the whole turn: it is surfaced as a tool error the caller can recover from.
3. The runtime honors a configurable `max_steps` from runtime_options instead of
   always using the hardcoded MAX_STEPS=10 (leader/members need a bigger budget).
"""

import datetime

import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.repositories.registry import agent_repo, execution_event_repo, provider_repo
from app.domain import schemas
from app.domain.enums import ApprovalMode, EventType, ExecutionStatus, ExecutionType, ProviderType
from app.orchestrator.event_bus import event_bus
from app.providers.errors import RequestTimeoutError
from app.runtime.agent_runtime import AgentRuntime
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


async def _one_event(execution_id: str, agent_id: str, result: str):
    yield schemas.ExecutionEventCreate(
        execution_id=execution_id,
        type=EventType.AGENT_COMPLETED,
        source="runtime",
        source_id=agent_id,
        content={"result": result},
    )


def _agent_model(agent_id="agent_x"):
    return schemas.Agent(
        id=agent_id,
        name="X",
        model_config=schemas.ModelConfig(provider_id="prov_1", model="mock"),
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )


def _execution_model(execution_id="exec_1"):
    return schemas.Execution(
        id=execution_id,
        type=ExecutionType.AGENT,
        target_id="agent_x",
        user_input="hi",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        workspace_ids=[],
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_agent_call_publishes_member_events_live(monkeypatch):
    """Subagent + member events must be published on the event_bus so the SSE
    stream shows them in real time (previously they were DB-only)."""
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
        lambda *args, **kwargs: _one_event("exec_live", "agent_child", "sub result"),
    )

    queue = event_bus.subscribe("exec_live")
    try:
        tool = tool_registry.get("agent.call")
        await tool.execute(
            {"target_agent_id": "agent_child", "task": "Do child work"},
            context=MagicMock(
                execution_id="exec_live",
                agent_id=caller.id,
                workspace_ids=[],
                db=db,
                approval_mode="auto",
                extra={"subagent_depth": 0, "max_subagent_depth": 5, "team_id": "team_1"},
            ),
        )
    finally:
        event_bus.unsubscribe("exec_live", queue)

    published = []
    while not queue.empty():
        published.append(queue.get_nowait())
    published_types = {e.get("type") for e in published if isinstance(e, dict)}

    assert EventType.MEMBER_STARTED in published_types
    assert EventType.MEMBER_COMPLETED in published_types
    assert EventType.SUBAGENT_STARTED in published_types
    # Every published event carries the persisted id + created_at (SSE contract).
    for e in published:
        assert e.get("id")
        assert e.get("created_at")


@pytest.mark.asyncio
async def test_tool_provider_error_does_not_kill_turn():
    """A ProviderError raised inside a tool must be caught and returned as a tool
    error payload, not propagate out and fail the whole execution."""
    runtime = AgentRuntime(db_session=None)

    failing_tool = MagicMock()
    failing_tool.source = "core"
    failing_tool.critical = False

    async def _boom(args, ctx):
        raise RequestTimeoutError()

    failing_tool.execute = _boom

    import app.runtime.agent_runtime as rt
    original_get = rt.tool_registry.get
    original_perm = rt.check_tool_permission
    rt.tool_registry.get = lambda name: failing_tool
    rt.check_tool_permission = lambda *a, **k: None
    try:
        events, payload, waiting = await runtime._execute_tool_call(
            call={"id": "c1", "tool": "agent.call", "arguments": {}},
            execution_id="exec_1",
            agent_id="agent_x",
            agent=_agent_model(),
            execution=_execution_model(),
            approval_mode=ApprovalMode.AUTO,
            runtime_options={},
            messages=[],
            step=0,
        )
    finally:
        rt.tool_registry.get = original_get
        rt.check_tool_permission = original_perm

    assert waiting is False
    assert payload["status"] == "error"
    assert EventType.TOOL_FAILED in [e.type for e in events]


@pytest.mark.asyncio
async def test_runtime_honors_max_steps_from_options(monkeypatch):
    """The loop must run at most `runtime_options['max_steps']` model requests."""
    from tests.mocks.mock_provider import MockProvider

    provider = MockProvider("prov_1", config={
        "mock_response_text": '{"type":"tool_call","tool":"unknown_tool"}',
        "mock_chunks": ['{"type":"tool_call","tool":"unknown_tool"}'],
    })

    import app.runtime.agent_runtime as rt
    monkeypatch.setattr(rt.provider_registry, "get", lambda cfg: provider)

    runtime = AgentRuntime(db_session=None)
    provider_cfg = schemas.Provider(id="prov_1", type=ProviderType.OLLAMA, name="Mock")

    model_requests = 0
    completed_msg = None
    async for event in runtime.run(
        agent=_agent_model(),
        execution=_execution_model(),
        provider_config=provider_cfg,
        stream=False,
        initial_messages=[{"role": "user", "content": "hi"}],
        runtime_options={"max_steps": 3},
    ):
        if event.type == EventType.MODEL_REQUEST_STARTED:
            model_requests += 1
        if event.type == EventType.AGENT_COMPLETED:
            completed_msg = event.content.get("result", "")

    assert model_requests == 3
    assert "maximum steps" in (completed_msg or "")
