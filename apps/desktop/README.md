# AgentDesk Desktop

Electron shell that wraps the AgentDesk frontend and manages the backend process.

## Development

Run backend and frontend separately, then start Electron in dev mode:

```bash
# Terminal 1 – backend (from backend/)
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 – frontend (from apps/frontend/)
npm run dev

# Terminal 3 – Electron (from apps/desktop/)
npm run dev
```

Electron in dev mode (`NODE_ENV=development`) connects to the Vite dev server on port 5173
and expects the backend already running on port 8000 (or `BACKEND_PORT` env var).

## Build (packaged)

### 1. Build frontend

```bash
cd apps/frontend
npm run build
# Output: apps/frontend/dist/
```

### 2. Build backend with PyInstaller

```bash
cd backend
pip install pyinstaller
pyinstaller pyinstaller/agentdesk-backend.spec
# Output: backend/dist/agentdesk-backend/agentdesk-backend.exe
```

### 3. Install Electron deps

```bash
cd apps/desktop
npm install
```

### 4. Package for Windows

```bash
# Installer (NSIS) + Portable
npm run build

# Portable only
npm run package:portable

# Installer only
npm run package:installer
```

Output in `dist/electron/`.

## Architecture

- **main.js** – Electron main process
  - In packaged mode: finds a free port (default 8765), spawns `agentdesk-backend.exe`,
    polls `/api/health`, then creates the window.
  - In dev mode: skips backend spawn; connects to the manually started backend.
- **preload.js** – Exposes `window.electronAPI.apiBaseUrl` synchronously to the renderer.
- **Frontend** reads `window.electronAPI.apiBaseUrl` first, falls back to `VITE_API_BASE_URL`.

## Startup Logs

Logs are written to:

```
%APPDATA%\AgentDesk\logs\app\startup.log
%APPDATA%\AgentDesk\logs\app\backend.log
```

## Backend Shutdown

When the app window is closed (`window-all-closed`) or the app quits (`will-quit`),
`taskkill /PID <pid> /T /F` is used to terminate the backend process tree on Windows.
