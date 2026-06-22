import json
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List, Optional

from app.domain.schemas import (
    Agent, Execution, ExecutionEventCreate, Provider,
    AuditLogCreate, ApprovalRequestCreate,
)
from app.domain.enums import EventType, ApprovalStatus, ApprovalMode
from app.domain.utils import generate_id
from app.domain.utils import mask_secrets, sanitize_for_output
from app.providers import provider_registry, ChatRequest, ChatMessage, ProviderError
from app.tools.base import ToolExecutionContext
from app.tools.capabilities import CRITICAL_TOOLS, get_risk_level, get_tool_summary
from app.tools.errors import ToolError, ToolNotFoundError, ToolDeniedError
from app.tools.registry import tool_registry
from app.permissions.gate import check_tool_permission, get_available_tool_definitions
from app.memory.service import MemoryService
from app.domain.schemas import MemorySearchRequest
from app.skills.service import SkillService
from .prompt_builder import PromptBuilder
from .parser import OutputParser

MAX_STEPS = 10
TOOL_RESULT_PREVIEW_BYTES = 4_000
TOOL_MODEL_RESULT_MAX_BYTES = 12_000
TOOL_MODEL_BODY_MAX_CHARS = 8_000


def _compact_tool_result_for_model(result: Any) -> Any:
    """Keep tool feedback small enough for the next model turn."""
    original_body_chars = None
    if isinstance(result, dict) and isinstance(result.get("body"), str):
        original_body_chars = len(result["body"])

    safe_result = mask_secrets(result)
    try:
        encoded = json.dumps(safe_result, ensure_ascii=False)
    except (TypeError, ValueError):
        return {"result": str(safe_result)[:TOOL_MODEL_RESULT_MAX_BYTES], "truncated_for_model": True}

    if len(encoded) <= TOOL_MODEL_RESULT_MAX_BYTES:
        return safe_result

    if isinstance(safe_result, dict) and isinstance(safe_result.get("body"), str):
        body = safe_result["body"]
        compacted = dict(safe_result)
        compacted["body"] = body[:TOOL_MODEL_BODY_MAX_CHARS]
        compacted["body_truncated_for_model"] = True
        compacted["original_body_chars"] = original_body_chars or len(body)
        try:
            if len(json.dumps(compacted, ensure_ascii=False)) <= TOOL_MODEL_RESULT_MAX_BYTES:
                return compacted
        except (TypeError, ValueError):
            pass

    return {
        "result_preview": encoded[:TOOL_MODEL_RESULT_MAX_BYTES],
        "truncated_for_model": True,
        "original_result_chars": len(encoded),
    }


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
            data = sanitize_for_output(data)
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

    async def _execute_tool_call(
        self,
        *,
        call: Dict[str, Any],
        execution_id: str,
        agent_id: str,
        agent: Agent,
        execution: Execution,
        approval_mode: ApprovalMode,
        runtime_options: Dict[str, Any],
        messages: List[Dict],
        step: int,
    ) -> tuple[List[ExecutionEventCreate], Dict[str, Any], bool]:
        events: List[ExecutionEventCreate] = []
        call_id = str(call.get("id") or f"call_{step + 1}")
        tool_name = str(call.get("tool") or "unknown_tool")
        tool_args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}

        events.append(self._make_event(
            execution_id, EventType.TOOL_CALL_REQUESTED, "runtime", agent_id,
            {"id": call_id, "tool": tool_name, "arguments": tool_args, "step": step}
        ))

        try:
            check_tool_permission(
                tool_name, agent.capabilities, agent.explicit_tools, agent.blocked_tools,
            )
        except (ToolNotFoundError, ToolDeniedError) as exc:
            events.append(self._make_event(
                execution_id, EventType.TOOL_CALL_DENIED, "runtime", agent_id,
                {"id": call_id, "tool": tool_name, "error": exc.message, "code": exc.code}
            ))
            self._save_audit_log(
                execution_id, agent_id, "tool_call_denied",
                f"Tool '{tool_name}' denied: {exc.message}",
                {"id": call_id, "tool": tool_name, "arguments": tool_args, "code": exc.code},
            )
            return events, {
                "id": call_id,
                "tool": tool_name,
                "status": "error",
                "error": exc.message,
                "error_code": exc.code,
            }, False

        events.append(self._make_event(
            execution_id, EventType.TOOL_CALL_VALIDATED, "runtime", agent_id,
            {"id": call_id, "tool": tool_name}
        ))

        context = ToolExecutionContext(
            execution_id=execution_id,
            agent_id=agent_id,
            workspace_ids=execution.workspace_ids or [],
            db=self.db,
            approval_mode=str(approval_mode),
            extra=runtime_options,
        )
        tool = tool_registry.get(tool_name)
        is_plugin_tool = getattr(tool, "source", "") == "plugin"
        is_mcp_tool = getattr(tool, "source", "") == "mcp"
        is_critical = tool_name in CRITICAL_TOOLS or bool(getattr(tool, "critical", False))

        if is_critical:
            if approval_mode == ApprovalMode.MANUAL:
                approval_id = self._save_approval_request(
                    execution_id, agent_id, tool_name, tool_args,
                    messages, step + 1
                )
                self._save_audit_log(
                    execution_id, agent_id, "approval_requested",
                    f"Approval requested for {tool_name}",
                    {
                        "id": call_id,
                        "tool": tool_name,
                        "arguments": tool_args,
                        "approval_id": approval_id,
                        "risk_level": get_risk_level(tool_name),
                    },
                    risk_level=get_risk_level(tool_name),
                )
                events.append(self._make_event(
                    execution_id, EventType.APPROVAL_REQUESTED, "runtime", agent_id,
                    {
                        "id": call_id,
                        "approval_id": approval_id,
                        "tool": tool_name,
                        "arguments": tool_args,
                        "risk_level": get_risk_level(tool_name),
                        "summary": get_tool_summary(tool_name),
                    }
                ))
                events.append(self._make_event(
                    execution_id, EventType.EXECUTION_WAITING_APPROVAL, "orchestrator", "engine",
                    {"approval_id": approval_id}
                ))
                return events, {
                    "id": call_id,
                    "tool": tool_name,
                    "status": "waiting_approval",
                    "approval_id": approval_id,
                }, True

            self._save_audit_log(
                execution_id, agent_id, "approval_auto_granted",
                f"Auto-approved {tool_name}",
                {
                    "id": call_id,
                    "tool": tool_name,
                    "arguments": tool_args,
                    "risk_level": get_risk_level(tool_name),
                },
                risk_level=get_risk_level(tool_name),
            )
            events.append(self._make_event(
                execution_id, EventType.APPROVAL_AUTO_GRANTED, "orchestrator", "engine",
                {
                    "id": call_id,
                    "tool": tool_name,
                    "risk_level": get_risk_level(tool_name),
                }
            ))

        try:
            if is_plugin_tool:
                events.append(self._make_event(
                    execution_id, EventType.PLUGIN_TOOL_CALL_REQUESTED, "runtime", agent_id,
                    {"id": call_id, "tool": tool_name, "arguments": tool_args, "plugin_id": getattr(tool, "plugin_id", "")}
                ))
            if is_mcp_tool:
                events.append(self._make_event(
                    execution_id, EventType.MCP_TOOL_CALL_REQUESTED, "runtime", agent_id,
                    {"id": call_id, "tool": tool_name, "arguments": tool_args, "server_id": getattr(tool, "server_id", "")}
                ))
            result = await tool.execute(tool_args, context)

            result_preview = json.dumps(result, ensure_ascii=False)[:TOOL_RESULT_PREVIEW_BYTES]
            if is_plugin_tool:
                events.append(self._make_event(
                    execution_id, EventType.PLUGIN_TOOL_COMPLETED, "tool", tool_name,
                    {"id": call_id, "tool": tool_name, "plugin_id": getattr(tool, "plugin_id", ""), "result_preview": result_preview}
                ))
            if is_mcp_tool:
                events.append(self._make_event(
                    execution_id, EventType.MCP_TOOL_COMPLETED, "tool", tool_name,
                    {"id": call_id, "tool": tool_name, "server_id": getattr(tool, "server_id", ""), "result_preview": result_preview}
                ))

            events.append(self._make_event(
                execution_id, EventType.TOOL_EXECUTED, "tool", tool_name,
                {"id": call_id, "tool": tool_name, "arguments": tool_args, "status": "success"}
            ))
            events.append(self._make_event(
                execution_id, EventType.TOOL_RESULT, "tool", tool_name,
                {"id": call_id, "tool": tool_name, "result_preview": result_preview}
            ))

            self._save_audit_log(
                execution_id, agent_id, "tool_executed",
                f"Executou {tool_name}",
                {"id": call_id, "tool": tool_name, "arguments": tool_args, "result_preview": result_preview},
                risk_level=get_risk_level(tool_name) if is_critical else "low",
            )
            return events, {
                "id": call_id,
                "tool": tool_name,
                "status": "success",
                "result": _compact_tool_result_for_model(result),
            }, False

        except ToolError as exc:
            if is_plugin_tool and exc.code == "PLUGIN_DISABLED":
                events.append(self._make_event(
                    execution_id, EventType.PLUGIN_DISABLED_TOOL_BLOCKED, "tool", tool_name,
                    {"id": call_id, "tool": tool_name, "plugin_id": getattr(tool, "plugin_id", ""), "error": exc.message}
                ))
            elif is_plugin_tool:
                events.append(self._make_event(
                    execution_id, EventType.PLUGIN_TOOL_FAILED, "tool", tool_name,
                    {"id": call_id, "tool": tool_name, "plugin_id": getattr(tool, "plugin_id", ""), "error": exc.message, "code": exc.code}
                ))
            if getattr(tool, "source", "") == "mcp":
                events.append(self._make_event(
                    execution_id, EventType.MCP_TOOL_FAILED, "tool", tool_name,
                    {"id": call_id, "tool": tool_name, "server_id": getattr(tool, "server_id", ""), "error": exc.message, "code": exc.code}
                ))
            events.append(self._make_event(
                execution_id, EventType.TOOL_FAILED, "tool", tool_name,
                {"id": call_id, "tool": tool_name, "error": exc.message, "code": exc.code}
            ))
            self._save_audit_log(
                execution_id, agent_id, "tool_failed",
                f"Tool '{tool_name}' falhou: {exc.message}",
                {"id": call_id, "tool": tool_name, "arguments": tool_args, "error": exc.message, "code": exc.code},
                risk_level=get_risk_level(tool_name) if is_critical else "low",
            )
            return events, {
                "id": call_id,
                "tool": tool_name,
                "status": "error",
                "error": exc.message,
                "error_code": exc.code,
            }, False

    async def run(
        self,
        agent: Agent,
        execution: Execution,
        provider_config: Provider,
        stream: bool = True,
        initial_messages: Optional[List[Dict]] = None,
        initial_step: int = 0,
        runtime_options: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[ExecutionEventCreate, None]:
        execution_id = execution.id
        agent_id = agent.id
        approval_mode = execution.approval_mode
        runtime_options = runtime_options or {}

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
                    if (
                        runtime_options.get("include_team_memory")
                        and runtime_options.get("team_id")
                        and agent.memory_config.use_team_memory
                    ):
                        scopes.append(f"team:{runtime_options['team_id']}")

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

                skills_context = ""
                try:
                    team_skill_ids = runtime_options.get("team_skill_ids", [])
                    if not team_skill_ids and runtime_options.get("team_id") and self.db:
                        from app.db.repositories.registry import team_repo
                        team = team_repo.get(self.db, id=runtime_options["team_id"])
                        team_skill_ids = team.skills if team else []

                    skill_result = SkillService(self.db).format_skills_for_prompt(
                        agent.skills or [],
                        team_skill_ids or [],
                    )
                    skills_context = skill_result.text

                    if skill_result.loaded:
                        yield self._make_event(
                            execution_id, EventType.SKILLS_LOADED, "runtime", agent_id,
                            {"count": len(skill_result.loaded), "skills": skill_result.loaded}
                        )
                    for skill in skill_result.injected:
                        yield self._make_event(
                            execution_id, EventType.SKILL_INJECTED, "runtime", agent_id,
                            {"skill": skill}
                        )
                    if skill_result.truncated:
                        yield self._make_event(
                            execution_id, EventType.SKILLS_TRUNCATED, "runtime", agent_id,
                            {
                                "count": len(skill_result.injected),
                                "max_skills_per_prompt": SkillService.max_skills_per_prompt,
                                "max_skill_chars_per_item": SkillService.max_skill_chars_per_item,
                                "max_total_skill_chars": SkillService.max_total_skill_chars,
                            }
                        )
                except Exception as exc:
                    yield self._make_event(
                        execution_id, EventType.SKILL_LOAD_FAILED, "runtime", agent_id,
                        {"error": str(exc)}
                    )

                history = []
                if self.db:
                    try:
                        from app.runtime.history import build_conversation_history
                        history = build_conversation_history(
                            self.db,
                            getattr(execution, "conversation_id", None),
                            execution.id,
                        )
                    except Exception:
                        history = []

                builder = PromptBuilder(
                    agent,
                    execution,
                    available_tools,
                    skills_context=skills_context,
                    memory_context=memory_context,
                    operational_context=runtime_options.get("operational_context", ""),
                    history=history,
                )
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
                        reasoning_delta = getattr(chunk, "reasoning_delta", "") or ""
                        if reasoning_delta:
                            yield self._make_event(
                                execution_id, EventType.MODEL_REASONING_CHUNK, "model", provider_config.id,
                                {"delta": reasoning_delta}
                            )
                        if chunk.content_delta:
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
                    if self.parser.looks_like_truncated_tool_call(final_text):
                        # The model began a tool call but the output was cut off
                        # before the JSON closed — almost always because
                        # llm_config.max_tokens is too small for the payload (e.g.
                        # writing a whole file inline). Feed back a recovery hint
                        # and let it retry instead of silently dropping the call.
                        self._save_audit_log(
                            execution_id, agent_id, "tool_call_truncated",
                            "Tool call truncated (likely exceeded max_tokens)",
                            {"step": step, "raw_output_preview": final_text[-500:]},
                        )
                        messages.append({"role": "assistant", "content": final_text.strip()})
                        messages.append({"role": "user", "content": json.dumps({
                            "type": "tool_call_truncated",
                            "error": (
                                "Your previous response was cut off before the tool-call "
                                "JSON was complete (output token limit reached). Do NOT "
                                "resend the same large payload. If writing a large file, "
                                "split it: call filesystem.write with mode 'create_only' "
                                "for the first part, then filesystem.write with mode "
                                "'append' for each remaining part, keeping every call "
                                "small enough to finish within the output limit. Respond "
                                "with ONLY valid JSON."
                            ),
                        })})
                        continue
                    yield self._make_event(
                        execution_id, EventType.AGENT_COMPLETED, "runtime", agent_id,
                        {"result": parsed.content}
                    )
                    return

                messages.append({"role": "assistant", "content": final_text.strip()})
                tool_results = []
                for call in parsed.tool_calls:
                    events, result_payload, waiting_approval = await self._execute_tool_call(
                        call=call,
                        execution_id=execution_id,
                        agent_id=agent_id,
                        agent=agent,
                        execution=execution,
                        approval_mode=approval_mode,
                        runtime_options=runtime_options,
                        messages=messages,
                        step=step,
                    )
                    for event in events:
                        yield event
                    if waiting_approval:
                        return
                    tool_results.append(result_payload)

                if parsed.is_batch or len(tool_results) > 1:
                    messages.append({"role": "user", "content": json.dumps({
                        "type": "tool_results",
                        "results": tool_results,
                    })})
                elif tool_results:
                    result = tool_results[0]
                    if result.get("status") == "success":
                        messages.append({"role": "user", "content": json.dumps({
                            "type": "tool_result",
                            "tool": result.get("tool"),
                            "status": "success",
                            "result": result.get("result"),
                        })})
                    else:
                        messages.append({"role": "user", "content": json.dumps({
                            "type": "tool_error",
                            "tool": result.get("tool"),
                            "error": result.get("error"),
                            "error_code": result.get("error_code"),
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
