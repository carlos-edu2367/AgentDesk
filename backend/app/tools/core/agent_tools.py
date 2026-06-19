from app.db.repositories.registry import agent_repo, audit_log_repo, execution_event_repo, provider_repo
from app.domain.enums import EventType, ExecutionStatus, ExecutionType
from app.domain.schemas import Agent, Execution, ExecutionEventCreate, Provider
from app.domain.utils import generate_id
from app.runtime.agent_runtime import AgentRuntime
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolDeniedError, ToolError


DEFAULT_MAX_SUBAGENT_DEPTH = 5


def _save_event(context: ToolExecutionContext, event: ExecutionEventCreate) -> None:
    execution_event_repo.create(context.db, obj_in=event, id=generate_id("event"))


class AgentListTool(BaseTool):
    name = "agent.list"
    description = "List available agents that can be called by the current agent."
    capability = "agent_control"
    critical = False
    input_schema = {}
    output_schema = {
        "agents": [
            {"id": "agent_id", "name": "Agent name", "description": "Agent description"}
        ]
    }

    async def execute(self, arguments: dict, context: ToolExecutionContext) -> dict:
        agents = agent_repo.get_multi(context.db, limit=500)
        return {
            "agents": [
                {"id": a.id, "name": a.name, "description": a.description or ""}
                for a in agents
            ]
        }


class AgentCallTool(BaseTool):
    name = "agent.call"
    description = "Call another configured agent as a subagent and return its final result."
    capability = "agent_control"
    critical = False
    input_schema = {
        "target_agent_id": "string",
        "task": "string",
        "context": "object optional",
    }
    output_schema = {"target_agent_id": "string", "result": "string"}

    async def execute(self, arguments: dict, context: ToolExecutionContext) -> dict:
        target_agent_id = str(arguments.get("target_agent_id") or "").strip()
        task = str(arguments.get("task") or "").strip()
        extra_context = arguments.get("context") or {}

        if not target_agent_id:
            raise ToolError("INVALID_ARGUMENTS", "target_agent_id is required")
        if not task:
            raise ToolError("INVALID_ARGUMENTS", "task is required")

        caller_model = agent_repo.get(context.db, id=context.agent_id)
        if not caller_model:
            raise ToolError("CALLER_NOT_FOUND", f"Caller agent '{context.agent_id}' was not found")

        caller_subagents = caller_model.subagents or {}
        if not caller_subagents.get("can_call", True):
            raise ToolDeniedError("SUBAGENTS_DISABLED", "Caller agent cannot call subagents")

        allowed_agent_ids = caller_subagents.get("allowed_agent_ids") or ["*"]
        if "*" not in allowed_agent_ids and target_agent_id not in allowed_agent_ids:
            raise ToolDeniedError(
                "SUBAGENT_NOT_ALLOWED",
                f"Caller agent is not allowed to call '{target_agent_id}'",
            )

        depth = int(context.extra.get("subagent_depth", 0))
        max_depth = int(context.extra.get("max_subagent_depth", DEFAULT_MAX_SUBAGENT_DEPTH))
        if depth >= max_depth:
            raise ToolDeniedError("MAX_SUBAGENT_DEPTH", "Maximum subagent depth exceeded")
        subagent_calls = int(context.extra.get("subagent_calls", 0))
        max_subagent_calls = int(context.extra.get("max_subagent_calls", 20))
        if subagent_calls >= max_subagent_calls:
            raise ToolDeniedError("MAX_SUBAGENT_CALLS", "Maximum subagent call count exceeded")
        context.extra["subagent_calls"] = subagent_calls + 1

        target_model = agent_repo.get(context.db, id=target_agent_id)
        if not target_model:
            raise ToolError("SUBAGENT_NOT_FOUND", f"Target agent '{target_agent_id}' was not found")
        target_agent = Agent.model_validate(target_model)

        provider_model = provider_repo.get(context.db, id=target_agent.llm_config.provider_id)
        if not provider_model:
            raise ToolError("PROVIDER_NOT_FOUND", f"Provider '{target_agent.llm_config.provider_id}' was not found")
        provider = Provider.model_validate(provider_model)

        _save_event(context, ExecutionEventCreate(
            execution_id=context.execution_id,
            type=EventType.SUBAGENT_CALL_REQUESTED,
            source="agent",
            source_id=context.agent_id,
            content={"target_agent_id": target_agent_id, "task": task},
        ))
        if context.extra.get("team_id"):
            _save_event(context, ExecutionEventCreate(
                execution_id=context.execution_id,
                type=EventType.MEMBER_ASSIGNED,
                source="agent",
                source_id=context.agent_id,
                content={"member_agent_id": target_agent_id, "task": task, "team_id": context.extra.get("team_id")},
            ))
        _save_event(context, ExecutionEventCreate(
            execution_id=context.execution_id,
            type=EventType.SUBAGENT_STARTED,
            source="subagent",
            source_id=target_agent_id,
            content={"called_by": context.agent_id},
        ))
        if context.extra.get("team_id"):
            _save_event(context, ExecutionEventCreate(
                execution_id=context.execution_id,
                type=EventType.MEMBER_STARTED,
                source="subagent",
                source_id=target_agent_id,
                content={"called_by": context.agent_id, "team_id": context.extra.get("team_id")},
            ))
        _save_audit_log(
            context,
            "subagent_called",
            f"Subagent called: {target_agent_id}",
            {"target_agent_id": target_agent_id, "task": task, "team_id": context.extra.get("team_id")},
            risk_level="medium",
        )

        execution = Execution(
            id=context.execution_id,
            type=ExecutionType.AGENT,
            target_id=target_agent_id,
            user_input=_build_subagent_message(task, extra_context),
            status=ExecutionStatus.RUNNING,
            approval_mode=context.approval_mode,
            workspace_ids=context.workspace_ids,
            created_at=__import__("datetime").datetime.utcnow(),
            updated_at=__import__("datetime").datetime.utcnow(),
        )

        result = ""
        try:
            runtime = AgentRuntime(db_session=context.db)
            async for event in runtime.run(
                agent=target_agent,
                execution=execution,
                provider_config=provider,
                stream=False,
                runtime_options={
                    "subagent_depth": depth + 1,
                    "max_subagent_depth": max_depth,
                    "team_id": context.extra.get("team_id"),
                    "include_team_memory": bool(context.extra.get("team_id")),
                },
            ):
                _save_event(context, event)
                if event.type == EventType.AGENT_COMPLETED:
                    result = event.content.get("result", "")

            _save_event(context, ExecutionEventCreate(
                execution_id=context.execution_id,
                type=EventType.SUBAGENT_COMPLETED,
                source="subagent",
                source_id=target_agent_id,
                content={"result": result},
            ))
            if context.extra.get("team_id"):
                _save_event(context, ExecutionEventCreate(
                    execution_id=context.execution_id,
                    type=EventType.MEMBER_COMPLETED,
                    source="subagent",
                    source_id=target_agent_id,
                    content={"result": result, "team_id": context.extra.get("team_id")},
                ))
                _save_audit_log(
                    context,
                    "member_completed",
                    f"Team member completed: {target_agent_id}",
                    {"target_agent_id": target_agent_id, "team_id": context.extra.get("team_id")},
                )
        except Exception as exc:
            _save_event(context, ExecutionEventCreate(
                execution_id=context.execution_id,
                type=EventType.SUBAGENT_FAILED,
                source="subagent",
                source_id=target_agent_id,
                content={"error": str(exc)},
            ))
            if context.extra.get("team_id"):
                _save_event(context, ExecutionEventCreate(
                    execution_id=context.execution_id,
                    type=EventType.MEMBER_FAILED,
                    source="subagent",
                    source_id=target_agent_id,
                    content={"error": str(exc), "team_id": context.extra.get("team_id")},
                ))
            raise

        return {"target_agent_id": target_agent_id, "result": result}


def _build_subagent_message(task: str, context: dict) -> str:
    if not context:
        return task
    return task + "\n\n[CALL CONTEXT]\n" + str(context)


def _save_audit_log(context: ToolExecutionContext, event_type: str, summary: str, data: dict, risk_level: str = "low") -> None:
    try:
        from app.domain.schemas import AuditLogCreate

        audit_log_repo.create(context.db, obj_in=AuditLogCreate(
            execution_id=context.execution_id,
            agent_id=context.agent_id,
            event_type=event_type,
            risk_level=risk_level,
            summary=summary,
            data=data,
        ), id=generate_id("audit"))
    except Exception:
        pass
