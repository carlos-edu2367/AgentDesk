<#
.SYNOPSIS
    Builds the full AgentDesk Windows desktop package in one step.

.DESCRIPTION
    Runs every stage required to produce the distributable Windows artifacts:
      1. Frontend production bundle  (apps/frontend/dist)
      2. Backend executable          (backend/dist/agentdesk-backend, via PyInstaller)
      3. Electron portable + NSIS installer  (dist/electron)

    The Electron app bundles the backend exe and the frontend bundle as
    extraResources, so the produced installers are fully self-contained:
    launching AgentDesk spawns the local backend and loads the frontend UI.

    Build outputs live under dist/ and backend/dist|build/ — all gitignored.

.PARAMETER SkipFrontend
    Skip the frontend (Vite) build. Use when apps/frontend/dist is current.

.PARAMETER SkipBackend
    Skip the backend (PyInstaller) build. Use when backend/dist is current.

.PARAMETER InstallDeps
    Run dependency installation (pip install -r, npm install) before building.

.EXAMPLE
    pwsh scripts/build-windows.ps1

.EXAMPLE
    pwsh scripts/build-windows.ps1 -InstallDeps
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [switch]$InstallDeps
)

$ErrorActionPreference = 'Stop'

# ── Paths ──────────────────────────────────────────────────────────────────
$RepoRoot    = Split-Path -Parent $PSScriptRoot
$BackendDir  = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'apps\frontend'
$DesktopDir  = Join-Path $RepoRoot 'apps\desktop'
$VenvPython  = Join-Path $BackendDir 'venv\Scripts\python.exe'
$OutputDir   = Join-Path $RepoRoot 'dist\electron'

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ── Prerequisites ────────────────────────────────────────────────────────────
Write-Step 'Checking prerequisites'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'node was not found on PATH. Install Node.js 18+ and retry.'
}
if (-not (Test-Path $VenvPython)) {
    throw "Backend venv not found at $VenvPython. Create it first: `n  python -m venv backend\venv; backend\venv\Scripts\python -m pip install -r backend\requirements.txt"
}
Write-Host "node $(node -v)"
Write-Host "python $(& $VenvPython --version)"

# ── 1. Frontend ──────────────────────────────────────────────────────────────
if (-not $SkipFrontend) {
    Write-Step 'Building frontend (Vite)'
    Push-Location $FrontendDir
    try {
        if ($InstallDeps) { npm install }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
} else { Write-Host "`n(skipping frontend build)" }

# ── 2. Backend executable ──────────────────────────────────────────────────────
if (-not $SkipBackend) {
    Write-Step 'Building backend executable (PyInstaller)'
    Push-Location $BackendDir
    try {
        if ($InstallDeps) {
            & $VenvPython -m pip install -r requirements.txt
            & $VenvPython -m pip install pyinstaller
        }
        # Ensure PyInstaller is available even without -InstallDeps.
        & $VenvPython -c "import PyInstaller" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'PyInstaller missing; installing...'
            & $VenvPython -m pip install pyinstaller
        }
        Remove-Item -Recurse -Force (Join-Path $BackendDir 'build'),(Join-Path $BackendDir 'dist\agentdesk-backend') -ErrorAction SilentlyContinue
        & $VenvPython -m PyInstaller --noconfirm pyinstaller\agentdesk-backend.spec
        if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    } finally { Pop-Location }
} else { Write-Host "`n(skipping backend build)" }

# ── 3. Electron artifacts ──────────────────────────────────────────────────────
Write-Step 'Building Electron artifacts (portable + installer)'
Push-Location $DesktopDir
try {
    if ($InstallDeps) { npm install }
    # Disable code-signing auto-discovery; this MVP ships unsigned.
    $env:CSC_IDENTITY_AUTO_DISCOVERY = 'false'
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'electron-builder failed.' }
} finally { Pop-Location }

# ── Summary ────────────────────────────────────────────────────────────────────
Write-Step 'Build complete'
Write-Host "Artifacts in: $OutputDir" -ForegroundColor Green
Get-ChildItem $OutputDir -File | Where-Object { $_.Extension -eq '.exe' } |
    ForEach-Object { Write-Host ("  {0,-32} {1,8:N1} MB" -f $_.Name, ($_.Length / 1MB)) }
