def test_crud_execution(client):
    payload = {
        "type": "agent",
        "target_id": "agent_123",
        "user_input": "Hello",
        "status": "pending"
    }
    response = client.post("/api/executions", json=payload)
    assert response.status_code == 200
    execution = response.json()
    assert execution["id"].startswith("execution_")
    assert execution["status"] == "pending"
