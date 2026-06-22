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
