# AgentDesk Developer Guide

## Architecture

The backend is the source of truth for storage, permissions, execution state, audit logs, tools, plugins, MCP, and provider calls. The frontend renders state and sends commands through REST/SSE. Electron is responsible for packaged startup, API base URL injection, startup logs, and backend shutdown.

## Backend

Run from `backend/`:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
python -m pytest tests -q
```

Migrations run on startup through the app lifecycle. Packaged mode uses `backend/server.py`.

## Frontend

Run from `apps/frontend/`:

```powershell
npm run dev
npm test -- --run
npm run build
npm run test:e2e
```

Use the shared API client in `src/api/client.ts`; do not hardcode host/port in feature API modules.

## Desktop

Run from `apps/desktop/`:

```powershell
$env:BACKEND_PORT='8000'
npm run dev
$env:CSC_IDENTITY_AUTO_DISCOVERY='false'
npm run package:portable
npm run package:installer
```

Packaged startup writes logs to `%APPDATA%\AgentDesk\logs\app\startup.log` and the backend writes `%APPDATA%\AgentDesk\logs\app\backend.log`.

When smoke-testing packaged Electron from a shell that was used by npm/Electron tooling, ensure the child process does not inherit `ELECTRON_RUN_AS_NODE`. Portable builds launch a wrapper first; follow the extracted `AgentDesk.exe` path in `startup.log` when validating window close and backend shutdown.

## Testing Strategy

Backend tests cover domain, CRUD, providers, permissions, tools, memory, skills, plugins, MCP, audit, and packaging structure. Frontend Vitest covers screens and API behavior. Playwright mocks `/api/*` so E2E does not require Ollama or OpenRouter.
