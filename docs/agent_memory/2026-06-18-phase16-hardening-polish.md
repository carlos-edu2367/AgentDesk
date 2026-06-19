# Phase 16 Hardening and Polish

## What exists now

- Frontend E2E is configured with Playwright under `apps/frontend/e2e`.
- Playwright tests mock `/api/*`, so they do not require Ollama, OpenRouter, or a live backend.
- `apps/frontend/src/api/approvals.ts` now uses the shared API client instead of hardcoding `localhost:8000`.
- StartupScreen reports the injected local API URL and the startup log path on failure.
- Safe local examples exist under `examples/plugins/echo-plugin`, `examples/mcp/mock-mcp-server.py`, and `examples/prompts/simple-agent-test.md`.
- Final MVP docs exist for README, contributing, user guide, developer guide, plugin SDK, MCP stdio, troubleshooting, manual smoke test, and release checklist.

## Decisions

- E2E mocks backend routes because Phase 16 requires UI coverage without depending on real providers.
- `docs/specs/15-testing-strategy.md` was created as a standalone testing strategy file because the referenced spec was missing and the strategy text had been appended to packaging docs.
- No dependency audit force-fix was applied because `npm audit fix --force` can introduce breaking upgrades outside Phase 16.
- Packaged Electron now uses `app.isPackaged` instead of `NODE_ENV` to decide dev/prod behavior because packaged builds can launch with an empty `NODE_ENV`.
- Windows package builds set `win.signAndEditExecutable=false` because electron-builder's `winCodeSign` cache extraction failed on this machine when creating symlinks. This keeps local package generation working, but the resulting executables are unsigned and use fallback executable metadata.
- Automated Electron smoke tests must remove `ELECTRON_RUN_AS_NODE` from the child process environment. When this variable is present, the packaged Electron executable exits as a Node runtime and does not load `main.js`.
- The portable NSIS wrapper can exit before the extracted `AgentDesk.exe` process. Portable smoke tests should follow the extracted process from `startup.log` and close that process to verify backend shutdown.

## Follow-up

- Run packaged smoke tests on a clean Windows profile before release.
- Review npm audit output and upgrade dependencies deliberately.
- Add CI once the MVP release checklist is stable.
- Add production icons before release; electron-builder currently uses the default Electron icon.
