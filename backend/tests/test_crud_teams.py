def test_crud_team(client):
    # Need to create an agent first for the leader
    agent_payload = {
        "name": "Leader",
        "model_config": {"provider_id": "p1", "model": "m1"}
    }
    leader_response = client.post("/api/agents", json=agent_payload)
    leader_id = leader_response.json()["id"]

    team_payload = {
        "name": "My Team",
        "leader_agent_id": leader_id,
        "member_agent_ids": [leader_id]
    }
    response = client.post("/api/teams", json=team_payload)
    assert response.status_code == 200
    team = response.json()
    team_id = team["id"]
    assert team_id.startswith("team_")
    assert team["leader_agent_id"] == leader_id
    assert team["member_agent_ids"] == [leader_id]
