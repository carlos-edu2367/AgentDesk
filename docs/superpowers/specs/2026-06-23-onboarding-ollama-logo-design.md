# AgentDesk — First-run onboarding, Ollama setup, hardware-based model recommendation, new logo

Date: 2026-06-23
Branch base: `feat/computer-use`
Status: approved design → implementation plan pending

## 1. Goal

Improve the AgentDesk first-run experience and refresh the brand:

1. On first use, present a **non-mandatory** onboarding wizard that explains that the
   app needs **at least one** model provider — either **Ollama** (local, free, private)
   or **OpenRouter** (cloud, API key, paid) — and lets the user set one up without
   leaving the app.
2. Offer to **install Ollama** from inside the app, with live progress.
3. After Ollama is confirmed installed, **analyze the user's hardware** and present a
   **ranked list** of Ollama models that fit, with one-click install (`ollama pull`)
   and live progress.
4. Replace the placeholder text branding with a real **logo** (Orbit/leader node motif)
   wired through the UI and used as the Windows app icon.
5. Produce a fresh **`AgentDesk-Portable-0.1.0.exe`** containing all of the above.

Non-goals (YAGNI): auto-update, bundling the Ollama installer inside the app
(~700 MB; downloaded at runtime instead), macOS/Linux install flows, model
benchmarking, GPU driver installation.

## 2. Key constraints discovered

- **Windows Ollama install is NOT `irm install.ps1 | iex`** (that is the Linux/macOS
  pattern). On Windows the supported paths are the **`OllamaSetup.exe`** installer
  (silent, per-user, no admin) or **`winget install Ollama.Ollama`**. The app downloads
  and runs the installer, with winget as a fallback. (Refs: docs.ollama.com/windows,
  winget `Ollama.Ollama`.)
- The Electron main process (`apps/desktop/main.js`) only exposes `apiBaseUrl` to the
  renderer and spawns the FastAPI backend. System operations therefore live in the
  **backend** (Python), which already has streaming responses and pytest coverage.
  Packaged backend is a PyInstaller exe and can spawn `powershell`/the installer in the
  user context.
- There is **no onboarding/first-run flow today**: `StartupScreen` → `RootRedirect`
  → `/agents`. Providers are created via `Config > Providers` (`ProviderForm`).
- There is **no logo or app icon**: Sidebar/StartupScreen render the text "AgentDesk";
  electron-builder has no `win.icon` (ships the default Electron icon); `index.html`
  has no favicon.
- Packaging is one step: `scripts/build-windows.ps1` → `dist/electron/AgentDesk-Portable-0.1.0.exe`.

## 3. Decisions (locked)

- Model recommendation: **ranked list, user picks** (tiers matched to hardware).
- Wizard covers **both** Ollama and OpenRouter paths; either one produces a working
  provider before exit.
- Logo: **Orbit / leader** node motif (central node + orbiting satellites + ring),
  blue/cyan on dark slate, matching the existing UI theme.
- Install/pull failures: **graceful fallback** — show the error, offer Retry, plus a
  manual download link and the winget command; never block the app; user can switch to
  OpenRouter or skip.

## 4. Backend design

New package `backend/app/setup/` plus routers registered in `app/main.py`.

### 4.1 `hardware.py`
`detect() -> HardwareInfo` where `HardwareInfo = { ram_gb: float, cpu_name: str,
cpu_cores: int, gpu_name: str | None, vram_gb: float | None }`.

Detection (Windows-first, degrade gracefully — never raise to the caller):
- RAM: `psutil.virtual_memory().total`.
- CPU: `platform.processor()` / `os.cpu_count()`.
- GPU/VRAM fallback chain:
  1. `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits` (accurate).
  2. Windows registry `HardwareInformation.qwMemorySize` under the display class key
     (true VRAM for >4 GB cards).
  3. `Get-CimInstance Win32_VideoController` for the GPU **name** only (AdapterRAM is a
     uint32 capped at 4 GB and unreliable).
  - On failure, `gpu_name=None, vram_gb=None`; recommendations use RAM alone.

### 4.2 `catalog.py`
Curated static catalog. `recommend(hw: HardwareInfo) -> Recommendations` computes a
memory budget `budget = max(vram_gb or 0, ram_gb * 0.6)` and returns the matching tier
plus the next lighter tier as fallbacks. Each model entry:
`{ tag, label, params, approx_size_gb, min_budget_gb, vision: bool, blurb }`, with
`min_budget_gb ≈ approx_size_gb * 1.25` (download size + context overhead).

Tiers use the **current** Ollama-library tags and real download sizes verified
2026-06-23 (Gemma 4, released 2026-03-31, and Qwen 3.5; both multimodal, Apache-2.0).
"E" sizes are Gemma's effective-parameter edge variants; `-it-qat` is the smallest
quality-preserving Gemma quant.

| Budget GB | Tier | Models (tag — size) |
|---|---|---|
| < 4 | Light | `qwen3.5:0.8b` (1.0) · `qwen3.5:2b` (2.7) |
| 4–8 | Balanced-light | `qwen3.5:4b` (3.4) · `gemma4:e2b-it-qat` (4.3) · `qwen3.5:9b` (6.6) |
| 8–16 | Balanced | `gemma4:12b` (7.6) · `gemma4:e4b` (9.6) · `qwen3.5:9b` (6.6) |
| 16–32 | Strong | `qwen3.5:27b` (17) · `gemma4:26b` (18) |
| ≥ 32 | Max | `gemma4:31b` (20) · `qwen3.5:35b` (24) |

`gemma4:122b`/`qwen3.5:122b`-class models are intentionally excluded (out of scope for
consumer hardware). The catalog is a plain data module so tags/sizes can be adjusted
without touching logic. `recommend()` is pure and unit-tested against fixed
`HardwareInfo` inputs. Gemma 4 entries are `vision: true`; the Ollama provider's
`_VISION_FAMILIES` list (`backend/app/providers/ollama.py`) gains `gemma4` and
`qwen3.5` so vision capability is reported correctly.

### 4.3 `ollama_manager.py`
- `status() -> { installed, running, version, models: [str] }`.
  - `installed`: `ollama` on PATH or `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` exists.
  - `running`: reuse existing `OllamaProvider.health_check()` against `localhost:11434`.
- `install()` async generator yielding progress events
  `{ phase, percent?, message }` (`download` → `installing` → `starting` → `done` |
  `error`):
  1. If already installed+running, emit `done` immediately.
  2. Download `https://ollama.com/download/OllamaSetup.exe` to AppData `temp/`,
     streaming byte progress.
  3. Run the installer silently (`Start-Process -Wait`; Inno Setup `/VERYSILENT`
     where applicable).
  4. Poll `localhost:11434` until healthy (bounded timeout).
  5. On any failure, emit `error` with a message; the manager exposes the manual
     download URL and winget command for the UI fallback.
- `pull(model)` async generator proxying Ollama's native `POST /api/pull` streaming
  JSON, normalized to `{ phase, percent, completed, total, message }`.

### 4.4 Routers
New `app/api/routers/onboarding.py` and `app/api/routers/ollama.py`
(+ `system` hardware endpoint), included in `app/main.py`:

- `GET  /api/onboarding/state` → `{ completed: bool, has_providers: bool }`
- `POST /api/onboarding/complete`
- `GET  /api/system/hardware` → `HardwareInfo`
- `GET  /api/ollama/status` → status
- `POST /api/ollama/install` → `StreamingResponse` (ndjson) of install progress
- `GET  /api/ollama/recommendations` → `{ hardware, tier, models[], fallback_models[] }`
- `POST /api/ollama/pull` `{ model }` → `StreamingResponse` (ndjson) of pull progress
- After a successful pull or OpenRouter key submission, the **provider record is
  auto-created** (reuse `provider_repo`): Ollama → `type=ollama,
  base_url=http://localhost:11434`; OpenRouter → `type=openrouter` with the key.
  Streaming endpoints emit a final `provider_created` event with the id.

### 4.5 Onboarding state persistence
A small key/value setting persisted in the existing SQLite DB (new
`app_settings(key TEXT PK, value TEXT)` table via an Alembic migration) storing
`onboarding_completed`. `has_providers` is derived from `provider_repo` count.
The streaming follows the existing ndjson `StreamingResponse` convention used by
`provider_chat`; no new event-bus wiring required.

### 4.6 Dependencies
- Add `psutil` to `backend/requirements.txt` (cross-platform, PyInstaller-friendly).
- No new frontend runtime deps; `sharp` + `png-to-ico` added as **desktop devDeps**
  for icon rasterization only.

## 5. Frontend design

`apps/frontend/src/components/onboarding/OnboardingWizard.tsx` plus a small
`api/onboarding.ts` + `api/ollama.ts`.

### 5.1 Gating
Rendered as a full-screen overlay from `App` (inside `StartupScreen`, outside the
router) when:
`state.completed === false` **and** `state.has_providers === false` **and** not running
under Vitest/dev-mock **and** localStorage `agentdesk.onboardingSkipped` is unset.
"Skip for now" sets the localStorage flag (so it does not nag every launch); "Done"
calls `POST /onboarding/complete`. Re-openable later via a Config entry.

### 5.2 Steps
1. **Welcome** — two side-by-side cards: Ollama (local · free · private · uses your
   RAM/GPU) vs OpenRouter (cloud · API key · paid · nothing to install). Copy: "You
   need at least one to run agents."
2. **Choose path** — `Set up Ollama` · `Use OpenRouter` · `Skip for now`.
3a. **Ollama**
   - Call `GET /ollama/status`. If not installed → `Install Ollama` button streaming
     `POST /ollama/install` into a progress bar + phase label. On error → inline error
     with Retry, a "Download Ollama manually" link (`https://ollama.com/download/windows`)
     and the `winget install Ollama.Ollama` command to copy.
   - Once running → **hardware card** from `GET /system/hardware` (RAM, CPU, GPU) and a
     **ranked model list** from `GET /ollama/recommendations`. Best-fit tier shown first;
     each row shows label, params, approx size, and a fit note. User selects one →
     `POST /ollama/pull` streamed into a progress bar. On success the provider is created.
3b. **OpenRouter** — API key input (masked) → submit → backend creates the provider and
    runs a health check; show success/error inline.
4. **Done** — confirmation → close overlay → existing `RootRedirect` lands the user in
   chat.

### 5.3 Components
- `OnboardingWizard.tsx` (step state machine)
- `WelcomeStep`, `OllamaStep`, `OpenRouterStep`, `DoneStep`
- `ProgressStream` helper that reads an ndjson `StreamingResponse` via `fetch` +
  `ReadableStream` and surfaces `{ phase, percent, message }` to the UI.
- Reuse existing `client.ts` base-URL resolution.

## 6. Logo design

Concept: **Orbit / leader** — a central filled node, three orbiting satellite nodes
connected by spokes, enclosed by a thin orbit ring. Palette: `#3b82f6` (center),
`#38bdf8` (satellites), `#1e3a5f` ring, on `#0f172a` rounded-square tile — consistent
with the slate/blue UI.

Deliverables:
- `apps/frontend/src/assets/logo.svg` (icon) and a `Logo.tsx` React component (icon +
  optional "AgentDesk" wordmark) used in `Sidebar`, `StartupScreen`, and the wizard.
- `apps/frontend/public/favicon.svg` referenced from `index.html`.
- `apps/desktop/build/icon.ico` (256×256, multi-size) generated by
  `apps/desktop/scripts/make-icon.mjs` (`sharp` rasterizes the SVG to PNG → `png-to-ico`).
  electron-builder auto-detects `build/icon.ico`; also set `win.icon` explicitly.

## 7. Packaging

- Add `"icon": "build/icon.ico"` under `build.win` (and rely on `buildResources: build`).
- Generate the icon, then run `scripts/build-windows.ps1` to produce
  `dist/electron/AgentDesk-Portable-0.1.0.exe` (and the NSIS installer) carrying the new
  icon and features. Version stays `0.1.0`.

## 8. Testing

Backend (pytest, real install/pull always mocked):
- `catalog.recommend()` — tier selection across RAM/VRAM fixtures incl. no-GPU.
- `hardware.detect()` — mocked `nvidia-smi`/registry/CIM outputs and the failure path.
- `ollama_manager.status()` — installed/running permutations (mock PATH + health).
- `install()` / `pull()` generators — mocked download + subprocess + httpx stream.
- Routers — state, complete, hardware, status, recommendations; streaming endpoints with
  mocked managers; provider auto-creation asserts a `provider_repo` row.

Frontend (Vitest + RTL):
- Gating logic (completed / has_providers / skipped / dev permutations).
- Wizard renders each step; path selection; ranked model list renders from a mocked
  recommendations payload; `ProgressStream` parses a mocked ndjson stream; OpenRouter
  key submission calls the API.
- `Logo` renders in Sidebar/StartupScreen.

Packaging smoke (manual): launch the produced portable exe, confirm the new icon, the
wizard appears on a clean AppData, and skipping/finishing both reach chat.

## 9. Implementation phases (for the plan)

1. Backend: `setup/` package (`hardware`, `catalog`, `ollama_manager`), `app_settings`
   migration, routers, provider auto-creation, tests.
2. Frontend: `api/onboarding.ts` + `api/ollama.ts`, `OnboardingWizard` + steps +
   `ProgressStream`, gating in `App`, Config re-open entry, tests.
3. Logo: `logo.svg`, `Logo.tsx`, favicon, `make-icon.mjs` → `icon.ico`, wire into UI.
4. Packaging: electron-builder `win.icon`, run `build-windows.ps1`, verify the portable
   exe.

## 10. Risks / open points

- Silent-install flags for `OllamaSetup.exe` can change between releases; the winget +
  manual-download fallback covers regressions.
- VRAM detection is best-effort on non-NVIDIA GPUs; recommendation gracefully falls back
  to RAM, so a wrong/missing VRAM read never breaks the flow.
- Downloaded-exe execution may trip SmartScreen/antivirus; the manual link is the escape
  hatch and should be documented in the wizard copy.
