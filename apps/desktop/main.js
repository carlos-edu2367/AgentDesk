'use strict'

const { app, BrowserWindow, ipcMain, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const net = require('net')
const fs = require('fs')
const os = require('os')

// ── Constants ────────────────────────────────────────────────────────────────

const isDev = !app.isPackaged
const FRONTEND_DEV_URL = 'http://localhost:5173'
const DEFAULT_BACKEND_PORT = 8765
const BACKEND_STARTUP_TIMEOUT_MS = 30_000
const HEALTH_CHECK_ATTEMPTS = 30
const HEALTH_CHECK_INTERVAL_MS = 1_000

// ── State ────────────────────────────────────────────────────────────────────

let backendProcess = null
let mainWindow = null
let apiBaseUrl = null
let startupLogPath = null
let shuttingDownBackend = false

// ── AppData helpers ──────────────────────────────────────────────────────────

function getAppDataDir() {
  return process.env.APPDATA
    ? path.join(process.env.APPDATA, 'AgentDesk')
    : path.join(os.homedir(), '.agentdesk')
}

// ── Logging ──────────────────────────────────────────────────────────────────

function initStartupLog() {
  const logDir = path.join(getAppDataDir(), 'logs', 'app')
  fs.mkdirSync(logDir, { recursive: true })
  startupLogPath = path.join(logDir, 'startup.log')
  // Rotate: keep only last 500 KB
  try {
    const stat = fs.statSync(startupLogPath)
    if (stat.size > 512 * 1024) fs.truncateSync(startupLogPath, 0)
  } catch {
    // File may not exist yet
  }
}

function log(msg) {
  const line = `[${new Date().toISOString()}] [electron] ${msg}`
  console.log(line)
  if (startupLogPath) {
    try {
      fs.appendFileSync(startupLogPath, line + '\n', 'utf8')
    } catch {
      // Non-fatal; startup log is best-effort
    }
  }
}

function bootstrapLog(msg) {
  try {
    const logDir = path.join(getAppDataDir(), 'logs', 'app')
    fs.mkdirSync(logDir, { recursive: true })
    fs.appendFileSync(
      path.join(logDir, 'startup.log'),
      `[${new Date().toISOString()}] [electron:bootstrap] ${msg}\n`,
      'utf8',
    )
  } catch {
    // Startup logging must never prevent app launch.
  }
}

bootstrapLog(`main loaded; packaged=${app.isPackaged}; argv=${process.argv.join(' ')}`)

process.on('uncaughtException', (err) => {
  bootstrapLog(`uncaughtException: ${err.stack || err.message}`)
})

process.on('unhandledRejection', (reason) => {
  bootstrapLog(`unhandledRejection: ${reason instanceof Error ? reason.stack || reason.message : String(reason)}`)
})

// ── Port management ──────────────────────────────────────────────────────────

function isPortFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.once('listening', () => {
      server.close()
      resolve(true)
    })
    server.listen(port, '127.0.0.1')
  })
}

async function findFreePort(start = DEFAULT_BACKEND_PORT, end = 8900) {
  for (let p = start; p <= end; p++) {
    if (await isPortFree(p)) return p
  }
  throw new Error(`No free port found in range ${start}–${end}`)
}

// ── Backend path ─────────────────────────────────────────────────────────────

function getBackendExePath() {
  // electron-builder places extraResources at process.resourcesPath
  return path.join(
    process.resourcesPath,
    'backend',
    'agentdesk-backend',
    'agentdesk-backend.exe',
  )
}

// ── Backend startup ──────────────────────────────────────────────────────────

function spawnBackend(port) {
  return new Promise((resolve) => {
    const exePath = getBackendExePath()
    log(`Backend exe: ${exePath}`)

    if (!fs.existsSync(exePath)) {
      log(`ERROR: Backend exe not found at ${exePath}`)
      resolve(false)
      return
    }

    const env = { ...process.env, PORT: String(port), HOST: '127.0.0.1' }

    backendProcess = spawn(exePath, [], {
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
    })

    let resolved = false
    const resolveOnce = (val) => {
      if (!resolved) {
        resolved = true
        resolve(val)
      }
    }

    backendProcess.stdout.on('data', (chunk) => {
      const text = chunk.toString()
      text.split('\n').filter(Boolean).forEach((line) => {
        log(`[backend] ${line}`)
        // Backend prints "AGENTDESK_PORT:<port>" on stdout to signal readiness
        if (line.includes(`AGENTDESK_PORT:${port}`)) {
          resolveOnce(true)
        }
      })
    })

    backendProcess.stderr.on('data', (chunk) => {
      chunk.toString().split('\n').filter(Boolean).forEach((line) => {
        log(`[backend:err] ${line}`)
      })
    })

    backendProcess.on('error', (err) => {
      log(`Backend spawn error: ${err.message}`)
      resolveOnce(false)
    })

    backendProcess.on('exit', (code, signal) => {
      log(`Backend exited (code=${code}, signal=${signal})`)
      resolveOnce(false)
    })

    // Hard timeout so we never block forever
    setTimeout(() => {
      if (!resolved) {
        log('Backend startup timed out after ' + BACKEND_STARTUP_TIMEOUT_MS + 'ms')
        resolveOnce(false)
      }
    }, BACKEND_STARTUP_TIMEOUT_MS)
  })
}

// ── Health check ─────────────────────────────────────────────────────────────

async function waitForHealth(baseUrl) {
  for (let i = 0; i < HEALTH_CHECK_ATTEMPTS; i++) {
    try {
      const res = await fetch(`${baseUrl}/api/health`, {
        signal: AbortSignal.timeout(2000),
      })
      if (res.ok) {
        const data = await res.json()
        log(`Health OK: ${JSON.stringify(data)}`)
        return true
      }
    } catch {
      // Not ready yet; keep polling
    }
    await new Promise((r) => setTimeout(r, HEALTH_CHECK_INTERVAL_MS))
  }
  log('Health check failed after all attempts')
  return false
}

// ── Backend shutdown ─────────────────────────────────────────────────────────

function killBackend() {
  if (!backendProcess) return
  if (shuttingDownBackend) return
  shuttingDownBackend = true
  log('Shutting down backend...')
  try {
    // On Windows, SIGTERM isn't forwarded to child processes spawned without
    // shell=True; use taskkill to ensure the whole process tree is killed.
    const { execSync } = require('child_process')
    execSync(`taskkill /PID ${backendProcess.pid} /T /F`, { stdio: 'ignore' })
  } catch {
    try {
      backendProcess.kill()
    } catch {
      // Already dead
    }
  }
  backendProcess = null
  shuttingDownBackend = false
  log('Backend shut down.')
}

// ── Window creation ──────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'AgentDesk',
    backgroundColor: '#030712',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    mainWindow.loadURL(FRONTEND_DEV_URL)
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    // Frontend dist is placed in extraResources by electron-builder
    const indexPath = path.join(
      process.resourcesPath,
      'frontend',
      'dist',
      'index.html',
    )
    mainWindow.loadFile(indexPath)
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.once('ready-to-show', () => mainWindow.show())

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ── IPC handlers ─────────────────────────────────────────────────────────────

// Synchronous so preload can call sendSync before the page renders.
ipcMain.on('get-api-url', (event) => {
  event.returnValue = apiBaseUrl ?? `http://127.0.0.1:${DEFAULT_BACKEND_PORT}`
})

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  initStartupLog()
  log(`AgentDesk starting — isDev=${isDev}`)
  log(`AppData dir: ${getAppDataDir()}`)
  log(`Electron v${process.versions.electron}, Node v${process.versions.node}`)

  if (isDev) {
    // In dev mode the developer runs the backend manually.
    const devPort = parseInt(process.env.BACKEND_PORT || '8000', 10)
    apiBaseUrl = `http://127.0.0.1:${devPort}`
    log(`Dev mode: using existing backend at ${apiBaseUrl}`)
  } else {
    // --- Packaged mode: spawn backend, wait for health ---
    let port = DEFAULT_BACKEND_PORT
    try {
      port = await findFreePort(DEFAULT_BACKEND_PORT)
      log(`Selected port: ${port}`)
    } catch (err) {
      log(`Port selection error: ${err.message}`)
    }

    apiBaseUrl = `http://127.0.0.1:${port}`

    const spawned = await spawnBackend(port)
    if (spawned) {
      const healthy = await waitForHealth(apiBaseUrl)
      if (!healthy) {
        log('WARNING: Backend spawned but health check failed; continuing anyway')
      }
    } else {
      log('ERROR: Backend failed to start')
    }
  }

  log(`API base URL: ${apiBaseUrl}`)
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  killBackend()
  if (process.platform !== 'darwin') app.quit()
})

// Ensure backend is killed even on forced quit / Ctrl+C
app.on('will-quit', () => {
  killBackend()
})

app.commandLine.appendSwitch('disable-http-cache')
