# AgentDesk Testing Strategy

This file separates the testing strategy that was historically appended to `docs/specs/14-packaging-windows.md`.

## Test Layers

- Backend unit and API tests with pytest.
- Tool safety tests for workspace boundaries, approvals, terminal timeout, and masking.
- Provider tests with mocks for Ollama and OpenRouter.
- Frontend tests with Vitest and React Testing Library.
- Playwright E2E tests with mocked backend APIs.
- Packaging smoke tests for PyInstaller and Electron artifacts.

## Required Commands

```powershell
python -m pytest backend/tests -q
cd apps/frontend
npm test -- --run
npm run build
npm run test:e2e
```

## Packaging Smoke

After building, verify:

- Backend executable starts and prints `AGENTDESK_PORT:<port>`.
- `/api/health` returns ok.
- AppData, SQLite, migrations, and logs are created.
- Electron portable opens, clears StartupScreen, loads Dashboard, and closes the backend.
