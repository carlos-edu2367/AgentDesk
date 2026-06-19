# AgentDesk

AgentDesk is a Windows-first, local-first desktop MVP for creating and running AI agents on your machine. It combines a FastAPI backend, SQLite storage, a React/Vite frontend, and an Electron shell that can launch a packaged local backend.

## MVP Status

The MVP includes local AppData storage, SQLite migrations, Ollama and OpenRouter providers, agents, teams, native tools with approval gates, audit logs, memory, skills, local plugins, MCP stdio, exports, and Windows packaging scripts. Phase 16 focuses on hardening, tests, documentation, examples, and packaging smoke validation.

## Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic, SQLite
- Frontend: React, TypeScript, Vite, TailwindCSS
- Desktop: Electron, electron-builder
- Local models: Ollama
- Remote models: OpenRouter
- E2E: Playwright

## Development

Backend:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd apps/frontend
npm install
npm run dev
```

Electron dev shell:

```powershell
cd apps/desktop
npm install
$env:BACKEND_PORT='8000'
npm run dev
```

## Providers

Ollama is optional and must be installed separately. Use `http://localhost:11434` as the default base URL. AgentDesk should show a friendly unavailable status when Ollama is not running.

OpenRouter works after adding an API key in Providers. API keys must be masked in UI, logs, audit records, and exports.

## Tests

```powershell
python -m pytest backend/tests -q
cd apps/frontend
npm test -- --run
npm run build
npm run test:e2e
```

## Packaging

Build backend executable:

```powershell
cd backend
python -m pip install pyinstaller
pyinstaller pyinstaller/agentdesk-backend.spec
```

Build Windows desktop artifacts:

```powershell
cd apps/desktop
npm install
npm run package:portable
npm run package:installer
```

Expected artifacts are under `dist/electron/` at the repository root.

## Security Notes

AgentDesk can execute local tools. Manual approval is the safe default for critical actions. Workspaces constrain filesystem and terminal access. Plugins and MCP servers are local code/process integrations, so only use examples or code you trust.

## Project Structure

```txt
backend/        FastAPI backend, domain, storage, tools, runtime, tests
apps/frontend/ React/Vite desktop UI
apps/desktop/  Electron shell and packaging config
docs/          Specs, guides, testing, troubleshooting, release docs
examples/      Safe local plugin, MCP, and prompt examples
```

## License

Open-source MVP. Add the project license file before public release.
