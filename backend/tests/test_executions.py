import pytest
import json
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import get_db
from app.db.models import Base
from app.db.repositories.registry import agent_repo, provider_repo, execution_repo, execution_event_repo
from app.domain import schemas
from app.domain.enums import ProviderType, ExecutionStatus, EventType

from tests.mocks.mock_provider import MockProvider
from app.providers import provider_registry

from sqlalchemy.pool import StaticPool

# Setup a test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
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
    # Register mock provider to override ollama
    provider_registry.register(ProviderType.OLLAMA, MockProvider)
    
    # Patch SessionLocal used by background tasks
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
def setup_data(test_db):
    # Create provider
    provider = schemas.ProviderCreate(
        type=ProviderType.OLLAMA,
        name="Test Provider",
        enabled=True,
        config={"mock_response_text": "This is a final test response."}
    )
    provider_repo.create(test_db, obj_in=provider, id="prov_1")
    
    # Create agent
    agent = schemas.AgentCreate(
        name="Test Agent",
        model_config=schemas.ModelConfig(provider_id="prov_1", model="test", stream=True)
    )
    agent_repo.create(test_db, obj_in=agent, id="agent_1")
    
    test_db.commit()

client = TestClient(app)

def test_execution_flow(setup_data, test_db):
    # Start execution
    response = client.post("/api/executions/agent", json={
        "agent_id": "agent_1",
        "message": "Hello",
        "stream": True
    })
    assert response.status_code == 200
    data = response.json()
    exec_id = data["execution_id"]
    
    # Wait for background task to finish
    import time
    time.sleep(1) 
    
    execution = execution_repo.get(test_db, id=exec_id)
    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.result == "This is a mock response."
    
    events = execution_event_repo.get_multi(test_db)
    event_types = [e.type for e in events if e.execution_id == exec_id]
    
    assert EventType.EXECUTION_STARTED in event_types
    assert EventType.PROMPT_BUILT in event_types
    assert EventType.MODEL_REQUEST_STARTED in event_types
    assert EventType.MODEL_CHUNK in event_types
    assert EventType.MODEL_COMPLETED in event_types
    assert EventType.AGENT_COMPLETED in event_types
    assert EventType.EXECUTION_COMPLETED in event_types

def test_execution_sse(setup_data, test_db):
    response = client.post("/api/executions/agent", json={
        "agent_id": "agent_1",
        "message": "Hello SSE",
        "stream": True
    })
    exec_id = response.json()["execution_id"]
    
    # We can connect to SSE endpoint directly
    with client.stream("GET", f"/api/executions/{exec_id}/events") as sse_response:
        assert sse_response.status_code == 200
        events_received = []
        for line in sse_response.iter_lines():
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events_received.append(event_data["type"])
                
    assert "execution_started" in events_received
    assert "model_chunk" in events_received
    assert "execution_completed" in events_received

def test_execution_unknown_tool_denied(setup_data, test_db):
    # Model tries to call an unknown tool — Phase 7 behavior:
    # permission check fails, TOOL_CALL_DENIED is emitted, and after
    # MAX_STEPS attempts the execution completes with a max-steps message.
    provider = provider_repo.get(test_db, id="prov_1")
    new_config = dict(provider.config)
    new_config["mock_response_text"] = '{"type": "tool_call", "tool": "unknown_tool"}'
    new_config["mock_chunks"] = ['{"type": "tool_call", "tool": "unknown_tool"}']
    provider.config = new_config
    test_db.commit()

    response = client.post("/api/executions/agent", json={
        "agent_id": "agent_1",
        "message": "Hello",
        "stream": True
    })
    exec_id = response.json()["execution_id"]
    import time
    time.sleep(3)  # Allow up to MAX_STEPS iterations

    execution = execution_repo.get(test_db, id=exec_id)
    assert execution.status == ExecutionStatus.COMPLETED

    events = execution_event_repo.get_multi(test_db)
    event_types = [e.type for e in events if e.execution_id == exec_id]
    # Phase 7: tool calls are intercepted and denied when tool is unknown/not authorized
    assert EventType.TOOL_CALL_REQUESTED in event_types
    assert EventType.TOOL_CALL_DENIED in event_types

@pytest.mark.skip(reason="TestClient background tasks block synchronously")
def test_execution_cancel(setup_data, test_db):
    # Mock an endless stream so we can cancel it
    provider = provider_repo.get(test_db, id="prov_1")
    provider.config["mock_chunks"] = ["chunk"] * 50 # Make it take some time
    test_db.commit()
    
    response = client.post("/api/executions/agent", json={
        "agent_id": "agent_1",
        "message": "Cancel me",
        "stream": True
    })
    exec_id = response.json()["execution_id"]
    
    # Cancel immediately
    cancel_resp = client.post(f"/api/executions/{exec_id}/cancel")
    assert cancel_resp.status_code == 200
    
    import time
    time.sleep(1)
    
    execution = execution_repo.get(test_db, id=exec_id)
    assert execution.status == ExecutionStatus.CANCELLED
    
    events = execution_event_repo.get_multi(test_db)
    event_types = [e.type for e in events if e.execution_id == exec_id]
    assert EventType.EXECUTION_CANCELLED in event_types
