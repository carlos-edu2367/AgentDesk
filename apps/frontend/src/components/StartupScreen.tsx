import { useEffect, useState } from 'react'
import { Logo } from './Logo'

type BackendStatus = 'checking' | 'ready' | 'failed'

interface StartupScreenProps {
  children: React.ReactNode
  /** Override polling params — useful for tests. */
  maxAttempts?: number
  intervalMs?: number
}

function getElectronApiUrl(): string | null {
  if (typeof window === 'undefined') return null
  const api = (window as Window & { electronAPI?: { apiBaseUrl?: string } }).electronAPI
  return api?.apiBaseUrl ?? null
}

export function StartupScreen({
  children,
  maxAttempts = 30,
  intervalMs = 1000,
}: StartupScreenProps) {
  const apiUrl = getElectronApiUrl()
  // Only show startup screen when running inside Electron (preload sets apiBaseUrl)
  const isElectron = apiUrl !== null

  const [status, setStatus] = useState<BackendStatus>(isElectron ? 'checking' : 'ready')
  const [errorMsg, setErrorMsg] = useState('')
  const logPath = '%APPDATA%\\AgentDesk\\logs\\app\\startup.log'

  useEffect(() => {
    if (!isElectron || !apiUrl) return

    let cancelled = false

    async function pollHealth() {
      for (let i = 0; i < maxAttempts; i++) {
        if (cancelled) return
        try {
          const res = await fetch(`${apiUrl}/api/health`, {
            signal: AbortSignal.timeout(2000),
          })
          if (res.ok) {
            if (!cancelled) setStatus('ready')
            return
          }
        } catch {
          // Backend not ready yet
        }
        await new Promise((r) => setTimeout(r, intervalMs))
      }
      if (!cancelled) {
        setStatus('failed')
        setErrorMsg(`The local API at ${apiUrl} did not respond. Check the startup log and retry.`)
      }
    }

    pollHealth()
    return () => {
      cancelled = true
    }
  }, [isElectron, apiUrl, maxAttempts, intervalMs])

  if (status === 'ready') {
    return <>{children}</>
  }

  if (status === 'checking') {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center gap-6 bg-gray-950 text-gray-100">
        <Logo className="h-12 w-12" />
        <div className="text-2xl font-bold tracking-tight">AgentDesk</div>
        <div className="flex flex-col items-center gap-1 text-sm text-gray-400">
          <p>Starting AgentDesk backend…</p>
          <p>Checking local storage…</p>
          <p>Connecting to local API…</p>
        </div>
        <div className="mt-2 h-1 w-48 overflow-hidden rounded-full bg-gray-800">
          <div className="h-full animate-pulse rounded-full bg-blue-500" />
        </div>
      </div>
    )
  }

  // status === 'failed'
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center gap-4 bg-gray-950 px-8 text-gray-100">
      <div className="text-xl font-bold text-red-400">AgentDesk backend failed to start</div>
      <p className="max-w-sm text-center text-sm text-gray-400">
        {errorMsg || 'The local API could not be reached. Please check the startup logs.'}
      </p>
      <p className="text-xs text-gray-600">
        Logs: {logPath}
      </p>
      <button
        onClick={() => window.location.reload()}
        className="mt-2 rounded bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
      >
        Retry
      </button>
    </div>
  )
}
