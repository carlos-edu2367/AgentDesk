from app.setup import hardware


def test_hardware_endpoint(client, monkeypatch):
    monkeypatch.setattr(hardware, "detect",
        lambda: hardware.HardwareInfo(ram_gb=16.0, cpu_name="Test CPU", cpu_cores=8, gpu_name="GPU", vram_gb=8.0))
    r = client.get("/api/system/hardware")
    assert r.status_code == 200
    assert r.json()["ram_gb"] == 16.0


def test_recommendations_endpoint(client, monkeypatch):
    monkeypatch.setattr(hardware, "detect",
        lambda: hardware.HardwareInfo(ram_gb=24.0, cpu_name="x", cpu_cores=8))
    r = client.get("/api/ollama/recommendations")
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "balanced"
    assert any(m["tag"] == "gemma4:12b" for m in body["models"])


def test_status_endpoint(client, monkeypatch):
    from app.api.routers import ollama as ollama_router
    async def fake_status():
        return {"installed": False, "running": False, "version": None, "models": []}
    monkeypatch.setattr(ollama_router.ollama_manager, "status", fake_status)
    r = client.get("/api/ollama/status")
    assert r.status_code == 200 and r.json()["installed"] is False


def test_pull_streams_ndjson(client, monkeypatch):
    from app.api.routers import ollama as ollama_router
    async def fake_pull(model):
        yield {"phase": "pulling", "percent": 10, "message": "x"}
        yield {"phase": "success", "percent": 100, "message": "success"}
    monkeypatch.setattr(ollama_router.ollama_manager, "pull", fake_pull)
    r = client.post("/api/ollama/pull", json={"model": "qwen3.5:4b"})
    assert r.status_code == 200
    lines = [l for l in r.text.split("\n") if l.strip()]
    assert len(lines) == 2 and '"success"' in lines[-1]
