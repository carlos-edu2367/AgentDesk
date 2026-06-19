import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StartupScreen } from '../components/StartupScreen'

// ── Helpers ──────────────────────────────────────────────────────────────────

function setElectronApi(apiBaseUrl: string | null) {
  if (apiBaseUrl === null) {
    delete (window as any).electronAPI
  } else {
    ;(window as any).electronAPI = { apiBaseUrl }
  }
}

afterEach(() => {
  delete (window as any).electronAPI
  vi.restoreAllMocks()
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('StartupScreen — outside Electron', () => {
  it('renders children immediately when electronAPI is absent', () => {
    setElectronApi(null)
    render(
      <StartupScreen>
        <div>App Content</div>
      </StartupScreen>,
    )
    expect(screen.getByText('App Content')).toBeInTheDocument()
    expect(screen.queryByText(/Starting AgentDesk/i)).not.toBeInTheDocument()
  })
})

describe('StartupScreen — inside Electron', () => {
  it('shows loading screen while checking backend', () => {
    setElectronApi('http://127.0.0.1:8765')
    // fetch never resolves during this test
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))

    render(
      <StartupScreen maxAttempts={3} intervalMs={50}>
        <div>App Content</div>
      </StartupScreen>,
    )

    expect(screen.getByText(/Starting AgentDesk backend/i)).toBeInTheDocument()
    expect(screen.queryByText('App Content')).not.toBeInTheDocument()
  })

  it('shows children when health check succeeds', async () => {
    setElectronApi('http://127.0.0.1:8765')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: 'ok', version: '0.1.0' }),
      } as Response),
    )

    render(
      <StartupScreen maxAttempts={5} intervalMs={10}>
        <div>App Content</div>
      </StartupScreen>,
    )

    await waitFor(() => {
      expect(screen.getByText('App Content')).toBeInTheDocument()
    })
    expect(screen.queryByText(/Starting AgentDesk/i)).not.toBeInTheDocument()
  })

  it('shows error screen after all attempts fail', async () => {
    setElectronApi('http://127.0.0.1:8765')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Connection refused')))

    render(
      <StartupScreen maxAttempts={2} intervalMs={10}>
        <div>App Content</div>
      </StartupScreen>,
    )

    await waitFor(
      () => {
        expect(screen.getByText(/backend failed to start/i)).toBeInTheDocument()
      },
      { timeout: 5000 },
    )
    expect(screen.queryByText('App Content')).not.toBeInTheDocument()
  })

  it('shows retry button on failure', async () => {
    setElectronApi('http://127.0.0.1:8765')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('refused')))

    render(
      <StartupScreen maxAttempts={1} intervalMs={10}>
        <div>App</div>
      </StartupScreen>,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
    })
  })

  it('shows log path hint on failure', async () => {
    setElectronApi('http://127.0.0.1:8765')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('refused')))

    render(
      <StartupScreen maxAttempts={1} intervalMs={10}>
        <div>App</div>
      </StartupScreen>,
    )

    await waitFor(() => {
      expect(screen.getByText(/startup\.log/i)).toBeInTheDocument()
    })
  })

  it('shows children if backend becomes healthy on second attempt', async () => {
    setElectronApi('http://127.0.0.1:8765')
    let calls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => {
        calls++
        if (calls < 2) return Promise.reject(new Error('not ready'))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: 'ok' }),
        } as Response)
      }),
    )

    render(
      <StartupScreen maxAttempts={5} intervalMs={10}>
        <div>App Ready</div>
      </StartupScreen>,
    )

    await waitFor(() => {
      expect(screen.getByText('App Ready')).toBeInTheDocument()
    })
  })
})

describe('StartupScreen — API URL used for health check', () => {
  it('calls the correct API URL from electronAPI', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'ok' }),
    } as Response)
    vi.stubGlobal('fetch', fetchMock)
    setElectronApi('http://127.0.0.1:9999')

    render(
      <StartupScreen maxAttempts={1} intervalMs={10}>
        <div>ok</div>
      </StartupScreen>,
    )

    await waitFor(() => expect(screen.getByText('ok')).toBeInTheDocument())

    const calledUrl = (fetchMock.mock.calls[0][0] as string)
    expect(calledUrl).toBe('http://127.0.0.1:9999/api/health')
  })
})
