// Resolve the API base URL at module load time.
// Priority: Electron preload (packaged app) > VITE_API_BASE_URL (dev env var) > default
function resolveBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const electronApi = (window as Window & { electronAPI?: { apiBaseUrl?: string } }).electronAPI
    if (electronApi?.apiBaseUrl) return electronApi.apiBaseUrl
  }
  return (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'
}

const BASE_URL = resolveBaseUrl()

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })

  if (!res.ok) {
    let detail: unknown
    try {
      detail = await res.json()
    } catch {
      detail = await res.text()
    }
    throw new ApiError(res.status, `HTTP ${res.status}: ${res.statusText}`, detail)
  }

  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return undefined as T
  }

  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string, params?: object) => {
    const query = params
      ? new URLSearchParams(
          Object.entries(params as Record<string, unknown>)
            .filter(([, value]) => value !== undefined && value !== null && value !== '')
            .map(([key, value]) => [key, String(value)]),
        ).toString()
      : ''
    return request<T>(query ? `${path}?${query}` : path)
  },
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  getBaseUrl: () => BASE_URL,
}
