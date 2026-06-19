# AgentDesk Troubleshooting

## Backend nao inicia

Check `%APPDATA%\AgentDesk\logs\app\startup.log` and `backend.log`. In development, confirm the backend is running on `127.0.0.1:8000`.

## Porta ocupada

Packaged mode starts at `8765` and searches for another local port. Development mode uses `BACKEND_PORT` or `8000`.

## PyInstaller falha

Run from `backend/`:

```powershell
python -m pip install pyinstaller
python -m PyInstaller pyinstaller/agentdesk-backend.spec
```

Confirm `alembic.ini`, `alembic/`, and `server.py` exist.

## Electron package falha em winCodeSign

On Windows without symlink privileges, electron-builder can fail while extracting the `winCodeSign` cache. Local unsigned builds use `win.signAndEditExecutable=false` in `apps/desktop/package.json` and can be run with:

```powershell
$env:CSC_IDENTITY_AUTO_DISCOVERY='false'
npm run package:portable
npm run package:installer
```

Release signing and executable metadata should be handled deliberately before public distribution.

## Electron abre tela branca

Run `npm run build` in `apps/frontend`, then package again. In development, confirm Vite is running at `http://localhost:5173`.

## Ollama indisponivel

Start Ollama separately and check `http://localhost:11434`. AgentDesk should still run without Ollama, but local model/embedding calls can fail.

## OpenRouter API key invalida

Re-enter the key in Providers. Do not paste keys into logs, issues, or screenshots.

## SQLite locked

Close duplicate backend processes, then retry. Check Task Manager for stale `agentdesk-backend.exe`.

## Alembic/migrations no packaged

The PyInstaller spec must bundle `alembic.ini` and the `alembic` directory. Check `backend.log` for migration errors.

## Plugin falha

Use the sample plugin first. Check manifest path, JSON stdin/stdout, command, timeout, and stderr preview. Do not add secrets to plugin env or output.

## MCP server nao responde

Use the mock MCP server first. Verify command, args, env, and that the process speaks JSON-RPC over stdio.

## Backend fica preso apos fechar app

Packaged Electron should terminate the backend process tree on quit. If a stale process remains, record its PID and inspect `startup.log`.

## Smoke test do Electron sai imediatamente

If a packaged Electron smoke test exits with code 0 before creating `startup.log`, check the shell environment:

```powershell
Get-ChildItem Env:ELECTRON*
```

Remove `ELECTRON_RUN_AS_NODE` from the child process environment before launching packaged `AgentDesk.exe`.
