from app.domain.enums import ProviderType

def test_crud_provider_and_masking(client):
    payload = {
        "type": ProviderType.OPENROUTER,
        "name": "OpenRouter Test",
        "config": {
            "api_key": "sk-or-v1-abcdef1234567890abcdef1234567890"
        }
    }
    # Create
    response = client.post("/api/providers", json=payload)
    assert response.status_code == 200
    provider = response.json()
    provider_id = provider["id"]
    assert provider_id.startswith("provider_")
    
    # Masking check on CREATE
    assert provider["config"]["api_key"] == "sk-...7890"
    
    # Masking check on GET
    response = client.get(f"/api/providers/{provider_id}")
    assert response.status_code == 200
    assert response.json()["config"]["api_key"] == "sk-...7890"

    # Masking check on LIST
    response = client.get("/api/providers")
    assert response.status_code == 200
    assert any(p["config"].get("api_key") == "sk-...7890" for p in response.json() if p["id"] == provider_id)

    # Delete
    client.delete(f"/api/providers/{provider_id}")
