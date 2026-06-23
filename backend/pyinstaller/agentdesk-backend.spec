# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the AgentDesk backend.

Build from the backend/ directory:
    pyinstaller pyinstaller/agentdesk-backend.spec

Output:
    backend/dist/agentdesk-backend/agentdesk-backend.exe
"""
from pathlib import Path

block_cipher = None

spec_dir = Path(SPECPATH)       # backend/pyinstaller/
backend_dir = spec_dir.parent   # backend/

a = Analysis(
    [str(backend_dir / "server.py")],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=[
        # Alembic config and migration scripts must travel with the binary.
        (str(backend_dir / "alembic.ini"), "."),
        (str(backend_dir / "alembic"), "alembic"),
        # Bundled base (builtin) skills seeded on startup.
        (str(backend_dir / "resources"), "resources"),
    ],
    hiddenimports=[
        # uvicorn internals not always auto-detected
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.config",
        # SQLAlchemy dialect
        "sqlalchemy.dialects.sqlite",
        # Alembic runtime
        "alembic.runtime.migration",
        "alembic.operations",
        "alembic.operations.ops",
        # All FastAPI routers (dynamic imports inside main.py)
        "app.api.routers.agents",
        "app.api.routers.teams",
        "app.api.routers.workspaces",
        "app.api.routers.providers",
        "app.api.routers.executions",
        "app.api.routers.skills",
        "app.api.routers.mcp",
        "app.api.routers.plugins",
        "app.api.routers.memories",
        "app.api.routers.tools",
        "app.api.routers.approvals",
        "app.api.routers.audit",
        "app.api.routers.logs",
        # Startup seeder (dynamic import in lifespan)
        "app.skills.seeder",
        # Pydantic v2 validators (sometimes missing)
        "pydantic.deprecated.class_validators",
        "pydantic.deprecated.config",
        # Computer-use: comtypes generates bindings at runtime;
        # must be collected wholesale so uiautomation works in frozen app.
        "comtypes",
        "comtypes.gen",
        "uiautomation",
        "mss",
        "pynput",
        "pynput.keyboard",
        "pynput.mouse",
    ],
    collect_submodules=[
        "comtypes",
        "uiautomation",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="agentdesk-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # stdout needed so Electron can read AGENTDESK_PORT
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="agentdesk-backend",
)
