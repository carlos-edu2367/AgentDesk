# Contributing to AgentDesk

## Setup

Use Windows PowerShell for the supported MVP environment.

```powershell
cd backend
python -m pip install -r requirements.txt

cd ..\apps\frontend
npm install

cd ..\desktop
npm install
```

## Running Locally

Backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd apps/frontend
npm run dev
```

Electron:

```powershell
cd apps/desktop
$env:BACKEND_PORT='8000'
npm run dev
```

## Tests

```powershell
python -m pytest backend/tests -q
cd apps/frontend
npm test -- --run
npm run build
npm run test:e2e
```

## Branches and Commits

Use short branch names such as `phase16-e2e-docs` or `fix-startup-logs`. Keep commits focused by subsystem. Commit messages should use a clear prefix such as `feat:`, `fix:`, `test:`, or `docs:`.

## Issues and PRs

Describe the behavior, expected result, reproduction steps, and security impact. For tool, plugin, MCP, provider, or packaging changes, include the exact verification commands and outputs.

## Security Rules

- Do not log API keys, Authorization headers, cookies, passwords, tokens, private keys, or MCP env secrets.
- Do not bypass the Permission Gate for filesystem, terminal, plugin, or MCP actions.
- Do not use frontend state, model output, plugin output, or user input as the source of truth for critical permissions.
- Keep backend bound to `127.0.0.1`.
- Keep manual approval working for critical tools.
- Treat local plugins and MCP servers as code execution surfaces.
