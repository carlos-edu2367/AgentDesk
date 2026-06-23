def test_state_defaults_false(client):
    r = client.get("/api/onboarding/state")
    assert r.status_code == 200
    assert r.json() == {"completed": False, "has_providers": False}


def test_complete_persists(client):
    assert client.post("/api/onboarding/complete").status_code == 200
    assert client.get("/api/onboarding/state").json()["completed"] is True


def test_create_ollama_provider_is_idempotent(client):
    r1 = client.post("/api/onboarding/provider/ollama")
    assert r1.status_code == 200 and r1.json()["type"] == "ollama"
    client.post("/api/onboarding/provider/ollama")
    providers = client.get("/api/providers").json()
    assert len([p for p in providers if p["type"] == "ollama"]) == 1


def test_state_reflects_providers(client):
    client.post("/api/onboarding/provider/ollama")
    assert client.get("/api/onboarding/state").json()["has_providers"] is True


def test_create_openrouter_provider_stores_key(client):
    r = client.post("/api/onboarding/provider/openrouter", json={"api_key": "sk-or-1234567890"})
    assert r.status_code == 200 and r.json()["type"] == "openrouter"
