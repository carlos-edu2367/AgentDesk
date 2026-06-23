"""The Stop button must also cancel team (leader-managed) executions.

Cancellation is tracked on the shared registry owned by `execution_engine`, so a
single `POST /executions/{id}/cancel` works for both agent and team runs. Before
the fix the team engine never consulted that registry, so stopping a team chat
did nothing.
"""

import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.repositories.registry import (
    agent_repo,
    execution_event_repo,
    execution_repo,
    provider_repo,
    team_repo,
)
from app.domain import schemas
from app.domain.enums import (
    EventType,
    ExecutionStatus,
    ExecutionType,
    ProviderType,
)
from app.orchestrator.execution_engine import execution_engine
from app.orchestrator.team_engine import team_execution_engine


def _seed(db):
    provider_repo.create(
        db,
        obj_in=schemas.ProviderCreate(
            type=ProviderType.OLLAMA,
            name="Mock Provider",
            enabled=True,
            config={"mock_response_text": "ok", "mock_chunks": ["ok"]},
        ),
        id="prov_1",
    )
    agent_repo.create(
        db,
        obj_in=schemas.AgentCreate(
            name="Leader",
            model_config=schemas.ModelConfig(provider_id="prov_1", model="mock"),
        ),
        id="agent_leader",
    )
    team_repo.create(
        db,
        obj_in=schemas.TeamCreate(name="Team", leader_agent_id="agent_leader"),
        id="team_1",
    )
    execution_repo.create(
        db,
        obj_in=schemas.ExecutionCreate(
            type=ExecutionType.TEAM,
            target_id="team_1",
            user_input="do work",
            status=ExecutionStatus.PENDING,
        ),
        id="exec_team",
    )
    db.commit()


async def _endless_leader_run(*args, **kwargs):
    """Stand-in for the leader runtime that keeps emitting events so the cancel
    check has something to interrupt."""
    for _ in range(50):
        yield schemas.ExecutionEventCreate(
            execution_id="exec_team",
            type=EventType.MODEL_CHUNK,
            source="agent",
            source_id="agent_leader",
            content={"delta": "..."},
        )


@pytest.mark.asyncio
async def test_team_execution_honors_cancellation(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    _seed(db)

    # The engine opens its own session via database.SessionLocal(); point it at
    # our shared in-memory DB.
    monkeypatch.setattr("app.db.database.SessionLocal", SessionLocal)
    monkeypatch.setattr(
        "app.orchestrator.team_engine.AgentRuntime.run",
        lambda self, *a, **k: _endless_leader_run(*a, **k),
    )

    # Pre-mark the run as cancelled (as if the user hit Stop the instant it began).
    execution_engine.cancel_execution("exec_team")
    try:
        await team_execution_engine.run_team_execution("exec_team", "team_1", stream=True)
    finally:
        execution_engine.clear_cancellation("exec_team")

    refreshed = SessionLocal()
    execution = execution_repo.get(refreshed, id="exec_team")
    assert execution.status == ExecutionStatus.CANCELLED
    assert execution.completed_at is not None

    event_types = [
        e.type
        for e in execution_event_repo.get_multi(refreshed)
        if e.execution_id == "exec_team"
    ]
    assert EventType.EXECUTION_CANCELLED in event_types
    # Cancellation must short-circuit: the endless stream is not fully drained.
    assert event_types.count(EventType.MODEL_CHUNK) == 0
    refreshed.close()
    db.close()


@pytest.mark.asyncio
async def test_clear_cancellation_is_idempotent():
    execution_engine.cancel_execution("exec_x")
    assert execution_engine.is_cancelled("exec_x") is True
    execution_engine.clear_cancellation("exec_x")
    assert execution_engine.is_cancelled("exec_x") is False
    # Clearing an unknown id must not raise.
    execution_engine.clear_cancellation("never_seen")
