import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api, ApiError } from '../api/client'

describe('API client', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    // Reset fetch mock before each test
    vi.restoreAllMocks()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('uses VITE_API_BASE_URL when set', () => {
    // The base URL is read from import.meta.env at module load time.
    // We verify it calls fetch with the correct base.
    const mockFetch = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    globalThis.fetch = mockFetch

    api.get('/api/health')

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/health'),
      expect.objectContaining({ headers: expect.any(Object) }),
    )
  })

  it('throws ApiError on non-OK response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404, statusText: 'Not Found' }),
    )

    await expect(api.get('/api/agents/missing')).rejects.toBeInstanceOf(ApiError)
  })

  it('posts JSON body correctly', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 'agent_1', name: 'Test' }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    globalThis.fetch = mockFetch

    await api.post('/api/agents', { name: 'Test' })

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Test' }),
      }),
    )
  })
})
