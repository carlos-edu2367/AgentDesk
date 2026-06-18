"""Tests for memory injection in Agent Runtime."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, MemoryModel
from app.domain.schemas import Agent, Execution, Provider, ModelConfig, MemoryConfig
from app.domain.enums import ExecutionType, ExecutionStatus, ApprovalMode, EventType, ProviderType
from app.runtime.agent_runtime import AgentRuntime


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _add_memory(db, id, title, content, scope="global", scope_id=None):
    m = MemoryModel(
        id=id, scope=scope, scope_id=scope_id, type="preference",
        title=title, content=content, tags=[], confidence=0.8, importance=0.7,
        source={}, usage_count=0, embedding_status="pending",
    )
    db.add(m)
    db.commit()


def _make_agent(agent_id="agent_001", use_global=True, use_agent_memory=True):
    return Agent(
        id=agent_id,
        name="Test Agent",
        model_config=ModelConfig(provider_id="prov_001", model="llama3"),
        memory_config=MemoryConfig(use_global=use_global, use_agent_memory=use_agent_memory),
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )


def _make_execution(agent_id="agent_001"):
    return Execution(
        id="exec_001", type=ExecutionType.AGENT, target_id=agent_id,
        user_input="Qual é minha preferência de resposta?",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )


def _make_provider():
    return Provider(id="prov_001", type=ProviderType.OLLAMA, name="Ollama")


@pytest.mark.asyncio
async def test_runtime_injects_memories_into_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()
    _add_memory(db, "m1", "Prefere Python", "Usa Python para scripts e automações")

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))
    mock_provider.stream_chat = AsyncMock(return_value=iter([]))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.memory.search.get_embedding_for_memory", AsyncMock(return_value=None)):
        mock_registry.get.return_value = mock_provider
        runtime = AgentRuntime(db_session=db)
        agent = _make_agent()
        execution = _make_execution()
        provider = _make_provider()

        events = []
        async for event in runtime.run(agent, execution, provider, stream=False):
            events.append(event)

    memory_events = [e for e in events if "memory" in e.type]
    assert len(memory_events) >= 1

    prompt_events = [e for e in events if e.type == "prompt_built"]
    assert len(prompt_events) == 1


@pytest.mark.asyncio
async def test_runtime_continues_when_memory_search_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))
    mock_provider.stream_chat = AsyncMock(return_value=iter([]))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.runtime.agent_runtime.MemoryService") as MockMemorySvc:
        MockMemorySvc.return_value.search = AsyncMock(side_effect=Exception("DB error"))
        MockMemorySvc.return_value.format_memories_for_prompt = MagicMock(return_value="")
        MockMemorySvc.return_value.record_usage = MagicMock()
        mock_registry.get.return_value = mock_provider
        runtime = AgentRuntime(db_session=db)
        agent = _make_agent()
        execution = _make_execution()
        provider = _make_provider()

        events = []
        async for event in runtime.run(agent, execution, provider, stream=False):
            events.append(event)

    # Should still complete despite memory failure
    assert any("completed" in e.type or "error" in e.type for e in events)


@pytest.mark.asyncio
async def test_memory_scopes_respect_agent_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()

    captured_scopes = []

    async def fake_search(request):
        captured_scopes.extend(request.scopes)
        return MagicMock(results=[])

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.runtime.agent_runtime.MemoryService") as MockMemorySvc:
        svc_instance = MagicMock()
        svc_instance.search = AsyncMock(side_effect=fake_search)
        svc_instance.format_memories_for_prompt = MagicMock(return_value="")
        svc_instance.record_usage = MagicMock()
        MockMemorySvc.return_value = svc_instance
        mock_registry.get.return_value = mock_provider

        runtime = AgentRuntime(db_session=db)
        agent = _make_agent("agent_001", use_global=True, use_agent_memory=True)
        execution = _make_execution()
        provider = _make_provider()

        async for _ in runtime.run(agent, execution, provider, stream=False):
            pass

    assert "global" in captured_scopes
    assert "agent:agent_001" in captured_scopes


@pytest.mark.asyncio
async def test_memory_usage_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    db = _make_db()

    usage_calls = []

    async def fake_search(request):
        from app.domain.schemas import MemorySearchResult, MemorySearchResponse
        result = MemorySearchResult(
            memory_id="m1", score=0.9, scope="global", scope_id=None,
            type="preference", title="T", content="C", tags=[],
            confidence=0.8, importance=0.7, has_embedding=False,
        )
        return MemorySearchResponse(results=[result])

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=MagicMock(content='{"type":"final_answer","content":"ok"}'))

    with patch("app.runtime.agent_runtime.provider_registry") as mock_registry, \
         patch("app.runtime.agent_runtime.MemoryService") as MockMemorySvc:
        svc_instance = MagicMock()
        svc_instance.search = AsyncMock(side_effect=fake_search)
        svc_instance.format_memories_for_prompt = MagicMock(return_value="[RELEVANT MEMORIES]\n\nT: C")
        svc_instance.record_usage = MagicMock(side_effect=lambda *a, **kw: usage_calls.append(a))
        MockMemorySvc.return_value = svc_instance
        mock_registry.get.return_value = mock_provider

        runtime = AgentRuntime(db_session=db)
        agent = _make_agent()
        execution = _make_execution()
        provider = _make_provider()

        async for _ in runtime.run(agent, execution, provider, stream=False):
            pass

    assert len(usage_calls) >= 1
