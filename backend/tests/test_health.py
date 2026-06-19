def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "storage_ready" in data
    assert "database_ready" in data


def test_health_storage_ready(client):
    response = client.get("/api/health")
    data = response.json()
    # storage_ready should be True because mock_appdata fixture creates AppData
    assert data["storage_ready"] is True


def test_health_database_ready(client):
    response = client.get("/api/health")
    data = response.json()
    # database_ready may be False in in-memory test (no file written to disk)
    assert isinstance(data["database_ready"], bool)
