"""Tests for the [MEMORY SYSTEM] prompt section."""
from types import SimpleNamespace

from app.runtime.prompt_builder import PromptBuilder
from app.tools.schemas import ToolDefinition


def _agent():
    return SimpleNamespace(system_prompt="You are helpful.")


def _execution():
    return SimpleNamespace(
        approval_mode="auto",
        workspace_ids=[],
        user_input="oi",
    )


def _memory_tool():
    return ToolDefinition(
        name="memory.create",
        description="Store a new memory entry",
        source="core",
        capability="memory",
    )


def _fs_tool():
    return ToolDefinition(
        name="filesystem.read",
        description="Read a file",
        source="core",
        capability="filesystem_read",
    )


def test_memory_instructions_present_when_memory_tools_available():
    builder = PromptBuilder(_agent(), _execution(), available_tools=[_memory_tool()])
    prompt = builder.build_system_prompt()
    assert "[MEMORY SYSTEM]" in prompt
    assert "memory.create" in prompt
    assert "memory.update" in prompt
    assert "memory.delete" in prompt


def test_memory_instructions_absent_without_memory_tools():
    builder = PromptBuilder(_agent(), _execution(), available_tools=[_fs_tool()])
    prompt = builder.build_system_prompt()
    assert "[MEMORY SYSTEM]" not in prompt


def test_memory_instructions_absent_with_no_tools():
    builder = PromptBuilder(_agent(), _execution(), available_tools=[])
    prompt = builder.build_system_prompt()
    assert "[MEMORY SYSTEM]" not in prompt
