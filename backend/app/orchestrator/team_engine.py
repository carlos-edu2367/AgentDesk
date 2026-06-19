import asyncio
from datetime import datetime

from app.db import database
from app.db.repositories.registry import (
    agent_repo,
    audit_log_repo,
    execution_repo,
    execution_event_repo,
    provider_repo,
    team_repo,
)
from app.domain.enums import EventType, ExecutionStatus
from app.domain.schemas import Agent, AuditLogCreate, ExecutionEventCreate, ExecutionUpdate, Provider
from app.domain.utils import generate_id
from app.runtime.agent_runtime import AgentRuntime
from .event_bus import event_bus


DEFAULT_MAX_SUBAGENT_DEPTH = 5
DEFAULT_MAX_SUBAGENT_CALLS = 20
DEFAULT_MAX_TEAM_STEPS = 30
DEFAULT_MAX_MEMBER_RETRIES = 2


class TeamExecutionEngine:
    async def _emit_and_save_event(self, db, execution_id: str, event_create: ExecutionEventCreate):
        event_id = generate_id("event")
        db_event = execution_event_repo.create(db, obj_in=event_create, id=event_id)
        event_dict = event_create.model_dump()
        event_dict["id"] = event_id
        event_dict["created_at"] = db_event.created_at.isoformat()
        await event_bus.publish(execution_id, event_dict)

    def _save_audit_log(self, db, execution_id: str, agent_id: str, event_type: str, summary: str, data: dict, risk_level: str = "low"):
        try:
            audit_log_repo.create(db, obj_in=AuditLogCreate(
                execution_id=execution_id,
                agent_id=agent_id,
                event_type=event_type,
                risk_level=risk_level,
                summary=summary,
                data=data,
            ), id=generate_id("audit"))
        except Exception:
            pass

    async def run_team_execution(self, execution_id: str, team_id: str, stream: bool = True):
        db = database.SessionLocal()
        try:
            execution = execution_repo.get(db, id=execution_id)
            if not execution:
                return

            team = team_repo.get(db, id=team_id)
            if not team:
                raise ValueError(f"Team {team_id} not found.")
            if team.execution_strategy != "leader_managed":
                raise ValueError("Only leader_managed team strategy is supported.")

            execution = execution_repo.update(
                db,
                db_obj=execution,
                obj_in=ExecutionUpdate(status=ExecutionStatus.RUNNING),
            )

            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.TEAM_STARTED,
                source="team",
                source_id=team_id,
                content={"team_id": team_id, "name": team.name, "strategy": team.execution_strategy},
            ))
            self._save_audit_log(
                db, execution_id, team.leader_agent_id, "team_execution_started",
                f"Team execution started: {team.name}",
                {"team_id": team_id, "strategy": team.execution_strategy},
            )

            leader_model = agent_repo.get(db, id=team.leader_agent_id)
            if not leader_model:
                raise ValueError(f"Leader agent {team.leader_agent_id} not found.")
            leader = Agent.model_validate(leader_model)
            leader = self._with_leader_permissions(leader, team.member_agent_ids or [])

            provider_model = provider_repo.get(db, id=leader.llm_config.provider_id)
            if not provider_model:
                raise ValueError(f"Provider {leader.llm_config.provider_id} not found.")
            provider = Provider.model_validate(provider_model)

            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.LEADER_STARTED,
                source="agent",
                source_id=leader.id,
                content={"team_id": team_id},
            ))

            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.LEADER_PLAN_CREATED,
                source="agent",
                source_id=leader.id,
                content={"message": "Leader received the team request and can delegate to configured members."},
            ))

            runtime = AgentRuntime(db_session=db)
            result = ""
            runtime_options = {
                "team_id": team_id,
                "include_team_memory": bool((team.memory_config or {}).get("use_team_memory", True)),
                "subagent_depth": 0,
                "max_subagent_depth": DEFAULT_MAX_SUBAGENT_DEPTH,
                "max_subagent_calls": DEFAULT_MAX_SUBAGENT_CALLS,
                "max_team_steps": DEFAULT_MAX_TEAM_STEPS,
                "max_member_retries": DEFAULT_MAX_MEMBER_RETRIES,
                "operational_context": self._build_team_context(db, team),
            }

            async for event in runtime.run(
                agent=leader,
                execution=execution,
                provider_config=provider,
                stream=stream,
                runtime_options=runtime_options,
            ):
                await self._emit_and_save_event(db, execution_id, event)
                if event.type == EventType.EXECUTION_WAITING_APPROVAL:
                    execution_repo.update(db, db_obj=execution, obj_in=ExecutionUpdate(status=ExecutionStatus.WAITING_APPROVAL))
                    return
                if event.type == EventType.AGENT_COMPLETED:
                    result = event.content.get("result", "")

            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.LEADER_REVIEW_STARTED,
                source="agent",
                source_id=leader.id,
                content={"team_id": team_id},
            ))
            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.LEADER_FINALIZED,
                source="agent",
                source_id=leader.id,
                content={"result": result},
            ))
            await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
                execution_id=execution_id,
                type=EventType.TEAM_COMPLETED,
                source="team",
                source_id=team_id,
                content={"result": result},
            ))
            execution_repo.update(db, db_obj=execution, obj_in=ExecutionUpdate(
                status=ExecutionStatus.COMPLETED,
                result=result,
                completed_at=datetime.utcnow(),
            ))
            self._save_audit_log(
                db, execution_id, leader.id, "team_completed",
                f"Team execution completed: {team.name}",
                {"team_id": team_id},
            )

        except Exception as exc:
            await self._fail_execution(db, execution_id, team_id, str(exc))
        finally:
            await asyncio.sleep(0.5)
            await event_bus.publish(execution_id, {"type": "sse_close_connection"})
            db.close()

    def _with_leader_permissions(self, leader: Agent, member_agent_ids: list[str]) -> Agent:
        explicit_tools = list(leader.explicit_tools or [])
        if "agent.call" not in explicit_tools and "agent.call" not in (leader.blocked_tools or []):
            explicit_tools.append("agent.call")

        subagents = leader.subagents.model_copy(update={
            "can_call": True,
            "allowed_agent_ids": member_agent_ids or leader.subagents.allowed_agent_ids,
        })
        return leader.model_copy(update={"explicit_tools": explicit_tools, "subagents": subagents})

    def _build_team_context(self, db, team) -> str:
        lines = [
            "[TEAM CONTEXT]",
            "Voce e o agente chefe deste time.",
            "",
            "Sua funcao:",
            "- Entender a solicitacao do usuario.",
            "- Dividir a tarefa entre agentes membros quando util.",
            "- Delegar tarefas com instrucoes claras.",
            "- Revisar respostas dos membros.",
            "- Consolidar uma resposta final.",
            "",
            "Voce pode chamar os seguintes membros:",
        ]
        for member_id in team.member_agent_ids or []:
            member = agent_repo.get(db, id=member_id)
            if member:
                lines.append(f"- {member.id}: {member.name}")
            else:
                lines.append(f"- {member_id}")
        lines.extend(["", f"Estrategia do time: {team.execution_strategy}"])
        return "\n".join(lines)

    async def _fail_execution(self, db, execution_id: str, team_id: str, error: str):
        await self._emit_and_save_event(db, execution_id, ExecutionEventCreate(
            execution_id=execution_id,
            type=EventType.TEAM_FAILED,
            source="team",
            source_id=team_id,
            content={"error": error},
        ))
        execution = execution_repo.get(db, id=execution_id)
        if execution:
            execution_repo.update(db, db_obj=execution, obj_in=ExecutionUpdate(
                status=ExecutionStatus.FAILED,
                error=error,
                completed_at=datetime.utcnow(),
            ))
        self._save_audit_log(
            db, execution_id, team_id, "team_failed",
            f"Team execution failed: {error}",
            {"team_id": team_id, "error": error},
            risk_level="medium",
        )


team_execution_engine = TeamExecutionEngine()
