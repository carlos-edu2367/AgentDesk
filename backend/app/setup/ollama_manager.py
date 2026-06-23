import os
import json
import shutil
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Optional

import httpx

OLLAMA_BASE = "http://localhost:11434"
INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
MANUAL_DOWNLOAD_URL = "https://ollama.com/download/windows"
WINGET_COMMAND = "winget install --id Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements"


def _ollama_exe_path() -> Optional[str]:
    found = shutil.which("ollama")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if local:
        cand = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if cand.exists():
            return str(cand)
    return None


async def _is_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


async def _version() -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/version")
            if r.status_code == 200:
                return r.json().get("version")
    except Exception:
        pass
    return None


async def _list_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code == 200:
                return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


async def status() -> dict:
    running = await _is_running()
    installed = running or _ollama_exe_path() is not None
    return {
        "installed": installed,
        "running": running,
        "version": await _version() if running else None,
        "models": await _list_models() if running else [],
    }


def _appdata_temp() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home())
    d = Path(appdata) / "AgentDesk" / "temp"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def install() -> AsyncGenerator[dict, None]:
    if await _is_running():
        yield {"phase": "done", "message": "Ollama is already installed and running."}
        return
    installer = _appdata_temp() / "OllamaSetup.exe"
    try:
        yield {"phase": "download", "percent": 0, "message": "Downloading Ollama installer…"}
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as c:
            async with c.stream("GET", INSTALLER_URL) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0) or 0)
                done = 0
                with open(installer, "wb") as f:
                    async for chunk in r.aiter_bytes(1024 * 256):
                        f.write(chunk)
                        done += len(chunk)
                        pct = int(done * 100 / total) if total else None
                        yield {"phase": "download", "percent": pct, "message": "Downloading…"}
        yield {"phase": "installing", "message": "Running the installer…"}
        proc = await asyncio.create_subprocess_exec(
            str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        yield {"phase": "starting", "message": "Waiting for Ollama to start…"}
        for _ in range(60):
            if await _is_running():
                yield {"phase": "done", "message": "Ollama installed and running."}
                return
            await asyncio.sleep(2)
        yield {"phase": "error", "message": "Installer finished but Ollama did not start.",
               "manual_url": MANUAL_DOWNLOAD_URL, "winget": WINGET_COMMAND}
    except Exception as e:  # noqa: BLE001 — surface any failure to the UI
        yield {"phase": "error", "message": f"Install failed: {e}",
               "manual_url": MANUAL_DOWNLOAD_URL, "winget": WINGET_COMMAND}


async def pull(model: str) -> AsyncGenerator[dict, None]:
    try:
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream("POST", f"{OLLAMA_BASE}/api/pull", json={"model": model}) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    total = data.get("total") or 0
                    completed = data.get("completed") or 0
                    pct = int(completed * 100 / total) if total else None
                    status_msg = data.get("status", "")
                    done = status_msg == "success"
                    yield {
                        "phase": "success" if done else "pulling",
                        "percent": pct, "completed": completed, "total": total,
                        "message": status_msg,
                    }
    except Exception as e:  # noqa: BLE001
        yield {"phase": "error", "message": f"Pull failed: {e}"}
