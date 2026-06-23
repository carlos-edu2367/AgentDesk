# AgentDesk Release Checklist

## Build (one step)

```powershell
pwsh scripts/build-windows.ps1          # add -InstallDeps on a fresh checkout
```

Stages: frontend bundle → backend exe (PyInstaller) → Electron portable + NSIS
installer. Artifacts land in `dist/electron/`:

- `AgentDesk-Setup-<version>.exe`     — NSIS installer
- `AgentDesk-Portable-<version>.exe`  — portable single-file executable

## Smoke test (verify backend + frontend launch together)

1. Run the packaged app (portable exe, or `dist/electron/win-unpacked/AgentDesk.exe`).
2. Tail `%APPDATA%\AgentDesk\logs\app\startup.log` and confirm, in order:
   - `Selected port: <n>` and the backend exe path
   - `[backend] AGENTDESK_PORT:<n>`
   - `Health OK: {"status":"ok",...}`
   - `API base URL: http://127.0.0.1:<n>`
3. The main window opens and renders the UI (not the startup/error screen).
4. Close the window and confirm no orphan `agentdesk-backend.exe` remains
   (`tasklist /FI "IMAGENAME eq agentdesk-backend.exe"`).

## Tests
- [ ] Backend pytest passou
- [ ] Frontend vitest passou
- [ ] Frontend build passou
- [ ] Playwright passou
- [ ] PyInstaller build passou
- [ ] Portable abriu (backend spawnou + Health OK + janela)
- [ ] Installer abriu
- [ ] Sem backend órfão após fechar a janela

## Security
- [ ] Secrets mascarados
- [ ] Backend local-only
- [ ] Plugins auditados
- [ ] MCP auditado
- [ ] Approval manual testado

## Docs
- [ ] README atualizado
- [ ] CONTRIBUTING atualizado
- [ ] User guide atualizado
- [ ] Plugin SDK documentado
- [ ] MCP documentado
- [ ] Troubleshooting atualizado
