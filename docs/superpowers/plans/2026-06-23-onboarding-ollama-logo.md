# Onboarding + Ollama setup + hardware model recommendation + logo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-mandatory first-run wizard that installs Ollama, recommends models by hardware, configures OpenRouter as an alternative, refreshes the app logo, and ships a new portable exe.

**Architecture:** All system-level work (hardware probing, Ollama install/pull) lives in the FastAPI backend as a new `app/setup/` package exposed via streaming (ndjson) routers; the React frontend renders a gated full-screen wizard that drives those endpoints. The logo is an SVG rasterized to a Windows `.ico` for electron-builder.

**Tech Stack:** Python/FastAPI, SQLAlchemy + Alembic, psutil, httpx; React/TypeScript + Vitest; Electron + electron-builder; `sharp` + `png-to-ico` for the icon.

**Reference spec:** `docs/superpowers/specs/2026-06-23-onboarding-ollama-logo-design.md`

---

## File structure

Backend (new unless noted):
- `backend/app/setup/__init__.py` — package marker
- `backend/app/setup/hardware.py` — RAM/CPU/GPU detection
- `backend/app/setup/catalog.py` — curated model catalog + `recommend()`
- `backend/app/setup/ollama_manager.py` — status / install / pull
- `backend/app/setup/settings_store.py` — `app_settings` key/value helpers
- `backend/app/api/routers/onboarding.py` — onboarding state + provider creation
- `backend/app/api/routers/ollama.py` — hardware / status / recommendations / install / pull
- Modify `backend/app/db/models.py` — add `AppSettingModel`
- Modify `backend/app/providers/ollama.py:24` — add `gemma4`, `qwen3.5` to `_VISION_FAMILIES`
- Modify `backend/app/main.py:14,75-90` — register the two new routers
- Modify `backend/requirements.txt` — add `psutil`
- New `backend/alembic/versions/a7b8c9d0e1f2_add_app_settings.py` — migration
- Tests: `backend/tests/test_setup_hardware.py`, `test_setup_catalog.py`, `test_setup_ollama_manager.py`, `test_onboarding_api.py`, `test_ollama_api.py`

Frontend (new unless noted):
- `apps/frontend/src/api/ollama.ts`, `apps/frontend/src/api/onboarding.ts`
- `apps/frontend/src/lib/ndjson.ts` — streaming reader
- `apps/frontend/src/components/onboarding/OnboardingWizard.tsx`
- `apps/frontend/src/components/onboarding/steps.tsx` — Welcome/Ollama/OpenRouter/Done
- `apps/frontend/src/components/Logo.tsx`, `apps/frontend/src/assets/logo.svg`
- `apps/frontend/public/favicon.svg`
- Modify `apps/frontend/src/App.tsx` — gate the wizard
- Modify `apps/frontend/index.html` — favicon
- Modify `apps/frontend/src/components/Sidebar.tsx:91-93`, `apps/frontend/src/components/StartupScreen.tsx:71` — use `Logo`
- Tests: `apps/frontend/src/__tests__/Onboarding.test.tsx`, `Logo.test.tsx`, `ndjson.test.ts`

Packaging:
- New `apps/desktop/scripts/make-icon.mjs`
- New `apps/desktop/build/icon.svg` (source) → generates `apps/desktop/build/icon.ico`
- Modify `apps/desktop/package.json` — `win.icon` + devDeps

---

## Phase 1 — Backend: hardware, catalog, settings

### Task 1: `app_settings` model + key/value store

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/app/setup/__init__.py` (empty)
- Create: `backend/app/setup/settings_store.py`
- Test: `backend/tests/test_setup_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_setup_settings.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.models import Base
from app.setup import settings_store


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_get_missing_returns_default():
    db = _session()
    assert settings_store.get(db, "onboarding_completed", "false") == "false"


def test_set_then_get_roundtrip():
    db = _session()
    settings_store.set(db, "onboarding_completed", "true")
    assert settings_store.get(db, "onboarding_completed") == "true"


def test_set_is_idempotent_upsert():
    db = _session()
    settings_store.set(db, "k", "a")
    settings_store.set(db, "k", "b")
    assert settings_store.get(db, "k") == "b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_setup_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: app.setup` / `AppSettingModel` missing.

- [ ] **Step 3: Add the model**

Append to `backend/app/db/models.py` (after `UserModel`):

```python
class AppSettingModel(Base):
    __tablename__ = "app_settings"
    key = Column(String, primary_key=True)
    value = Column(Text)
```

- [ ] **Step 4: Implement the store**

```python
# backend/app/setup/settings_store.py
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import AppSettingModel


def get(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.query(AppSettingModel).filter(AppSettingModel.key == key).first()
    return row.value if row else default


def set(db: Session, key: str, value: str) -> None:
    row = db.query(AppSettingModel).filter(AppSettingModel.key == key).first()
    if row:
        row.value = value
    else:
        row = AppSettingModel(key=key, value=value)
        db.add(row)
    db.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_setup_settings.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models.py backend/app/setup/__init__.py backend/app/setup/settings_store.py backend/tests/test_setup_settings.py
git commit -m "feat(setup): app_settings key/value store"
```

### Task 2: Alembic migration for `app_settings`

**Files:**
- Create: `backend/alembic/versions/a7b8c9d0e1f2_add_app_settings.py`
- Test: reuse `backend/tests/test_alembic_startup.py` (already asserts migrations run clean)

- [ ] **Step 1: Find the current head revision**

Run: `cd backend && venv/Scripts/python -m alembic heads`
Expected: prints one revision id (the latest, e.g. `d55191bfff6b`). Use it as `down_revision` below.

- [ ] **Step 2: Write the migration**

```python
# backend/alembic/versions/a7b8c9d0e1f2_add_app_settings.py
"""add app_settings

Revision ID: a7b8c9d0e1f2
Revises: <PASTE_CURRENT_HEAD_FROM_STEP_1>
Create Date: 2026-06-23
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "<PASTE_CURRENT_HEAD_FROM_STEP_1>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
```

- [ ] **Step 3: Verify migration applies cleanly**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_alembic_startup.py -v`
Expected: PASS (migrations upgrade to head without error).

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/a7b8c9d0e1f2_add_app_settings.py
git commit -m "feat(setup): migration for app_settings table"
```

### Task 3: Hardware detection

**Files:**
- Create: `backend/app/setup/hardware.py`
- Modify: `backend/requirements.txt` (add `psutil`)
- Test: `backend/tests/test_setup_hardware.py`

- [ ] **Step 1: Install psutil and add to requirements**

Run: `cd backend && venv/Scripts/python -m pip install psutil`
Then add a line `psutil` to `backend/requirements.txt`.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_setup_hardware.py
from app.setup import hardware
from app.setup.hardware import HardwareInfo


def test_detect_uses_components(monkeypatch):
    monkeypatch.setattr(hardware, "_detect_ram_gb", lambda: 16.0)
    monkeypatch.setattr(hardware, "_detect_gpu_nvidia", lambda: ("NVIDIA RTX 4060", 8.0))
    info = hardware.detect()
    assert info.ram_gb == 16.0
    assert info.gpu_name == "NVIDIA RTX 4060"
    assert info.vram_gb == 8.0
    assert info.cpu_cores >= 1


def test_detect_falls_back_to_cim_when_no_nvidia(monkeypatch):
    monkeypatch.setattr(hardware, "_detect_ram_gb", lambda: 8.0)
    monkeypatch.setattr(hardware, "_detect_gpu_nvidia", lambda: None)
    monkeypatch.setattr(hardware, "_detect_gpu_windows_cim", lambda: "Intel Iris Xe")
    monkeypatch.setattr(hardware, "_detect_vram_windows_registry", lambda: None)
    info = hardware.detect()
    assert info.gpu_name == "Intel Iris Xe"
    assert info.vram_gb is None


def test_to_dict_is_serializable(monkeypatch):
    info = HardwareInfo(ram_gb=8.0, cpu_name="x", cpu_cores=4)
    d = info.to_dict()
    assert d["ram_gb"] == 8.0 and d["gpu_name"] is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_setup_hardware.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement hardware.py**

```python
# backend/app/setup/hardware.py
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, asdict, field
from typing import Optional, Tuple


@dataclass
class HardwareInfo:
    ram_gb: float
    cpu_name: str
    cpu_cores: int
    gpu_name: Optional[str] = None
    vram_gb: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _run(cmd: list[str], timeout: float = 6.0) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _detect_ram_gb() -> float:
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        return 0.0


def _detect_gpu_nvidia() -> Optional[Tuple[str, Optional[float]]]:
    if not shutil.which("nvidia-smi"):
        return None
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if not out:
        return None
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    if len(parts) < 2:
        return None
    name = parts[0]
    try:
        vram_gb: Optional[float] = round(float(parts[1]) / 1024, 1)  # MiB -> GiB
    except ValueError:
        vram_gb = None
    return name, vram_gb


def _detect_gpu_windows_cim() -> Optional[str]:
    out = _run([
        "powershell", "-NoProfile", "-Command",
        "(Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name)",
    ])
    return out or None


def _detect_vram_windows_registry() -> Optional[float]:
    ps = (
        "$p='HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
        "{4d36e968-e325-11ce-bfc1-08002be10318}\\0*';"
        "Get-ItemProperty -Path $p -Name 'HardwareInformation.qwMemorySize' "
        "-ErrorAction SilentlyContinue | "
        "Where-Object { $_.'HardwareInformation.qwMemorySize' } | "
        "Select-Object -First 1 -ExpandProperty 'HardwareInformation.qwMemorySize'"
    )
    out = _run(["powershell", "-NoProfile", "-Command", ps])
    try:
        return round(int(out) / (1024 ** 3), 1)
    except (ValueError, TypeError):
        return None


def detect() -> HardwareInfo:
    ram = _detect_ram_gb()
    cpu_name = platform.processor() or platform.machine() or "Unknown CPU"
    cores = os.cpu_count() or 1
    gpu_name: Optional[str] = None
    vram: Optional[float] = None

    nv = _detect_gpu_nvidia()
    if nv:
        gpu_name, vram = nv
    else:
        gpu_name = _detect_gpu_windows_cim()
        vram = _detect_vram_windows_registry()

    return HardwareInfo(ram_gb=ram, cpu_name=cpu_name, cpu_cores=cores, gpu_name=gpu_name, vram_gb=vram)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_setup_hardware.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/setup/hardware.py backend/requirements.txt backend/tests/test_setup_hardware.py
git commit -m "feat(setup): hardware detection (RAM/CPU/GPU with fallbacks)"
```

### Task 4: Model catalog + recommendation

**Files:**
- Create: `backend/app/setup/catalog.py`
- Test: `backend/tests/test_setup_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_setup_catalog.py
from app.setup.catalog import recommend, budget_gb
from app.setup.hardware import HardwareInfo


def test_budget_uses_max_of_vram_and_60pct_ram():
    assert budget_gb(HardwareInfo(ram_gb=16.0, cpu_name="x", cpu_cores=4)) == 9.6
    assert budget_gb(HardwareInfo(ram_gb=16.0, cpu_name="x", cpu_cores=4, vram_gb=12.0)) == 12.0


def test_low_ram_no_gpu_recommends_light_tier():
    rec = recommend(HardwareInfo(ram_gb=4.0, cpu_name="x", cpu_cores=2))  # budget 2.4
    assert rec["tier"] == "light"
    tags = [m["tag"] for m in rec["models"]]
    assert "qwen3.5:0.8b" in tags


def test_midrange_recommends_balanced_and_has_fallback():
    rec = recommend(HardwareInfo(ram_gb=24.0, cpu_name="x", cpu_cores=8))  # budget 14.4
    assert rec["tier"] == "balanced"
    assert any(m["tag"] == "gemma4:12b" for m in rec["models"])
    assert len(rec["fallback_models"]) > 0


def test_high_vram_recommends_max_tier():
    rec = recommend(HardwareInfo(ram_gb=64.0, cpu_name="x", cpu_cores=16, gpu_name="RTX 5090", vram_gb=32.0))
    assert rec["tier"] == "max"
    assert any(m["tag"] == "gemma4:31b" for m in rec["models"])


def test_models_only_include_those_that_fit_budget():
    rec = recommend(HardwareInfo(ram_gb=10.0, cpu_name="x", cpu_cores=4))  # budget 6.0
    for m in rec["models"]:
        assert m["min_budget_gb"] <= 6.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_setup_catalog.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement catalog.py**

```python
# backend/app/setup/catalog.py
from dataclasses import dataclass, asdict
from typing import List
from app.setup.hardware import HardwareInfo


@dataclass
class ModelEntry:
    tag: str
    label: str
    params: str
    approx_size_gb: float
    min_budget_gb: float
    vision: bool
    blurb: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Tier:
    key: str
    label: str
    max_budget_gb: float  # upper bound, exclusive; inf for the top tier
    models: List[ModelEntry]


# Tags + download sizes verified against the Ollama library on 2026-06-23.
# min_budget_gb ~= approx_size_gb * 1.25 (weights + context overhead).
CATALOG: List[Tier] = [
    Tier("light", "Light", 4.0, [
        ModelEntry("qwen3.5:0.8b", "Qwen 3.5 0.8B", "0.8B", 1.0, 1.3, False, "Tiny and fast; runs on almost anything."),
        ModelEntry("qwen3.5:2b", "Qwen 3.5 2B", "2B", 2.7, 3.4, False, "Small but capable general model."),
    ]),
    Tier("balanced_light", "Balanced-light", 8.0, [
        ModelEntry("qwen3.5:4b", "Qwen 3.5 4B", "4B", 3.4, 4.3, False, "Good quality at low memory."),
        ModelEntry("gemma4:e2b-it-qat", "Gemma 4 E2B (QAT)", "2B eff.", 4.3, 5.4, True, "Efficient multimodal, quality-preserving quant."),
        ModelEntry("qwen3.5:9b", "Qwen 3.5 9B", "9B", 6.6, 8.0, False, "Strong all-rounder."),
    ]),
    Tier("balanced", "Balanced", 16.0, [
        ModelEntry("gemma4:12b", "Gemma 4 12B", "12B", 7.6, 9.5, True, "Multimodal, great general reasoning."),
        ModelEntry("gemma4:e4b", "Gemma 4 E4B", "4B eff.", 9.6, 12.0, True, "Higher-quality efficient multimodal."),
        ModelEntry("qwen3.5:9b", "Qwen 3.5 9B", "9B", 6.6, 8.0, False, "Strong all-rounder."),
    ]),
    Tier("strong", "Strong", 32.0, [
        ModelEntry("qwen3.5:27b", "Qwen 3.5 27B", "27B", 17.0, 21.3, False, "High quality; needs a strong GPU or lots of RAM."),
        ModelEntry("gemma4:26b", "Gemma 4 26B (MoE)", "26B MoE", 18.0, 22.5, True, "Mixture-of-experts, ~3.8B active per token."),
    ]),
    Tier("max", "Max", float("inf"), [
        ModelEntry("gemma4:31b", "Gemma 4 31B", "31B", 20.0, 25.0, True, "Dense flagship; best Gemma quality."),
        ModelEntry("qwen3.5:35b", "Qwen 3.5 35B", "35B", 24.0, 30.0, False, "Top-tier quality for capable workstations."),
    ]),
]


def budget_gb(hw: HardwareInfo) -> float:
    return max(hw.vram_gb or 0.0, round(hw.ram_gb * 0.6, 1))


def _tier_index_for_budget(b: float) -> int:
    for i, tier in enumerate(CATALOG):
        if b < tier.max_budget_gb:
            return i
    return len(CATALOG) - 1


def recommend(hw: HardwareInfo) -> dict:
    b = budget_gb(hw)
    idx = _tier_index_for_budget(b)
    tier = CATALOG[idx]
    primary = [m for m in tier.models if m.min_budget_gb <= b] or tier.models
    fallback = CATALOG[idx - 1].models if idx > 0 else []
    return {
        "budget_gb": b,
        "tier": tier.key,
        "tier_label": tier.label,
        "models": [m.to_dict() for m in primary],
        "fallback_models": [m.to_dict() for m in fallback],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_setup_catalog.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/setup/catalog.py backend/tests/test_setup_catalog.py
git commit -m "feat(setup): curated Gemma 4 / Qwen 3.5 catalog + recommend()"
```

---

## Phase 2 — Backend: Ollama manager + routers

### Task 5: Ollama manager (status / install / pull)

**Files:**
- Create: `backend/app/setup/ollama_manager.py`
- Test: `backend/tests/test_setup_ollama_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_setup_ollama_manager.py
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
    monkeypatch.setattr(om, "_ollama_exe_path", lambda: r"C:\\x\\ollama.exe")
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
```

Note: tests need `pytest-asyncio` (already a backend dep per spec §3 testing). If a marker error appears, confirm `asyncio_mode = auto` in `backend/pytest.ini`/`pyproject`; otherwise the `@pytest.mark.asyncio` decorators shown are correct.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_setup_ollama_manager.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement ollama_manager.py**

```python
# backend/app/setup/ollama_manager.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_setup_ollama_manager.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/setup/ollama_manager.py backend/tests/test_setup_ollama_manager.py
git commit -m "feat(setup): ollama manager (status/install/pull streaming)"
```

### Task 6: Ollama + system router

**Files:**
- Create: `backend/app/api/routers/ollama.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_ollama_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_ollama_api.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_ollama_api.py -v`
Expected: FAIL — routes 404 (router not registered).

- [ ] **Step 3: Implement the router**

```python
# backend/app/api/routers/ollama.py
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.setup import hardware, catalog, ollama_manager

router = APIRouter(tags=["ollama"])


class PullRequest(BaseModel):
    model: str


@router.get("/system/hardware")
def get_hardware() -> dict:
    return hardware.detect().to_dict()


@router.get("/ollama/status")
async def get_status() -> dict:
    return await ollama_manager.status()


@router.get("/ollama/recommendations")
def get_recommendations() -> dict:
    hw = hardware.detect()
    return {"hardware": hw.to_dict(), **catalog.recommend(hw)}


def _ndjson(agen):
    async def gen():
        async for event in agen:
            yield json.dumps(event) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.post("/ollama/install")
def post_install() -> StreamingResponse:
    return _ndjson(ollama_manager.install())


@router.post("/ollama/pull")
def post_pull(req: PullRequest) -> StreamingResponse:
    return _ndjson(ollama_manager.pull(req.model))
```

- [ ] **Step 4: Register the router**

In `backend/app/main.py` line 14 add `ollama` to the import list, and after line 90 add:

```python
from app.api.routers import ollama as ollama_router
app.include_router(ollama_router.router, prefix="/api")
```

(Place the import with the others at top; keep the `include_router` call alongside the existing ones.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_ollama_api.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routers/ollama.py backend/app/main.py backend/tests/test_ollama_api.py
git commit -m "feat(api): ollama hardware/status/recommendations/install/pull routes"
```

### Task 7: Onboarding router (state, complete, provider creation)

**Files:**
- Create: `backend/app/api/routers/onboarding.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_onboarding_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_onboarding_api.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_onboarding_api.py -v`
Expected: FAIL — routes 404.

- [ ] **Step 3: Implement the router**

```python
# backend/app/api/routers/onboarding.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.repositories.registry import provider_repo
from app.domain import schemas
from app.domain.enums import ProviderType
from app.domain.utils import generate_id
from app.setup import settings_store

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_COMPLETED_KEY = "onboarding_completed"


class OpenRouterKey(BaseModel):
    api_key: str


@router.get("/state")
def get_state(db: Session = Depends(get_db)) -> dict:
    completed = settings_store.get(db, _COMPLETED_KEY, "false") == "true"
    has_providers = len(provider_repo.get_multi(db, limit=1)) > 0
    return {"completed": completed, "has_providers": has_providers}


@router.post("/complete")
def complete(db: Session = Depends(get_db)) -> dict:
    settings_store.set(db, _COMPLETED_KEY, "true")
    return {"completed": True}


@router.post("/provider/ollama", response_model=schemas.Provider)
def create_ollama_provider(db: Session = Depends(get_db)):
    for p in provider_repo.get_multi(db, limit=100):
        if p.type == ProviderType.OLLAMA.value:
            return schemas.Provider.model_validate(p)
    obj = schemas.ProviderCreate(
        type=ProviderType.OLLAMA, name="Ollama (local)",
        base_url="http://localhost:11434", enabled=True, config={},
    )
    created = provider_repo.create(db, obj_in=obj, id=generate_id("provider"))
    return schemas.Provider.model_validate(created)


@router.post("/provider/openrouter", response_model=schemas.Provider)
def create_openrouter_provider(body: OpenRouterKey, db: Session = Depends(get_db)):
    obj = schemas.ProviderCreate(
        type=ProviderType.OPENROUTER, name="OpenRouter",
        base_url=None, enabled=True, config={"api_key": body.api_key},
    )
    created = provider_repo.create(db, obj_in=obj, id=generate_id("provider"))
    return schemas.Provider.model_validate(created)
```

Note: confirm the enum member names in `backend/app/domain/enums.py` (`ProviderType.OLLAMA`, `ProviderType.OPENROUTER`). If the values differ, use the actual members; the string values are `"ollama"` / `"openrouter"`.

- [ ] **Step 4: Register the router** in `backend/app/main.py` (import `onboarding`, then `app.include_router(onboarding.router, prefix="/api")`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_onboarding_api.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routers/onboarding.py backend/app/main.py backend/tests/test_onboarding_api.py
git commit -m "feat(api): onboarding state + provider auto-creation"
```

### Task 8: Vision-family update + full backend suite

**Files:**
- Modify: `backend/app/providers/ollama.py:24`
- Test: existing `backend/tests/test_providers.py` (+ whole suite)

- [ ] **Step 1: Add families**

In `backend/app/providers/ollama.py`, extend `_VISION_FAMILIES`:

```python
_VISION_FAMILIES = ("llava", "gemma3", "gemma4", "qwen2.5vl", "qwen2.5-vl", "qwen3.5",
                    "llama3.2-vision", "minicpm-v", "moondream", "bakllava")
```

- [ ] **Step 2: Run the full backend suite**

Run: `cd backend && venv/Scripts/python -m pytest -q`
Expected: all green (prior 236 + new setup/onboarding/ollama tests).

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/ollama.py
git commit -m "feat(providers): report vision for gemma4 / qwen3.5"
```

---

## Phase 3 — Frontend: wizard

### Task 9: ndjson stream reader

**Files:**
- Create: `apps/frontend/src/lib/ndjson.ts`
- Test: `apps/frontend/src/__tests__/ndjson.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// apps/frontend/src/__tests__/ndjson.test.ts
import { describe, it, expect } from 'vitest'
import { readNdjson } from '../lib/ndjson'

function streamFrom(chunks: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const enc = new TextEncoder()
      chunks.forEach(c => controller.enqueue(enc.encode(c)))
      controller.close()
    },
  })
  return new Response(body)
}

describe('readNdjson', () => {
  it('parses objects split across chunks', async () => {
    const res = streamFrom(['{"a":1}\n{"a":', '2}\n'])
    const out: any[] = []
    for await (const ev of readNdjson(res)) out.push(ev)
    expect(out).toEqual([{ a: 1 }, { a: 2 }])
  })

  it('flushes a trailing line without newline', async () => {
    const res = streamFrom(['{"x":true}'])
    const out: any[] = []
    for await (const ev of readNdjson(res)) out.push(ev)
    expect(out).toEqual([{ x: true }])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && npm run test -- ndjson`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```ts
// apps/frontend/src/lib/ndjson.ts
export async function* readNdjson<T = any>(res: Response): AsyncGenerator<T> {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) if (line.trim()) yield JSON.parse(line) as T
  }
  if (buf.trim()) yield JSON.parse(buf) as T
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/frontend && npm run test -- ndjson`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/lib/ndjson.ts apps/frontend/src/__tests__/ndjson.test.ts
git commit -m "feat(frontend): ndjson stream reader"
```

### Task 10: Onboarding + Ollama API clients

**Files:**
- Create: `apps/frontend/src/api/onboarding.ts`, `apps/frontend/src/api/ollama.ts`
- Reference: `apps/frontend/src/api/client.ts` (existing `apiClient` + base URL resolution)

- [ ] **Step 1: Inspect the existing client**

Read `apps/frontend/src/api/client.ts` and reuse its exported request helper and base-URL getter (e.g. `apiClient.get/post` and a `getApiBaseUrl()`). The code below assumes `apiClient` with `.get(path)`, `.post(path, body)` returning parsed JSON, and `apiBaseUrl` for raw `fetch` streaming. Adapt names to the actual exports.

- [ ] **Step 2: Implement onboarding.ts**

```ts
// apps/frontend/src/api/onboarding.ts
import { apiClient } from './client'

export interface OnboardingState { completed: boolean; has_providers: boolean }

export const onboardingApi = {
  state: () => apiClient.get<OnboardingState>('/onboarding/state'),
  complete: () => apiClient.post('/onboarding/complete', {}),
  createOllamaProvider: () => apiClient.post('/onboarding/provider/ollama', {}),
  createOpenRouterProvider: (api_key: string) =>
    apiClient.post('/onboarding/provider/openrouter', { api_key }),
}
```

- [ ] **Step 3: Implement ollama.ts**

```ts
// apps/frontend/src/api/ollama.ts
import { apiClient, getApiBaseUrl } from './client'
import { readNdjson } from '../lib/ndjson'

export interface HardwareInfo {
  ram_gb: number; cpu_name: string; cpu_cores: number
  gpu_name: string | null; vram_gb: number | null
}
export interface ModelEntry {
  tag: string; label: string; params: string; approx_size_gb: number
  min_budget_gb: number; vision: boolean; blurb: string
}
export interface Recommendations {
  hardware: HardwareInfo; budget_gb: number; tier: string; tier_label: string
  models: ModelEntry[]; fallback_models: ModelEntry[]
}
export interface OllamaStatus {
  installed: boolean; running: boolean; version: string | null; models: string[]
}
export interface ProgressEvent {
  phase: string; percent?: number | null; message?: string
  completed?: number; total?: number; manual_url?: string; winget?: string
}

export const ollamaApi = {
  status: () => apiClient.get<OllamaStatus>('/ollama/status'),
  recommendations: () => apiClient.get<Recommendations>('/ollama/recommendations'),

  async *install(): AsyncGenerator<ProgressEvent> {
    const res = await fetch(`${getApiBaseUrl()}/api/ollama/install`, { method: 'POST' })
    yield* readNdjson<ProgressEvent>(res)
  },
  async *pull(model: string): AsyncGenerator<ProgressEvent> {
    const res = await fetch(`${getApiBaseUrl()}/api/ollama/pull`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    })
    yield* readNdjson<ProgressEvent>(res)
  },
}
```

- [ ] **Step 4: Typecheck**

Run: `cd apps/frontend && npm run build` (or `tsc --noEmit` if configured)
Expected: no type errors. Fix import names to match `client.ts`.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/api/onboarding.ts apps/frontend/src/api/ollama.ts
git commit -m "feat(frontend): onboarding + ollama API clients"
```

### Task 11: Wizard step components

**Files:**
- Create: `apps/frontend/src/components/onboarding/steps.tsx`
- Test: covered in Task 12

- [ ] **Step 1: Implement the step components**

```tsx
// apps/frontend/src/components/onboarding/steps.tsx
import { useEffect, useState } from 'react'
import { ollamaApi, type ProgressEvent, type Recommendations, type ModelEntry } from '../../api/ollama'
import { onboardingApi } from '../../api/onboarding'

export function WelcomeStep({ onChoose }: { onChoose: (p: 'ollama' | 'openrouter' | 'skip') => void }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100">Bem-vindo ao AgentDesk</h2>
        <p className="text-sm text-slate-400 mt-1">
          Para rodar agentes você precisa de pelo menos um provedor de modelos. Escolha um abaixo —
          você pode trocar depois nas Configurações.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="card">
          <p className="font-medium text-slate-100">Ollama</p>
          <p className="text-xs text-slate-400 mt-1">Local · grátis · privado. Usa a RAM/GPU da sua máquina. Instalável aqui pelo app.</p>
          <button className="btn-primary text-sm mt-3 w-full" onClick={() => onChoose('ollama')}>Configurar Ollama</button>
        </div>
        <div className="card">
          <p className="font-medium text-slate-100">OpenRouter</p>
          <p className="text-xs text-slate-400 mt-1">Nuvem · precisa de API key · pago. Nada para instalar.</p>
          <button className="btn-secondary text-sm mt-3 w-full" onClick={() => onChoose('openrouter')}>Usar OpenRouter</button>
        </div>
      </div>
      <button className="btn-ghost text-xs text-slate-500" onClick={() => onChoose('skip')}>Pular por enquanto</button>
    </div>
  )
}

function ProgressBar({ ev }: { ev: ProgressEvent | null }) {
  const pct = ev?.percent ?? null
  return (
    <div className="space-y-1">
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div className="h-full bg-blue-500 transition-all" style={{ width: pct != null ? `${pct}%` : '100%' }} />
      </div>
      <p className="text-xs text-slate-400">{ev?.message ?? ''}{pct != null ? ` (${pct}%)` : ''}</p>
    </div>
  )
}

export function OllamaStep({ onDone }: { onDone: () => void }) {
  const [phase, setPhase] = useState<'checking' | 'needs-install' | 'installing' | 'ready' | 'pulling' | 'error'>('checking')
  const [progress, setProgress] = useState<ProgressEvent | null>(null)
  const [recs, setRecs] = useState<Recommendations | null>(null)
  const [selected, setSelected] = useState<string>('')
  const [errorEv, setErrorEv] = useState<ProgressEvent | null>(null)

  const loadReady = async () => {
    const r = await ollamaApi.recommendations()
    setRecs(r)
    setSelected(r.models[0]?.tag ?? '')
    setPhase('ready')
  }

  useEffect(() => {
    ollamaApi.status().then(s => {
      if (s.running) loadReady()
      else setPhase('needs-install')
    }).catch(() => setPhase('needs-install'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const runInstall = async () => {
    setPhase('installing'); setErrorEv(null)
    for await (const ev of ollamaApi.install()) {
      setProgress(ev)
      if (ev.phase === 'error') { setErrorEv(ev); setPhase('error'); return }
      if (ev.phase === 'done') { await loadReady(); return }
    }
  }

  const runPull = async () => {
    if (!selected) return
    setPhase('pulling'); setErrorEv(null)
    for await (const ev of ollamaApi.pull(selected)) {
      setProgress(ev)
      if (ev.phase === 'error') { setErrorEv(ev); setPhase('error'); return }
      if (ev.phase === 'success') {
        await onboardingApi.createOllamaProvider()
        onDone(); return
      }
    }
  }

  if (phase === 'checking') return <p className="text-sm text-slate-400">Verificando o Ollama…</p>

  if (phase === 'needs-install' || phase === 'installing') {
    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-300">O Ollama ainda não está rodando. Instale-o pelo app:</p>
        {phase === 'installing' ? <ProgressBar ev={progress} /> :
          <button className="btn-primary text-sm" onClick={runInstall}>Instalar Ollama</button>}
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-400">{errorEv?.message ?? 'Algo deu errado.'}</p>
        <div className="flex gap-2">
          <button className="btn-secondary text-sm" onClick={runInstall}>Tentar novamente</button>
          {errorEv?.manual_url && (
            <a className="btn-ghost text-sm" href={errorEv.manual_url} target="_blank" rel="noreferrer">Baixar manualmente</a>
          )}
        </div>
        {errorEv?.winget && (
          <code className="block text-xs bg-slate-800 rounded px-2 py-1 text-slate-300">{errorEv.winget}</code>
        )}
      </div>
    )
  }

  // ready or pulling
  return (
    <div className="space-y-4">
      {recs && (
        <div className="card text-xs text-slate-400">
          Hardware: {recs.hardware.ram_gb} GB RAM · {recs.hardware.cpu_cores} núcleos
          {recs.hardware.gpu_name ? ` · ${recs.hardware.gpu_name}` : ''}
          {recs.hardware.vram_gb ? ` (${recs.hardware.vram_gb} GB VRAM)` : ''}
        </div>
      )}
      <p className="text-sm text-slate-300">Modelos recomendados para sua máquina (tier {recs?.tier_label}):</p>
      <div className="space-y-2">
        {recs?.models.map((m: ModelEntry) => (
          <label key={m.tag} className={`card flex items-start gap-3 cursor-pointer ${selected === m.tag ? 'ring-1 ring-blue-500' : ''}`}>
            <input type="radio" name="model" className="mt-1" checked={selected === m.tag} onChange={() => setSelected(m.tag)} />
            <div className="min-w-0">
              <p className="font-medium text-slate-100">{m.label} <span className="text-xs text-slate-500">{m.params} · {m.approx_size_gb} GB{m.vision ? ' · visão' : ''}</span></p>
              <p className="text-xs text-slate-400">{m.blurb}</p>
            </div>
          </label>
        ))}
      </div>
      {phase === 'pulling' ? <ProgressBar ev={progress} /> :
        <button className="btn-primary text-sm" onClick={runPull} disabled={!selected}>Instalar modelo selecionado</button>}
    </div>
  )
}

export function OpenRouterStep({ onDone }: { onDone: () => void }) {
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submit = async () => {
    setBusy(true); setError(null)
    try { await onboardingApi.createOpenRouterProvider(key); onDone() }
    catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-300">Cole sua API key do OpenRouter:</p>
      <input type="password" className="input w-full" placeholder="sk-or-..." value={key}
        onChange={e => setKey(e.target.value)} />
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button className="btn-primary text-sm" onClick={submit} disabled={busy || !key}>{busy ? 'Salvando…' : 'Salvar e continuar'}</button>
    </div>
  )
}

export function DoneStep({ onClose }: { onClose: () => void }) {
  return (
    <div className="space-y-4 text-center">
      <p className="text-lg font-bold text-slate-100">Tudo pronto!</p>
      <p className="text-sm text-slate-400">Seu provedor está configurado. Vamos começar a conversar.</p>
      <button className="btn-primary text-sm" onClick={onClose}>Ir para o chat</button>
    </div>
  )
}
```

Note: reuse existing CSS utility classes (`card`, `btn-primary`, `btn-secondary`, `btn-ghost`, `input`) — confirm these exist in the project's Tailwind layer (`Providers.tsx` uses `card`, `btn-primary`, etc.). If `input` is not defined, use the same classes as `ProviderForm.tsx`.

- [ ] **Step 2: Commit**

```bash
git add apps/frontend/src/components/onboarding/steps.tsx
git commit -m "feat(frontend): onboarding step components"
```

### Task 12: Wizard shell + gating + tests

**Files:**
- Create: `apps/frontend/src/components/onboarding/OnboardingWizard.tsx`
- Modify: `apps/frontend/src/App.tsx`
- Test: `apps/frontend/src/__tests__/Onboarding.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// apps/frontend/src/__tests__/Onboarding.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { OnboardingWizard } from '../components/onboarding/OnboardingWizard'

vi.mock('../api/onboarding', () => ({
  onboardingApi: {
    state: vi.fn().mockResolvedValue({ completed: false, has_providers: false }),
    complete: vi.fn().mockResolvedValue({}),
    createOllamaProvider: vi.fn().mockResolvedValue({ type: 'ollama' }),
    createOpenRouterProvider: vi.fn().mockResolvedValue({ type: 'openrouter' }),
  },
}))

describe('OnboardingWizard', () => {
  beforeEach(() => localStorage.clear())

  it('renders welcome and routes to OpenRouter path', async () => {
    render(<OnboardingWizard onFinished={() => {}} />)
    await screen.findByText('Bem-vindo ao AgentDesk')
    await userEvent.click(screen.getByText('Usar OpenRouter'))
    expect(await screen.findByPlaceholderText('sk-or-...')).toBeInTheDocument()
  })

  it('skip sets localStorage flag and finishes', async () => {
    const onFinished = vi.fn()
    render(<OnboardingWizard onFinished={onFinished} />)
    await screen.findByText('Bem-vindo ao AgentDesk')
    await userEvent.click(screen.getByText('Pular por enquanto'))
    await waitFor(() => expect(localStorage.getItem('agentdesk.onboardingSkipped')).toBe('1'))
    expect(onFinished).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/frontend && npm run test -- Onboarding`
Expected: FAIL — component missing.

- [ ] **Step 3: Implement the wizard shell**

```tsx
// apps/frontend/src/components/onboarding/OnboardingWizard.tsx
import { useState } from 'react'
import { onboardingApi } from '../../api/onboarding'
import { WelcomeStep, OllamaStep, OpenRouterStep, DoneStep } from './steps'
import { Logo } from '../Logo'

type Step = 'welcome' | 'ollama' | 'openrouter' | 'done'

export function OnboardingWizard({ onFinished }: { onFinished: () => void }) {
  const [step, setStep] = useState<Step>('welcome')

  const finishSkipped = () => {
    localStorage.setItem('agentdesk.onboardingSkipped', '1')
    onFinished()
  }
  const finishCompleted = async () => {
    await onboardingApi.complete().catch(() => {})
    onFinished()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/95">
      <div className="w-[560px] max-w-[92vw] rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <Logo className="h-7 w-7" />
          <span className="text-sm font-bold text-slate-200">AgentDesk</span>
        </div>
        {step === 'welcome' && (
          <WelcomeStep onChoose={p => {
            if (p === 'skip') finishSkipped()
            else setStep(p)
          }} />
        )}
        {step === 'ollama' && <OllamaStep onDone={() => setStep('done')} />}
        {step === 'openrouter' && <OpenRouterStep onDone={() => setStep('done')} />}
        {step === 'done' && <DoneStep onClose={finishCompleted} />}
      </div>
    </div>
  )
}
```

Note: this component renders `fixed inset-0` — acceptable here because it is a real app overlay (not the visualize sandbox). `Logo` is created in Task 13; if implementing this task first, temporarily replace `<Logo .../>` with a text span and wire it after Task 13.

- [ ] **Step 4: Gate it in App.tsx**

Add a gating hook in `apps/frontend/src/App.tsx` so the wizard renders over everything when first-run conditions hold. Insert inside `App`, wrapping the existing tree:

```tsx
import { useEffect, useState } from 'react'
import { onboardingApi } from './api/onboarding'
// ...existing imports...

function useOnboardingGate() {
  const [show, setShow] = useState(false)
  useEffect(() => {
    const isElectron = !!(window as any).electronAPI?.apiBaseUrl
    if (!isElectron) return // never gate in browser/dev/test
    if (localStorage.getItem('agentdesk.onboardingSkipped')) return
    onboardingApi.state()
      .then(s => setShow(!s.completed && !s.has_providers))
      .catch(() => setShow(false))
  }, [])
  return { show, dismiss: () => setShow(false) }
}
```

Then in the returned JSX (inside `StartupScreen`, before/around `HashRouter`):

```tsx
export function App() {
  const onboarding = useOnboardingGate()
  return (
    <StartupScreen>
      {onboarding.show && <OnboardingWizard onFinished={onboarding.dismiss} />}
      <HashRouter>
        {/* ...existing routes unchanged... */}
      </HashRouter>
    </StartupScreen>
  )
}
```

Add `import { OnboardingWizard } from './components/onboarding/OnboardingWizard'`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/frontend && npm run test -- Onboarding`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/frontend/src/components/onboarding/OnboardingWizard.tsx apps/frontend/src/App.tsx apps/frontend/src/__tests__/Onboarding.test.tsx
git commit -m "feat(frontend): onboarding wizard shell + first-run gating"
```

---

## Phase 4 — Logo + packaging

### Task 13: Logo SVG + React component

**Files:**
- Create: `apps/frontend/src/assets/logo.svg`
- Create: `apps/frontend/src/components/Logo.tsx`
- Create: `apps/frontend/public/favicon.svg`
- Modify: `apps/frontend/index.html`, `apps/frontend/src/components/Sidebar.tsx`, `apps/frontend/src/components/StartupScreen.tsx`
- Test: `apps/frontend/src/__tests__/Logo.test.tsx`

- [ ] **Step 1: Create the logo SVG (Orbit / leader motif)**

```
<!-- apps/frontend/src/assets/logo.svg AND apps/frontend/public/favicon.svg (identical) -->
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="AgentDesk">
  <rect width="64" height="64" rx="14" fill="#0f172a"/>
  <circle cx="32" cy="32" r="20" fill="none" stroke="#1e3a5f" stroke-width="2"/>
  <line x1="32" y1="32" x2="32" y2="14" stroke="#3b82f6" stroke-width="2.5"/>
  <line x1="32" y1="32" x2="17" y2="43" stroke="#3b82f6" stroke-width="2.5"/>
  <line x1="32" y1="32" x2="47" y2="43" stroke="#3b82f6" stroke-width="2.5"/>
  <circle cx="32" cy="14" r="4.5" fill="#38bdf8"/>
  <circle cx="17" cy="43" r="4.5" fill="#38bdf8"/>
  <circle cx="47" cy="43" r="4.5" fill="#38bdf8"/>
  <circle cx="32" cy="32" r="7" fill="#3b82f6"/>
</svg>
```

- [ ] **Step 2: Write the failing test**

```tsx
// apps/frontend/src/__tests__/Logo.test.tsx
import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Logo } from '../components/Logo'

describe('Logo', () => {
  it('renders an svg with the accessible label', () => {
    const { container } = render(<Logo className="h-8 w-8" />)
    const svg = container.querySelector('svg')
    expect(svg).toBeTruthy()
    expect(svg?.getAttribute('aria-label')).toBe('AgentDesk')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/frontend && npm run test -- Logo`
Expected: FAIL — component missing.

- [ ] **Step 4: Implement Logo.tsx** (inline SVG so it inherits sizing/color cleanly)

```tsx
// apps/frontend/src/components/Logo.tsx
export function Logo({ className = 'h-8 w-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="AgentDesk" xmlns="http://www.w3.org/2000/svg">
      <rect width="64" height="64" rx="14" fill="#0f172a" />
      <circle cx="32" cy="32" r="20" fill="none" stroke="#1e3a5f" strokeWidth="2" />
      <line x1="32" y1="32" x2="32" y2="14" stroke="#3b82f6" strokeWidth="2.5" />
      <line x1="32" y1="32" x2="17" y2="43" stroke="#3b82f6" strokeWidth="2.5" />
      <line x1="32" y1="32" x2="47" y2="43" stroke="#3b82f6" strokeWidth="2.5" />
      <circle cx="32" cy="14" r="4.5" fill="#38bdf8" />
      <circle cx="17" cy="43" r="4.5" fill="#38bdf8" />
      <circle cx="47" cy="43" r="4.5" fill="#38bdf8" />
      <circle cx="32" cy="32" r="7" fill="#3b82f6" />
    </svg>
  )
}
```

- [ ] **Step 5: Wire the logo into the UI**

In `apps/frontend/src/components/Sidebar.tsx` replace the header text block (lines ~91-93) so the logo sits next to the name:

```tsx
import { Logo } from './Logo'
// ...
<div className="px-4 py-4 border-b border-slate-800">
  <div className="flex items-center gap-2">
    <Logo className="h-6 w-6" />
    <span className="text-base font-bold text-slate-100 tracking-tight">AgentDesk</span>
  </div>
  <div className="mt-1"><StatusBadge status={status} /></div>
</div>
```

In `apps/frontend/src/components/StartupScreen.tsx`, replace the `checking` state's text title (line ~71) with the logo above it:

```tsx
import { Logo } from './Logo'
// ...inside the checking branch, above the title div:
<Logo className="h-12 w-12" />
```

In `apps/frontend/index.html`, add inside `<head>`:

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
```

- [ ] **Step 6: Run tests + build to verify**

Run: `cd apps/frontend && npm run test -- Logo && npm run build`
Expected: Logo test passes; build succeeds.

- [ ] **Step 7: Commit**

```bash
git add apps/frontend/src/assets/logo.svg apps/frontend/public/favicon.svg apps/frontend/src/components/Logo.tsx apps/frontend/src/components/Sidebar.tsx apps/frontend/src/components/StartupScreen.tsx apps/frontend/index.html apps/frontend/src/__tests__/Logo.test.tsx
git commit -m "feat(frontend): Orbit logo + favicon wired into UI"
```

### Task 14: Windows app icon (.ico)

**Files:**
- Create: `apps/desktop/build/icon.svg` (copy of the logo SVG)
- Create: `apps/desktop/scripts/make-icon.mjs`
- Modify: `apps/desktop/package.json`
- Generated: `apps/desktop/build/icon.ico`

- [ ] **Step 1: Copy the logo SVG**

Create `apps/desktop/build/icon.svg` with the same content as `apps/frontend/public/favicon.svg` from Task 13 Step 1.

- [ ] **Step 2: Add the icon generation script**

```js
// apps/desktop/scripts/make-icon.mjs
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import sharp from 'sharp'
import pngToIco from 'png-to-ico'

const here = dirname(fileURLToPath(import.meta.url))
const buildDir = join(here, '..', 'build')
const svg = readFileSync(join(buildDir, 'icon.svg'))

const sizes = [16, 24, 32, 48, 64, 128, 256]
const pngs = await Promise.all(
  sizes.map(s => sharp(svg, { density: 384 }).resize(s, s).png().toBuffer())
)
const ico = await pngToIco(pngs)
writeFileSync(join(buildDir, 'icon.ico'), ico)
// 256px PNG too (electron-builder/Linux + docs)
writeFileSync(join(buildDir, 'icon.png'), pngs[pngs.length - 1])
console.log('Wrote build/icon.ico and build/icon.png')
```

- [ ] **Step 3: Add devDeps + script to `apps/desktop/package.json`**

Under `devDependencies` add `"sharp": "^0.33.0"` and `"png-to-ico": "^2.1.8"`. Under `scripts` add `"make-icon": "node scripts/make-icon.mjs"`. Under `build.win` add `"icon": "build/icon.ico"`.

- [ ] **Step 4: Install and generate**

Run:
```bash
cd apps/desktop && npm install && npm run make-icon
```
Expected: prints "Wrote build/icon.ico and build/icon.png"; both files exist.

- [ ] **Step 5: Verify the ico is valid**

Run: `cd apps/desktop && node -e "console.log(require('fs').statSync('build/icon.ico').size > 0)"`
Expected: `true`.

- [ ] **Step 6: Commit**

```bash
git add apps/desktop/build/icon.svg apps/desktop/build/icon.ico apps/desktop/build/icon.png apps/desktop/scripts/make-icon.mjs apps/desktop/package.json apps/desktop/package-lock.json
git commit -m "feat(desktop): generate Windows app icon from Orbit logo"
```

### Task 15: Build the new portable exe

**Files:** none modified; runs the existing build pipeline.

- [ ] **Step 1: Full backend suite (green gate)**

Run: `cd backend && venv/Scripts/python -m pytest -q`
Expected: all pass.

- [ ] **Step 2: Full frontend suite (green gate)**

Run: `cd apps/frontend && npm run test`
Expected: all pass.

- [ ] **Step 3: Run the one-step Windows build**

Run: `pwsh scripts/build-windows.ps1`
Expected: completes; prints artifacts including `AgentDesk-Portable-0.1.0.exe` under `dist/electron/`.

- [ ] **Step 4: Confirm the artifact exists with the new icon**

Run: `pwsh -Command "Get-ChildItem dist/electron/*.exe | Select-Object Name,Length"`
Expected: `AgentDesk-Portable-0.1.0.exe` (and `AgentDesk-Setup-0.1.0.exe`) listed with non-zero size. Visually confirm the new icon in Explorer.

- [ ] **Step 5: Manual smoke (per spec §8)**

Launch `AgentDesk-Portable-0.1.0.exe` against a clean `%APPDATA%/AgentDesk` (rename any existing folder first). Confirm: new icon in taskbar; the onboarding wizard appears; "Pular por enquanto" reaches the chat; relaunch does not show the wizard again.

- [ ] **Step 6: Commit any lockfile/config changes** (if the build touched none, skip)

```bash
git status   # commit only if tracked files changed
```

---

## Self-review notes

- **Spec coverage:** Ollama install (Task 5/6/12), hardware detection (Task 3), model recommendation ranked list (Task 4/6/12), OpenRouter path (Task 7/11/12), non-mandatory skip + gating (Task 12), provider auto-creation (Task 7), logo everywhere + icon (Task 13/14), new portable exe (Task 15). All spec sections map to a task.
- **Streaming deviation from spec §4.4:** provider creation is a discrete `POST /onboarding/provider/*` call made by the frontend after a successful pull/key submit, rather than a `provider_created` event embedded in the stream. Cleaner DB-session handling; same user-visible result.
- **Enum/exports to verify at implementation time:** `ProviderType` member names (`backend/app/domain/enums.py`); `apiClient`/`getApiBaseUrl` exact exports in `apps/frontend/src/api/client.ts`; Tailwind utility classes (`card`, `btn-*`, `input`). Each task notes the check.
- **Type consistency:** `ProgressEvent`, `Recommendations`, `ModelEntry`, `OllamaStatus`, `OnboardingState` are defined once in the API clients and reused by the components/tests.
