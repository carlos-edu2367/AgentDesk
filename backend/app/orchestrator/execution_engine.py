import asyncio
import json
from datetime import datetime

from app.db import database
from app.db.repositories.registry import (
    execution_repo, execution_event_repo, agent_repo,
    provider_repo, approval_repo,
)
from app.domain.schemas import ExecutionEventCreate, Provider, Agent, ExecutionUpdate, AuditLogCreate, ApprovalRequestUpdate
from app.domain.enums import EventType, ExecutionStatus, ApprovalStatus
from app.domain.utils import generate_id
from app.domain.utils import sanitize_for_output
from app.runtime.agent_runtime import AgentRuntime
from app.tools.base import ToolExecutionContext
from app.tools.registry import tool_registry
from app.tools.errors import ToolError
from app.tools.capabilities import get_risk_level
from .event_bus import event_bus


class ExecutionEngine:
    def __init__(self):
        self._cancelled_executions = set()

    def cancel_execution(self, execution_id: str):
        self._cancelled_executions.add(execution_id)

    def is_cancelled(self, execution_id: str) -> bool:
        return execution_id in self._cancelled_executions

    async def _emit_and_save_event(self, db, execution_id: str, event_create: ExecutionEventCreate):
        new_id = generate_id("event")
        db_event = execution_event_repo.create(db, obj_in=event_create, id=new_id)

        event_dict = event_create.model_dump()
        event_dict["id"] = new_id
        event_dict["created_at"] = db_event.created_at.isoformat()
        await event_bus.publish(execution_id, event_dict)

    def _save_audit_log(self, db, execution_id: str, agent_id: str, event_type: str, summary: str, data: dict, risk_level: str = "low"):
        try:
            from app.db.repositories.registry import audit_log_repo
            log_in = AuditLogCreate(
                execution_id=execution_id,
                agent_id=agent_id,
                event_type=event_type,
                risk_level=risk_level,
                summary=summary,
                data=sanitize_for_output(data),
            )
            audit_log_repo.create(db, obj_in=log_in, id=generate_id("audit"))
        except Exception:
            pass

    async def run_agent_execution(self, execution_id: str, agent_id: str, stream: bool = True):
        db = database.SessionLocal()
        try:
            execution = execution_repo.get(db, id=execution_id)
            if not execution:
                return

            execution = execution_repo.update(db, db_obj=execution, obj_in=ExecutionUpdate(status=ExecutionStatus.RUNNING))

            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.EXECUTION_STARTED,
                source="orchestrator",
                source_id="engine",
                content={}
            ))

            agent_model = agent_repo.get(db, id=agent_id)
            if not agent_model:
                raise ValueError(f"Agent {agent_id} not found.")
            agent = Agent.model_validate(agent_model)

            provider_model = provider_repo.get(db, id=agent.llm_config.provider_id)
            if not provider_model:
                raise ValueError(f"Provider {agent.llm_config.provider_id} not found.")
            provider_config = Provider.model_validate(provider_model)

            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.AGENT_STARTED,
                source="orchestrator",
                source_id=agent_id,
                content={"provider_id": provider_config.id, "model": agent.llm_config.model}
            ))

            final_result = await self._run_runtime_loop(
                db, execution_id, agent, provider_config, stream
            )

            if final_result is None:
                # Execution was paused for approval; don't complete it
                return

            await self._finish_execution(db, execution_id, final_result)

        except Exception as e:
            await self._fail_execution(db, execution_id, str(e))
        finally:
            self._cleanup(execution_id)
            await asyncio.sleep(0.5)
            await event_bus.publish(execution_id, {"type": "sse_close_connection"})
            db.close()

    async def resume_agent_execution(
        self, execution_id: str, approval_id: str,
        approved: bool, rejection_reason: str = "", stream: bool = True
    ):
        """Called after a user approves or rejects a pending tool approval."""
        db = database.SessionLocal()
        try:
            execution = execution_repo.get(db, id=execution_id)
            if not execution:
                return

            approval = approval_repo.get(db, id=approval_id)
            if not approval:
                return

            agent_model = agent_repo.get(db, id=execution.target_id)
            if not agent_model:
                raise ValueError(f"Agent {execution.target_id} not found.")
            agent = Agent.model_validate(agent_model)

            provider_model = provider_repo.get(db, id=agent.llm_config.provider_id)
            if not provider_model:
                raise ValueError(f"Provider {agent.llm_config.provider_id} not found.")
            provider_config = Provider.model_validate(provider_model)

            execution = execution_repo.update(
                db, db_obj=execution,
                obj_in=ExecutionUpdate(status=ExecutionStatus.RUNNING)
            )

            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.EXECUTION_RESUMED,
                source="orchestrator",
                source_id="engine",
                content={"approval_id": approval_id, "approved": approved}
            ))

            pending_state = approval.pending_state or {}
            messages = pending_state.get("messages", [])
            step = pending_state.get("step", 0)

            tool_name = approval.tool
            tool_args = approval.arguments or {}

            if not approved:
                approval_repo.update(db, db_obj=approval, obj_in=ApprovalRequestUpdate(
                    status=ApprovalStatus.REJECTED,
                    rejection_reason=rejection_reason,
                    resolved_at=datetime.utcnow(),
                ))
                await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                    execution_id=execution_id,
                    type=EventType.APPROVAL_REJECTED,
                    source="orchestrator",
                    source_id="engine",
                    content={"approval_id": approval_id, "tool": tool_name, "reason": rejection_reason}
                ))
                self._save_audit_log(
                    db, execution_id, agent.id, "approval_rejected",
                    f"User rejected {tool_name}",
                    {"tool": tool_name, "reason": rejection_reason, "approval_id": approval_id},
                    risk_level=get_risk_level(tool_name),
                )
                messages.append({"role": "user", "content": json.dumps({
                    "type": "tool_rejected",
                    "tool": tool_name,
                    "reason": rejection_reason or "User rejected the action.",
                })})
            else:
                approval_repo.update(db, db_obj=approval, obj_in=ApprovalRequestUpdate(
                    status=ApprovalStatus.APPROVED,
                    resolved_at=datetime.utcnow(),
                ))
                await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                    execution_id=execution_id,
                    type=EventType.APPROVAL_APPROVED,
                    source="orchestrator",
                    source_id="engine",
                    content={"approval_id": approval_id, "tool": tool_name}
                ))
                self._save_audit_log(
                    db, execution_id, agent.id, "approval_approved",
                    f"User approved {tool_name}",
                    {"tool": tool_name, "approval_id": approval_id},
                    risk_level=get_risk_level(tool_name),
                )

                context = ToolExecutionContext(
                    execution_id=execution_id,
                    agent_id=agent.id,
                    workspace_ids=list(execution.workspace_ids or []),
                    db=db,
                    approval_mode=str(execution.approval_mode),
                )

                try:
                    tool = tool_registry.get(tool_name)
                    result = await tool.execute(tool_args, context)
                    result_preview = json.dumps(result, ensure_ascii=False)[:4_000]

                    await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                        execution_id=execution_id,
                        type=EventType.TOOL_EXECUTED,
                        source="tool",
                        source_id=tool_name,
                        content={"tool": tool_name, "arguments": tool_args, "status": "success"}
                    ))
                    await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                        execution_id=execution_id,
                        type=EventType.TOOL_RESULT,
                        source="tool",
                        source_id=tool_name,
                        content={"tool": tool_name, "result_preview": result_preview}
                    ))
                    self._save_audit_log(
                        db, execution_id, agent.id, "tool_executed",
                        f"Executou {tool_name} após aprovação",
                        {"tool": tool_name, "arguments": tool_args, "result_preview": result_preview},
                        risk_level=get_risk_level(tool_name),
                    )
                    messages.append({"role": "user", "content": json.dumps({
                        "type": "tool_result",
                        "tool": tool_name,
                        "status": "success",
                        "result": result,
                    })})

                except ToolError as exc:
                    await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                        execution_id=execution_id,
                        type=EventType.TOOL_FAILED,
                        source="tool",
                        source_id=tool_name,
                        content={"tool": tool_name, "error": exc.message, "code": exc.code}
                    ))
                    self._save_audit_log(
                        db, execution_id, agent.id, "tool_failed",
                        f"Tool '{tool_name}' falhou após aprovação: {exc.message}",
                        {"tool": tool_name, "arguments": tool_args, "error": exc.message},
                        risk_level=get_risk_level(tool_name),
                    )
                    messages.append({"role": "user", "content": json.dumps({
                        "type": "tool_error",
                        "tool": tool_name,
                        "error": exc.message,
                        "error_code": exc.code,
                    })})

            # Continue the runtime from stored state
            final_result = await self._run_runtime_loop(
                db, execution_id, agent, provider_config, stream,
                initial_messages=messages, initial_step=step
            )

            if final_result is None:
                return  # Another approval was requested

            await self._finish_execution(db, execution_id, final_result)

        except Exception as e:
            await self._fail_execution(db, execution_id, str(e))
        finally:
            self._cleanup(execution_id)
            await asyncio.sleep(0.5)
            await event_bus.publish(execution_id, {"type": "sse_close_connection"})
            db.close()

    async def _run_runtime_loop(
        self, db, execution_id: str, agent: Agent, provider_config: Provider,
        stream: bool, initial_messages=None, initial_step: int = 0
    ):
        """Runs the agent runtime loop and returns final_result or None if paused for approval."""
        execution = execution_repo.get(db, id=execution_id)
        runtime = AgentRuntime(db_session=db)
        final_result = ""

        async for event in runtime.run(
            agent=agent, execution=execution, provider_config=provider_config,
            stream=stream, initial_messages=initial_messages, initial_step=initial_step
        ):
            if self.is_cancelled(execution_id):
                await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                    execution_id=execution_id,
                    type=EventType.EXECUTION_CANCELLED,
                    source="orchestrator",
                    source_id="engine",
                    content={"reason": "User cancelled execution"}
                ))
                execution_repo.update(db, db_obj=execution, obj_in=ExecutionUpdate(
                    status=ExecutionStatus.CANCELLED,
                    completed_at=datetime.utcnow()
                ))
                return None

            await self._emit_and_save_event(db, execution_id, event)

            if event.type == EventType.AGENT_COMPLETED:
                final_result = event.content.get("result", "")
            elif event.type == EventType.EXECUTION_WAITING_APPROVAL:
                # Pause: update execution status, let endpoint handle resumption
                execution_repo.update(db, db_obj=execution, obj_in=ExecutionUpdate(
                    status=ExecutionStatus.WAITING_APPROVAL
                ))
                return None  # Signal that execution is paused

        return final_result

    async def _finish_execution(self, db, execution_id: str, final_result: str):
        execution = execution_repo.get(db, id=execution_id)
        await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
            execution_id=execution_id,
            type=EventType.EXECUTION_COMPLETED,
            source="orchestrator",
            source_id="engine",
            content={"result": final_result}
        ))
        if execution:
            execution_repo.update(db, db_obj=execution, obj_in=ExecutionUpdate(
                status=ExecutionStatus.COMPLETED,
                result=final_result,
                completed_at=datetime.utcnow()
            ))

    async def _fail_execution(self, db, execution_id: str, error: str):
        await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
            execution_id=execution_id,
            type=EventType.EXECUTION_FAILED,
            source="orchestrator",
            source_id="engine",
            content={"error": error}
        ))
        execution = execution_repo.get(db, id=execution_id)
        if execution:
            execution_repo.update(db, db_obj=execution, obj_in=ExecutionUpdate(
                status=ExecutionStatus.FAILED,
                error=error,
                completed_at=datetime.utcnow()
            ))

    def _cleanup(self, execution_id: str):
        if execution_id in self._cancelled_executions:
            self._cancelled_executions.remove(execution_id)


execution_engine = ExecutionEngine()
