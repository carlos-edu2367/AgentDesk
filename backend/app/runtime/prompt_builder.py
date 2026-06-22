import json
from typing import Dict, List, Any

from app.domain.schemas import Agent, Execution
from app.tools.schemas import ToolDefinition


class PromptBuilder:
    def __init__(
        self,
        agent: Agent,
        execution: Execution,
        available_tools: List[ToolDefinition] = None,
        skills_context: str = "",
        memory_context: str = "",
        operational_context: str = "",
        history: List[Dict[str, str]] = None,
    ):
        self.agent = agent
        self.execution = execution
        self.available_tools = available_tools or []
        self.skills_context = skills_context
        self.memory_context = memory_context
        self.operational_context = operational_context
        self.history = history or []

    def _get_system_rules(self) -> str:
        if self.available_tools:
            return """[AGENTDESK SYSTEM RULES]
You are an autonomous AI Agent running within the AgentDesk platform.
- You must answer user requests clearly and accurately.
- DO NOT pretend to execute actions that are not possible or haven't been completed.
- DO NOT invent results of external actions.
- When you need to use a tool, respond ONLY with the JSON tool call format described below.
- When you have your final answer, respond ONLY with the JSON final answer format.
"""
        return """[AGENTDESK SYSTEM RULES]
You are an autonomous AI Agent running within the AgentDesk platform.
- You must answer user requests clearly and accurately.
- DO NOT pretend to execute actions that are not possible or haven't been completed.
- You DO NOT have access to tools, terminal, or file system modifications.
- If a user asks you to perform an external action (like reading a file or running a command), explain that you cannot do that.
- DO NOT invent results of external actions.
"""

    def _get_agent_system_prompt(self) -> str:
        if not self.agent.system_prompt:
            return ""
        return f"""[AGENT SYSTEM PROMPT]
{self.agent.system_prompt}
"""

    def _get_operation_mode(self) -> str:
        return f"""[OPERATION MODE]
Approval Mode: {self.execution.approval_mode}
"""

    def _get_execution_context(self) -> str:
        context = "[EXECUTION CONTEXT]\n"
        context += "Workspace IDs: " + (", ".join(self.execution.workspace_ids) if self.execution.workspace_ids else "None") + "\n"
        return context

    def _get_operational_context(self) -> str:
        return self.operational_context

    def _get_tools_instructions(self) -> str:
        if not self.available_tools:
            return ""

        lines = ["[AVAILABLE TOOLS]"]
        lines.append("You have access to the following tools. To call one tool, respond with ONLY this JSON format:")
        lines.append('{"type": "tool_call", "tool": "<tool_name>", "arguments": {<args>}}')
        lines.append("")
        lines.append("To call multiple independent tools in the same step, respond with ONLY this JSON format:")
        lines.append('{"type": "tool_calls", "calls": [{"id": "call_1", "tool": "<tool_name>", "arguments": {<args>}}, {"id": "call_2", "tool": "<tool_name>", "arguments": {<args>}}]}')
        lines.append("AgentDesk will return all results together as tool_results. After reading them, you may call more tools if context is still incomplete.")
        lines.append("")
        lines.append("When you have your final answer, respond with ONLY:")
        lines.append('{"type": "final_answer", "content": "<your answer>"}')
        lines.append("")
        if any(tool.name == "agent.call" for tool in self.available_tools):
            lines.append("To delegate to a subagent, you may also respond with ONLY:")
            lines.append('{"type": "subagent_call", "target_agent_id": "<agent_id>", "task": "<clear task>"}')
            lines.append("")
        lines.append("Available tools:")

        for tool in self.available_tools:
            lines.append(f"\n- {tool.name}: {tool.description}")
            if tool.input_schema:
                schema_str = json.dumps(tool.input_schema, ensure_ascii=False)
                lines.append(f"  Arguments: {schema_str}")

        lines.append("")
        lines.append("IMPORTANT: Respond with ONLY valid JSON. Do not add explanations outside the JSON.")
        return "\n".join(lines)

    def _has_memory_tools(self) -> bool:
        return any(t.name.startswith("memory.") for t in self.available_tools)

    def _get_memory_instructions(self) -> str:
        if not self._has_memory_tools():
            return ""
        return """[MEMORY SYSTEM]
You have a long-term memory. Use it proactively across turns.

When to WRITE (memory.create):
- Whenever you learn a durable fact about the user: their name, role, language, preferences, tools/stack they use, recurring projects, goals, or constraints.
- Decisions made, lessons learned, and workflows worth reusing later.
Do NOT store secrets, passwords, or ephemeral chit-chat. Store one clear fact per memory, with a short descriptive title.

When to UPDATE (memory.update) / DELETE (memory.delete):
- If a known fact changed, update the existing memory instead of creating a duplicate.
- If a fact is wrong or obsolete, delete it. Use memory.list or memory.search first to find the memory_id.

Scope & type:
- scope "global" for facts about the user/environment that any agent should know; scope "agent" for facts specific to you.
- type: "profile" (who the user is), "preference" (how they like things), "project", "decision", "lesson", "workflow".

Relevant memories already retrieved for this turn appear under [RELEVANT MEMORIES]. Trust them, and silently record any new durable facts you learn — never ask the user for permission to remember.
"""

    def _get_memory_context(self) -> str:
        return self.memory_context

    def _get_skills_context(self) -> str:
        return self.skills_context

    def _get_user_request(self) -> str:
        return self.execution.user_input

    def build_system_prompt(self) -> str:
        parts = [
            self._get_system_rules(),
            self._get_agent_system_prompt(),
            self._get_operation_mode(),
            self._get_operational_context(),
            self._get_tools_instructions(),
            self._get_skills_context(),
            self._get_memory_instructions(),
            self._get_memory_context(),
            self._get_execution_context(),
        ]
        return "\n".join(filter(None, parts))

    def build_messages(self) -> List[Dict[str, str]]:
        messages = []
        sys_prompt = self.build_system_prompt()
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.extend(self.history)
        messages.append({"role": "user", "content": self._get_user_request()})
        return messages
