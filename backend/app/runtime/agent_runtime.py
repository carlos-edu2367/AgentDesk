import json
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List, Optional

from app.domain.schemas import (
    Agent, Execution, ExecutionEventCreate, Provider,
    AuditLogCreate, ApprovalRequestCreate,
)
from app.domain.enums import EventType, ApprovalStatus, ApprovalMode
from app.domain.utils import generate_id
from app.providers import provider_registry, ChatRequest, ChatMessage, ProviderError
from app.tools.base import ToolExecutionContext
from app.tools.capabilities import CRITICAL_TOOLS, get_risk_level, get_tool_summary
from app.tools.errors import ToolError, ToolNotFoundError, ToolDeniedError
from app.tools.registry import tool_registry
from app.permissions.gate import check_tool_permission, get_available_tool_definitions
from app.memory.service import MemoryService
from app.domain.schemas import MemorySearchRequest
from .prompt_builder import PromptBuilder
from .parser import OutputParser

MAX_STEPS = 10
TOOL_RESULT_PREVIEW_BYTES = 4_000


class AgentRuntime:
    def __init__(self, db_session=None):
        self.db = db_session
        self.parser = OutputParser()

    def _save_audit_log(
        self, execution_id: str, agent_id: str, event_type: str,
        summary: str, data: dict, risk_level: str = "low"
    ):
        if not self.db:
            return
        try:
            from app.db.repositories.registry import audit_log_repo
            log_in = AuditLogCreate(
                execution_id=execution_id,
                agent_id=agent_id,
                event_type=event_type,
                risk_level=risk_level,
                summary=summary,
                data=data,
            )
            audit_log_repo.create(self.db, obj_in=log_in, id=generate_id("audit"))
        except Exception:
            pass  # Audit log failure must not crash the execution

    def _save_approval_request(
        self, execution_id: str, agent_id: str, tool_name: str,
        tool_args: dict, messages: List[Dict], step: int
    ) -> str:
        """Persists an approval request and returns its ID."""
        approval_id = generate_id("approval")
        if not self.db:
            return approval_id
        try:
            from app.db.repositories.registry import approval_repo
            approval_in = ApprovalRequestCreate(
                execution_id=execution_id,
                agent_id=agent_id,
                tool=tool_name,
                status=ApprovalStatus.PENDING,
                risk_level=get_risk_level(tool_name),
                summary=get_tool_summary(tool_name),
                arguments=tool_args,
                pending_state={"messages": messages, "step": step},
            )
            approval_repo.create(self.db, obj_in=approval_in, id=approval_id)
        except Exception:
            pass
        return approval_id

    def _make_event(
        self, execution_id: str, event_type: EventType,
        source: str, source_id: str, content: dict
    ) -> ExecutionEventCreate:
        return ExecutionEventCreate(
            execution_id=execution_id,
            type=event_type,
            source=source,
            source_id=source_id,
            content=content,
        )

    async def run(
        self,
        agent: Agent,
        execution: Execution,
        provider_config: Provider,
        stream: bool = True,
        initial_messages: Optional[List[Dict]] = None,
        initial_step: int = 0,
    ) -> AsyncGenerator[ExecutionEventCreate, None]:
        execution_id = execution.id
        agent_id = agent.id
        approval_mode = execution.approval_mode

        try:
            provider = provider_registry.get(provider_config)

            available_tools = get_available_tool_definitions(
                agent.capabilities,
                agent.explicit_tools,
                agent.blocked_tools,
            )

            if initial_messages is not None:
                messages = initial_messages
            else:
                # Memory lookup before prompt build
                memory_context = ""
                try:
                    memory_svc = MemoryService(self.db)
                    scopes = []
                    if agent.memory_config.use_global:
                        scopes.append("global")
                    if agent.memory_config.use_agent_memory:
                        scopes.append(f"agent:{agent_id}")

                    if scopes:
                        yield self._make_event(
                            execution_id, EventType.MEMORY_LOOKUP, "runtime", agent_id,
                            {"scopes": scopes, "query": execution.user_input}
                        )
                        search_req = MemorySearchRequest(
                            query=execution.user_input,
                            scopes=scopes,
                            mode="hybrid",
                            limit=8,
                        )
                        search_resp = await memory_svc.search(search_req)
                        memory_context = memory_svc.format_memories_for_prompt(search_resp.results)

                        yield self._make_event(
                            execution_id, EventType.MEMORY_LOOKUP_RESULT, "runtime", agent_id,
                            {"count": len(search_resp.results), "has_context": bool(memory_context)}
                        )

                        for result in search_resp.results:
                            memory_svc.record_usage(result.memory_id, execution_id, agent_id, result.score)

                        if search_resp.results:
                            yield self._make_event(
                                execution_id, EventType.MEMORY_USAGE_RECORDED, "runtime", agent_id,
                                {"memory_ids": [r.memory_id for r in search_resp.results]}
                            )
                except Exception:
                    pass  # Memory failure must never crash execution

                builder = PromptBuilder(agent, execution, available_tools, memory_context=memory_context)
                messages = builder.build_messages()
                yield self._make_event(
                    execution_id, EventType.PROMPT_BUILT, "runtime", agent_id,
                    {"messages": messages, "available_tools": [t.name for t in available_tools]}
                )

            for step in range(initial_step, MAX_STEPS):
                yield self._make_event(
                    execution_id, EventType.MODEL_REQUEST_STARTED, "runtime", provider_config.id,
                    {"model": agent.llm_config.model, "step": step, "stream": stream}
                )

                request = ChatRequest(
                    provider_id=provider_config.id,
                    model=agent.llm_config.model,
                    messages=[ChatMessage(role=m["role"], content=m["content"]) for m in messages],
                    temperature=agent.llm_config.temperature,
                    top_p=agent.llm_config.top_p,
                    context_window=agent.llm_config.context_window,
                    max_tokens=agent.llm_config.max_tokens,
                    stream=stream,
                )

                final_text = ""
                if stream:
                    async for chunk in provider.stream_chat(request):
                        final_text += chunk.content_delta
                        yield self._make_event(
                            execution_id, EventType.MODEL_CHUNK, "model", provider_config.id,
                            {"delta": chunk.content_delta}
                        )
                else:
                    response = await provider.chat(request)
                    final_text = response.content

                yield self._make_event(
                    execution_id, EventType.MODEL_COMPLETED, "model", provider_config.id,
                    {"raw_output": final_text}
                )

                parsed = self.parser.parse(final_text)

                if not parsed.is_tool_call:
                    yield self._make_event(
                        execution_id, EventType.AGENT_COMPLETED, "runtime", agent_id,
                        {"result": parsed.content}
                    )
                    return

                tool_name = parsed.tool_name
                tool_args = parsed.arguments

                yield self._make_event(
                    execution_id, EventType.TOOL_CALL_REQUESTED, "runtime", agent_id,
                    {"tool": tool_name, "arguments": tool_args, "step": step}
                )

                messages.append({"role": "assistant", "content": final_text.strip()})

                try:
                    check_tool_permission(
                        tool_name, agent.capabilities, agent.explicit_tools, agent.blocked_tools,
                    )
                except (ToolNotFoundError, ToolDeniedError) as exc:
                    yield self._make_event(
                        execution_id, EventType.TOOL_CALL_DENIED, "runtime", agent_id,
                        {"tool": tool_name, "error": exc.message, "code": exc.code}
                    )
                    self._save_audit_log(
                        execution_id, agent_id, "tool_call_denied",
                        f"Tool '{tool_name}' denied: {exc.message}",
                        {"tool": tool_name, "arguments": tool_args, "code": exc.code},
                    )
                    messages.append({"role": "user", "content": json.dumps({
                        "type": "tool_error",
                        "tool": tool_name,
                        "error": exc.message,
                        "error_code": exc.code,
                    })})
                    continue

                yield self._make_event(
                    execution_id, EventType.TOOL_CALL_VALIDATED, "runtime", agent_id,
                    {"tool": tool_name}
                )

                context = ToolExecutionContext(
                    execution_id=execution_id,
                    agent_id=agent_id,
                    workspace_ids=execution.workspace_ids or [],
                    db=self.db,
                    approval_mode=str(approval_mode),
                )

                # --- Approval gate for critical tools ---
                if tool_name in CRITICAL_TOOLS:
                    if approval_mode == ApprovalMode.MANUAL:
                        approval_id = self._save_approval_request(
                            execution_id, agent_id, tool_name, tool_args,
                            messages, step + 1
                        )
                        self._save_audit_log(
                            execution_id, agent_id, "approval_requested",
                            f"Approval requested for {tool_name}",
                            {
                                "tool": tool_name, "arguments": tool_args,
                                "approval_id": approval_id,
                                "risk_level": get_risk_level(tool_name),
                            },
                            risk_level=get_risk_level(tool_name),
                        )
                        yield self._make_event(
                            execution_id, EventType.APPROVAL_REQUESTED, "runtime", agent_id,
                            {
                                "approval_id": approval_id,
                                "tool": tool_name,
                                "arguments": tool_args,
                                "risk_level": get_risk_level(tool_name),
                                "summary": get_tool_summary(tool_name),
                            }
                        )
                        yield self._make_event(
                            execution_id, EventType.EXECUTION_WAITING_APPROVAL, "orchestrator", "engine",
                            {"approval_id": approval_id}
                        )
                        return  # Stop; engine will resume after approval

                    else:
                        # Auto-approval
                        self._save_audit_log(
                            execution_id, agent_id, "approval_auto_granted",
                            f"Auto-approved {tool_name}",
                            {
                                "tool": tool_name, "arguments": tool_args,
                                "risk_level": get_risk_level(tool_name),
                            },
                            risk_level=get_risk_level(tool_name),
                        )
                        yield self._make_event(
                            execution_id, EventType.APPROVAL_AUTO_GRANTED, "orchestrator", "engine",
                            {
                                "tool": tool_name,
                                "risk_level": get_risk_level(tool_name),
                            }
                        )

                # --- Execute tool ---
                try:
                    tool = tool_registry.get(tool_name)
                    result = await tool.execute(tool_args, context)

                    result_preview = json.dumps(result, ensure_ascii=False)[:TOOL_RESULT_PREVIEW_BYTES]

                    yield self._make_event(
                        execution_id, EventType.TOOL_EXECUTED, "tool", tool_name,
                        {"tool": tool_name, "arguments": tool_args, "status": "success"}
                    )
                    yield self._make_event(
                        execution_id, EventType.TOOL_RESULT, "tool", tool_name,
                        {"tool": tool_name, "result_preview": result_preview}
                    )

                    self._save_audit_log(
                        execution_id, agent_id, "tool_executed",
                        f"Executou {tool_name}",
                        {"tool": tool_name, "arguments": tool_args, "result_preview": result_preview},
                        risk_level=get_risk_level(tool_name) if tool_name in CRITICAL_TOOLS else "low",
                    )

                    messages.append({"role": "user", "content": json.dumps({
                        "type": "tool_result",
                        "tool": tool_name,
                        "status": "success",
                        "result": result,
                    })})

                except ToolError as exc:
                    yield self._make_event(
                        execution_id, EventType.TOOL_FAILED, "tool", tool_name,
                        {"tool": tool_name, "error": exc.message, "code": exc.code}
                    )
                    self._save_audit_log(
                        execution_id, agent_id, "tool_failed",
                        f"Tool '{tool_name}' falhou: {exc.message}",
                        {"tool": tool_name, "arguments": tool_args, "error": exc.message, "code": exc.code},
                        risk_level=get_risk_level(tool_name) if tool_name in CRITICAL_TOOLS else "low",
                    )
                    messages.append({"role": "user", "content": json.dumps({
                        "type": "tool_error",
                        "tool": tool_name,
                        "error": exc.message,
                        "error_code": exc.code,
                    })})

            yield self._make_event(
                execution_id, EventType.AGENT_COMPLETED, "runtime", agent_id,
                {"result": "Execution reached maximum steps without a final answer."}
            )

        except ProviderError as exc:
            yield self._make_event(
                execution_id, EventType.ERROR, "runtime", "provider",
                {"error": exc.message, "details": exc.details}
            )
        except Exception as exc:
            yield self._make_event(
                execution_id, EventType.ERROR, "runtime", "system",
                {"error": str(exc)}
            )
