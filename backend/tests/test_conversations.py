import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import get_db
from app.db.models import Base
from app.db.repositories.registry import (
    agent_repo,
    provider_repo,
    execution_repo,
    conversation_repo,
)
from app.domain import schemas
from app.domain.enums import ProviderType, ExecutionType, ExecutionStatus

from tests.mocks.mock_provider import MockProvider
from app.providers import provider_registry

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def db_setup(monkeypatch):
    Base.metadata.create_all(bind=engine)
    provider_registry.register(ProviderType.OLLAMA, MockProvider)
    monkeypatch.setattr("app.db.database.SessionLocal", TestingSessionLocal)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def setup_agent(test_db):
    provider = schemas.ProviderCreate(
        type=ProviderType.OLLAMA,
        name="Test Provider",
        enabled=True,
        config={"mock_response_text": "Hi there."},
    )
    provider_repo.create(test_db, obj_in=provider, id="prov_1")
    agent = schemas.AgentCreate(
        name="Test Agent",
        model_config=schemas.ModelConfig(provider_id="prov_1", model="test", stream=True),
    )
    agent_repo.create(test_db, obj_in=agent, id="agent_1")
    test_db.commit()


@pytest.fixture
def setup_reasoning_agent(test_db):
    provider = schemas.ProviderCreate(
        type=ProviderType.OLLAMA,
        name="Reasoning Provider",
        enabled=True,
        config={"mock_reasoning_chunks": ["I should ", "answer."]},
    )
    provider_repo.create(test_db, obj_in=provider, id="prov_r")
    agent = schemas.AgentCreate(
        name="Reasoning Agent",
        model_config=schemas.ModelConfig(provider_id="prov_r", model="test", stream=True),
    )
    agent_repo.create(test_db, obj_in=agent, id="agent_r")
    test_db.commit()


client = TestClient(app)


def test_create_and_get_conversation(setup_agent):
    r = client.post(
        "/api/conversations",
        json={"type": "agent", "target_id": "agent_1", "title": "Hi"},
    )
    assert r.status_code == 200, r.text
    conv = r.json()
    assert conv["target_id"] == "agent_1"
    assert conv["type"] == "agent"

    g = client.get(f"/api/conversations/{conv['id']}")
    assert g.status_code == 200
    body = g.json()
    assert body["conversation"]["id"] == conv["id"]
    assert body["turns"] == []


def test_get_conversation_404():
    r = client.get("/api/conversations/does-not-exist")
    assert r.status_code == 404


def test_list_conversations_filters_by_target(setup_agent):
    client.post("/api/conversations", json={"type": "agent", "target_id": "agent_1"})
    client.post("/api/conversations", json={"type": "agent", "target_id": "agent_other"})
    r = client.get("/api/conversations", params={"target_id": "agent_1"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["target_id"] == "agent_1"


def test_post_message_creates_turn(setup_agent, test_db):
    conv = client.post(
        "/api/conversations", json={"type": "agent", "target_id": "agent_1"}
    ).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"message": "Hello"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["conversation_id"] == conv["id"]
    exec_id = data["execution_id"]

    time.sleep(1)  # let the background task finish

    execution = execution_repo.get(test_db, id=exec_id)
    assert execution.conversation_id == conv["id"]
    assert execution.status == ExecutionStatus.COMPLETED

    detail = client.get(f"/api/conversations/{conv['id']}").json()
    assert len(detail["turns"]) == 1
    assert detail["turns"][0]["execution"]["user_input"] == "Hello"

    # Title is auto-populated from the first message.
    refreshed = conversation_repo.get(test_db, id=conv["id"])
    assert refreshed.title == "Hello"


def test_update_conversation_workspaces_and_message_inherits(setup_agent, test_db):
    conv = client.post(
        "/api/conversations", json={"type": "agent", "target_id": "agent_1"}
    ).json()
    assert conv["workspace_ids"] == []

    # Grant workspaces to the conversation.
    upd = client.patch(
        f"/api/conversations/{conv['id']}", json={"workspace_ids": ["ws_a", "ws_b"]}
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["workspace_ids"] == ["ws_a", "ws_b"]

    # A message with no explicit workspaces inherits the conversation's grant.
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"message": "Hi"})
    assert r.status_code == 200, r.text
    exec_id = r.json()["execution_id"]
    execution = execution_repo.get(test_db, id=exec_id)
    assert execution.workspace_ids == ["ws_a", "ws_b"]


def test_message_workspaces_override_conversation(setup_agent, test_db):
    conv = client.post(
        "/api/conversations",
        json={"type": "agent", "target_id": "agent_1", "workspace_ids": ["ws_default"]},
    ).json()
    assert conv["workspace_ids"] == ["ws_default"]

    r = client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"message": "Hi", "workspace_ids": ["ws_override"]},
    )
    assert r.status_code == 200, r.text
    execution = execution_repo.get(test_db, id=r.json()["execution_id"])
    assert execution.workspace_ids == ["ws_override"]


def test_build_conversation_history(setup_agent, test_db):
    from app.runtime.history import build_conversation_history

    conv = conversation_repo.create(
        test_db,
        obj_in=schemas.ConversationCreate(type=ExecutionType.AGENT, target_id="agent_1"),
        id="conv_hist",
    )
    prior = execution_repo.create(
        test_db,
        obj_in=schemas.ExecutionCreate(
            type=ExecutionType.AGENT,
            target_id="agent_1",
            user_input="first message",
            status=ExecutionStatus.COMPLETED,
            conversation_id=conv.id,
        ),
        id="exec_prior",
    )
    prior.result = "first answer"
    test_db.commit()

    history = build_conversation_history(test_db, conv.id, exclude_execution_id="exec_current")
    assert history == [
        {"role": "user", "content": "first message"},
        {"role": "assistant", "content": "first answer"},
    ]


def test_build_conversation_history_excludes_current_and_unfinished(setup_agent, test_db):
    from app.runtime.history import build_conversation_history

    conv = conversation_repo.create(
        test_db,
        obj_in=schemas.ConversationCreate(type=ExecutionType.AGENT, target_id="agent_1"),
        id="conv_hist2",
    )
    # An unfinished turn (no result) should be skipped.
    execution_repo.create(
        test_db,
        obj_in=schemas.ExecutionCreate(
            type=ExecutionType.AGENT, target_id="agent_1",
            user_input="pending", status=ExecutionStatus.RUNNING, conversation_id=conv.id,
        ),
        id="exec_pending",
    )
    history = build_conversation_history(test_db, conv.id, exclude_execution_id="exec_current")
    assert history == []


def test_reasoning_emits_model_reasoning_chunk(setup_reasoning_agent, test_db):
    from app.db.repositories.registry import execution_event_repo
    from app.domain.enums import EventType

    conv = client.post(
        "/api/conversations", json={"type": "agent", "target_id": "agent_r"}
    ).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"message": "Hi"})
    exec_id = r.json()["execution_id"]

    time.sleep(1)

    events = execution_event_repo.get_multi(test_db, limit=1000)
    reasoning = [
        e for e in events
        if e.execution_id == exec_id and e.type == EventType.MODEL_REASONING_CHUNK
    ]
    assert len(reasoning) == 2
    assert "".join(e.content["delta"] for e in reasoning) == "I should answer."
