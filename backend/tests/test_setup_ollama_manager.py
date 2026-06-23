import pytest
from app.setup import ollama_manager as om


@pytest.mark.asyncio
async def test_status_running(monkeypatch):
    async def fake_running():
        return True
    async def fake_version():
        return "0.30.8"
    async def fake_models():
        return ["qwen3.5:4b"]
    monkeypatch.setattr(om, "_is_running", fake_running)
    monkeypatch.setattr(om, "_version", fake_version)
    monkeypatch.setattr(om, "_list_models", fake_models)
    st = await om.status()
    assert st == {"installed": True, "running": True, "version": "0.30.8", "models": ["qwen3.5:4b"]}


@pytest.mark.asyncio
async def test_status_installed_not_running(monkeypatch):
    async def fake_running():
        return False
    monkeypatch.setattr(om, "_is_running", fake_running)
    monkeypatch.setattr(om, "_ollama_exe_path", lambda: r"C:\x\ollama.exe")
    st = await om.status()
    assert st["installed"] is True and st["running"] is False and st["models"] == []


@pytest.mark.asyncio
async def test_install_short_circuits_when_running(monkeypatch):
    async def fake_running():
        return True
    monkeypatch.setattr(om, "_is_running", fake_running)
    events = [e async for e in om.install()]
    assert events[-1]["phase"] == "done"


@pytest.mark.asyncio
async def test_pull_normalizes_progress(monkeypatch):
    class FakeStream:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def raise_for_status(self): pass
        async def aiter_lines(self):
            yield '{"status":"pulling","completed":50,"total":100}'
            yield '{"status":"success"}'
    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def stream(self, *a, **k): return FakeStream()
    monkeypatch.setattr(om.httpx, "AsyncClient", FakeClient)
    events = [e async for e in om.pull("qwen3.5:4b")]
    assert events[0]["phase"] == "pulling" and events[0]["percent"] == 50
    assert events[-1]["phase"] == "success"
