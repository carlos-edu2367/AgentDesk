def test_crud_agent(client):
    # 1. Create
    payload = {
        "name": "Test Agent",
        "description": "A test agent",
        "model_config": {
            "provider_id": "provider_1",
            "model": "test-model"
        }
    }
    response = client.post("/api/agents", json=payload)
    assert response.status_code == 200
    agent = response.json()
    assert agent["name"] == "Test Agent"
    assert agent["id"].startswith("agent_")
    agent_id = agent["id"]

    # 2. Get
    response = client.get(f"/api/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["id"] == agent_id

    # 3. List
    response = client.get("/api/agents")
    assert response.status_code == 200
    assert len(response.json()) >= 1

    # 4. Update
    update_payload = {"description": "Updated description"}
    response = client.put(f"/api/agents/{agent_id}", json=update_payload)
    assert response.status_code == 200
    assert response.json()["description"] == "Updated description"

    # 5. Delete
    response = client.delete(f"/api/agents/{agent_id}")
    assert response.status_code == 200

    # 6. Get (Not Found)
    response = client.get(f"/api/agents/{agent_id}")
    assert response.status_code == 404
