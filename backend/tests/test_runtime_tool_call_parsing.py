import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.enums import ApprovalMode, ExecutionStatus, ExecutionType, ProviderType
from app.domain.schemas import Agent, Execution, ModelConfig, Provider
from app.providers.schemas import ChatResponse
from app.runtime.agent_runtime import AgentRuntime
from app.runtime.parser import OutputParser
from app.tools.base import BaseTool
from app.tools.registry import tool_registry


class EchoTool(BaseTool):
    name = "test.echo"
    description = "Echo test input"
    input_schema = {"type": "object", "properties": {"value": {"type": "string"}}}

    async def execute(self, arguments, context):
        return {"echo": arguments.get("value", "")}


def test_parser_extracts_tool_call_embedded_in_text_before_other_json_objects():
    raw = (
        'Vou pesquisar para voce.'
        '{"type": "tool_call", "tool": "http.request", "arguments": {"method": "GET", "url": "https://example.com/a"}}'
        '{"type": "tool_call", "tool": "http.request", "arguments": {"method": "GET", "url": "https://example.com/b"}}'
    )

    parsed = OutputParser().parse(raw)

    assert parsed.is_tool_call
    assert parsed.tool_name == "http.request"
    assert parsed.arguments == {"method": "GET", "url": "https://example.com/a"}


def test_parser_accepts_tool_name_collapsed_into_type():
    """Local models often emit {"type": "<tool>", "arguments": {...}} instead of
    the documented {"type": "tool_call", "tool": "<tool>", ...}. Accept it so the
    call actually runs instead of leaking raw JSON into the chat."""
    parsed = OutputParser().parse(
        '{"type": "filesystem.write", "arguments": {"path": "a.js", "content": "x", "mode": "overwrite"}}'
    )
    assert parsed.is_tool_call
    assert parsed.tool_name == "filesystem.write"
    assert parsed.arguments == {"path": "a.js", "content": "x", "mode": "overwrite"}


def test_parser_accepts_tool_call_without_type_field():
    """Shape {"tool": "<tool>", "arguments": {...}} with no type at all."""
    parsed = OutputParser().parse(
        '{"tool": "filesystem.read", "arguments": {"path": "a.js"}}'
    )
    assert parsed.is_tool_call
    assert parsed.tool_name == "filesystem.read"
    assert parsed.arguments == {"path": "a.js"}


def test_parser_does_not_misclassify_plain_json_as_tool_call():
    """A non-dotted unknown type without a tool field is not a tool call."""
    parsed = OutputParser().parse('{"type": "status", "arguments": {}}')
    assert not parsed.is_tool_call
    # final_answer still wins.
    final = OutputParser().parse('{"type": "final_answer", "content": "done"}')
    assert final.is_final and not final.is_tool_call


def test_parser_detects_truncated_tool_call():
    parser = OutputParser()
    # A tool call whose huge inline content was cut off mid-string.
    raw = (
        'Vou criar o arquivo.'
        '{"type": "tool_calls", "calls": [{"id": "call_1", "tool": "filesystem.write", '
        '"arguments": {"path": "C:/x/index.html", "content": "<!DOCTYPE html><html><body'
    )
    parsed = parser.parse(raw)
    assert not parsed.is_tool_call  # unparseable, so not a real tool call
    assert parser.looks_like_truncated_tool_call(raw)


def test_parser_does_not_flag_complete_outputs_as_truncated():
    parser = OutputParser()
    assert not parser.looks_like_truncated_tool_call("Just a plain text answer.")
    assert not parser.looks_like_truncated_tool_call(
        '{"type": "final_answer", "content": "all done"}'
    )
    # Prose mentioning braces but no protocol opener is not flagged.
    assert not parser.looks_like_truncated_tool_call("Here is some code: {x: 1")


def test_parser_accepts_tool_calls_batch():
    parsed = OutputParser().parse(
        json.dumps({
            "type": "tool_calls",
            "calls": [
                {"id": "call_1", "tool": "http.request", "arguments": {"url": "https://example.com/a"}},
                {"id": "call_2", "tool": "http.request", "arguments": {"url": "https://example.com/b"}},
            ],
        })
    )

    assert parsed.is_tool_call
    assert parsed.tool_calls == [
        {"id": "call_1", "tool": "http.request", "arguments": {"url": "https://example.com/a"}},
        {"id": "call_2", "tool": "http.request", "arguments": {"url": "https://example.com/b"}},
    ]
    assert parsed.tool_name == "http.request"
    assert parsed.arguments == {"url": "https://example.com/a"}


@pytest.mark.asyncio
async def test_runtime_surfaces_truncation_and_gives_up_instead_of_looping():
    """When the model keeps emitting tool calls cut off by max_tokens, the runtime
    must (a) surface each truncation as a visible event and (b) stop after a few
    consecutive truncations with an error — never loop silently to max_steps."""
    agent = Agent(
        id="agent_1",
        name="Agent",
        model_config=ModelConfig(provider_id="prov_1", model="mock"),
        explicit_tools=["filesystem.write"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    execution = Execution(
        id="exec_1",
        type=ExecutionType.AGENT,
        target_id="agent_1",
        user_input="write a big file",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        workspace_ids=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    provider_config = Provider(id="prov_1", type=ProviderType.OLLAMA, name="Mock")
    truncated = (
        'Vou criar o arquivo.'
        '{"type": "tool_calls", "calls": [{"id": "c1", "tool": "filesystem.write", '
        '"arguments": {"path": "a.html", "content": "<!DOCTYPE html><html><body'
    )
    provider = MagicMock()
    # More truncated responses than the retry budget — if the runtime looped to
    # max_steps it would consume all of these; we assert it stops well before.
    provider.chat = AsyncMock(side_effect=[
        ChatResponse(provider_id="prov_1", model="mock", content=truncated)
        for _ in range(8)
    ])

    with patch("app.runtime.agent_runtime.provider_registry") as provider_registry:
        provider_registry.get.return_value = provider
        events = [
            event
            async for event in AgentRuntime().run(agent, execution, provider_config, stream=False)
        ]

    truncation_events = [e for e in events if e.type.value == "model_output_truncated"]
    error_events = [e for e in events if e.type.value == "error"]

    # Each truncation is surfaced with an increasing attempt number...
    assert [e.content["attempt"] for e in truncation_events] == [1, 2, 3]
    # ...then the runtime gives up with a clear error instead of looping.
    assert len(error_events) == 1
    assert "max_tokens" in error_events[-1].content["error"]
    # It must not have reached a successful completion or burned all 8 calls.
    assert not any(e.type.value == "agent_completed" for e in events)
    assert provider.chat.call_count == 4


@pytest.mark.asyncio
async def test_runtime_does_not_complete_with_empty_result_after_tool_use():
    tool_registry.unregister("test.echo")
    tool_registry.register(EchoTool())
    agent = Agent(
        id="agent_1",
        name="Agent",
        model_config=ModelConfig(provider_id="prov_1", model="mock"),
        explicit_tools=["test.echo"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    execution = Execution(
        id="exec_1",
        type=ExecutionType.AGENT,
        target_id="agent_1",
        user_input="inspect and continue",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        workspace_ids=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    provider_config = Provider(id="prov_1", type=ProviderType.OLLAMA, name="Mock")
    provider = MagicMock()
    provider.chat = AsyncMock(
        side_effect=[
            ChatResponse(
                provider_id="prov_1",
                model="mock",
                content='{"type":"tool_call","tool":"test.echo","arguments":{"value":"context"}}',
            ),
            ChatResponse(provider_id="prov_1", model="mock", content=""),
        ]
    )

    try:
        with patch("app.runtime.agent_runtime.provider_registry") as provider_registry:
            provider_registry.get.return_value = provider
            events = [
                event
                async for event in AgentRuntime().run(agent, execution, provider_config, stream=False)
            ]
    finally:
        tool_registry.unregister("test.echo")

    assert [event.type.value for event in events if event.type.value == "tool_result"] == ["tool_result"]
    assert not any(
        event.type.value == "agent_completed" and event.content.get("result") == ""
        for event in events
    )
    error_events = [event for event in events if event.type.value == "error"]
    assert len(error_events) == 1
    assert "empty response" in error_events[0].content["error"].lower()


@pytest.mark.asyncio
async def test_execution_engine_fails_when_runtime_emits_error():
    from app.domain.enums import EventType
    from app.domain.schemas import ExecutionEventCreate
    from app.orchestrator.execution_engine import ExecutionEngine

    engine = ExecutionEngine()
    db = MagicMock()
    agent = Agent(
        id="agent_1",
        name="Agent",
        model_config=ModelConfig(provider_id="prov_1", model="mock"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    provider_config = Provider(id="prov_1", type=ProviderType.OLLAMA, name="Mock")
    engine._emit_and_save_event = AsyncMock()

    with (
        patch("app.orchestrator.execution_engine.execution_repo.get") as get_execution,
        patch("app.orchestrator.execution_engine.AgentRuntime") as Runtime,
    ):
        get_execution.return_value = Execution(
            id="exec_1",
            type=ExecutionType.AGENT,
            target_id="agent_1",
            user_input="run",
            status=ExecutionStatus.RUNNING,
            approval_mode=ApprovalMode.AUTO,
            workspace_ids=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        async def fake_run(**kwargs):
            yield ExecutionEventCreate(
                execution_id="exec_1",
                type=EventType.ERROR,
                source="runtime",
                source_id="agent_1",
                content={"error": "empty response from model"},
            )

        Runtime.return_value.run = fake_run

        with pytest.raises(RuntimeError, match="empty response from model"):
            await engine._run_runtime_loop(db, "exec_1", agent, provider_config, stream=False)


@pytest.mark.asyncio
async def test_runtime_returns_tool_result_to_model_and_allows_another_tool_call():
    tool_registry.unregister("test.echo")
    tool_registry.register(EchoTool())
    agent = Agent(
        id="agent_1",
        name="Agent",
        model_config=ModelConfig(provider_id="prov_1", model="mock"),
        explicit_tools=["test.echo"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    execution = Execution(
        id="exec_1",
        type=ExecutionType.AGENT,
        target_id="agent_1",
        user_input="use tools",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        workspace_ids=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    provider_config = Provider(id="prov_1", type=ProviderType.OLLAMA, name="Mock")
    provider = MagicMock()
    provider.chat = AsyncMock(
        side_effect=[
            ChatResponse(
                provider_id="prov_1",
                model="mock",
                content='Vou consultar.{"type":"tool_call","tool":"test.echo","arguments":{"value":"first"}}',
            ),
            ChatResponse(
                provider_id="prov_1",
                model="mock",
                content='{"type":"tool_call","tool":"test.echo","arguments":{"value":"second"}}',
            ),
            ChatResponse(
                provider_id="prov_1",
                model="mock",
                content='{"type":"final_answer","content":"done"}',
            ),
        ]
    )

    try:
        with patch("app.runtime.agent_runtime.provider_registry") as provider_registry:
            provider_registry.get.return_value = provider
            events = [
                event
                async for event in AgentRuntime().run(agent, execution, provider_config, stream=False)
            ]
    finally:
        tool_registry.unregister("test.echo")

    tool_results = [event for event in events if event.type.value == "tool_result"]
    assert [json.loads(call.args[0].messages[-1].content)["result"] for call in provider.chat.call_args_list[1:]] == [
        {"echo": "first"},
        {"echo": "second"},
    ]
    assert [event.content["tool"] for event in tool_results] == ["test.echo", "test.echo"]
    assert events[-1].type.value == "agent_completed"
    assert events[-1].content["result"] == "done"


@pytest.mark.asyncio
async def test_runtime_returns_batch_tool_results_and_allows_more_tool_calls():
    tool_registry.unregister("test.echo")
    tool_registry.register(EchoTool())
    agent = Agent(
        id="agent_1",
        name="Agent",
        model_config=ModelConfig(provider_id="prov_1", model="mock"),
        explicit_tools=["test.echo"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    execution = Execution(
        id="exec_1",
        type=ExecutionType.AGENT,
        target_id="agent_1",
        user_input="use tool batches",
        status=ExecutionStatus.RUNNING,
        approval_mode=ApprovalMode.AUTO,
        workspace_ids=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    provider_config = Provider(id="prov_1", type=ProviderType.OLLAMA, name="Mock")
    provider = MagicMock()
    provider.chat = AsyncMock(
        side_effect=[
            ChatResponse(
                provider_id="prov_1",
                model="mock",
                content=json.dumps({
                    "type": "tool_calls",
                    "calls": [
                        {"id": "call_1", "tool": "test.echo", "arguments": {"value": "first"}},
                        {"id": "call_2", "tool": "test.echo", "arguments": {"value": "second"}},
                    ],
                }),
            ),
            ChatResponse(
                provider_id="prov_1",
                model="mock",
                content=json.dumps({
                    "type": "tool_calls",
                    "calls": [
                        {"id": "call_3", "tool": "test.echo", "arguments": {"value": "third"}},
                    ],
                }),
            ),
            ChatResponse(
                provider_id="prov_1",
                model="mock",
                content='{"type":"final_answer","content":"done"}',
            ),
        ]
    )

    try:
        with patch("app.runtime.agent_runtime.provider_registry") as provider_registry:
            provider_registry.get.return_value = provider
            events = [
                event
                async for event in AgentRuntime().run(agent, execution, provider_config, stream=False)
            ]
    finally:
        tool_registry.unregister("test.echo")

    first_tool_feedback = json.loads(provider.chat.call_args_list[1].args[0].messages[-1].content)
    second_tool_feedback = json.loads(provider.chat.call_args_list[2].args[0].messages[-1].content)

    assert first_tool_feedback == {
        "type": "tool_results",
        "results": [
            {"id": "call_1", "tool": "test.echo", "status": "success", "result": {"echo": "first"}},
            {"id": "call_2", "tool": "test.echo", "status": "success", "result": {"echo": "second"}},
        ],
    }
    assert second_tool_feedback == {
        "type": "tool_results",
        "results": [
            {"id": "call_3", "tool": "test.echo", "status": "success", "result": {"echo": "third"}},
        ],
    }
    assert [event.content["tool"] for event in events if event.type.value == "tool_result"] == [
        "test.echo",
        "test.echo",
        "test.echo",
    ]
    assert events[-1].type.value == "agent_completed"
    assert events[-1].content["result"] == "done"
