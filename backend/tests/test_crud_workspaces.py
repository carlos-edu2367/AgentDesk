def test_crud_workspace(client):
    payload = {
        "name": "Test Workspace",
        "paths": ["/tmp/test"]
    }
    response = client.post("/api/workspaces", json=payload)
    assert response.status_code == 200
    ws = response.json()
    assert ws["id"].startswith("workspace_")
