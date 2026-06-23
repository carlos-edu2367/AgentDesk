import { api } from './client'
import { readNdjson } from '../lib/ndjson'

export interface HardwareInfo {
  ram_gb: number
  cpu_name: string
  cpu_cores: number
  gpu_name: string | null
  vram_gb: number | null
}

export interface ModelEntry {
  tag: string
  label: string
  params: string
  approx_size_gb: number
  min_budget_gb: number
  vision: boolean
  blurb: string
}

export interface Recommendations {
  hardware: HardwareInfo
  budget_gb: number
  tier: string
  tier_label: string
  models: ModelEntry[]
  fallback_models: ModelEntry[]
}

export interface OllamaStatus {
  installed: boolean
  running: boolean
  version: string | null
  models: string[]
}

export interface ProgressEvent {
  phase: string
  percent?: number | null
  message?: string
  completed?: number
  total?: number
  manual_url?: string
  winget?: string
}

export const ollamaApi = {
  status: () => api.get<OllamaStatus>('/api/ollama/status'),
  recommendations: () => api.get<Recommendations>('/api/ollama/recommendations'),

  async *install(): AsyncGenerator<ProgressEvent> {
    const res = await fetch(`${api.getBaseUrl()}/api/ollama/install`, { method: 'POST' })
    yield* readNdjson<ProgressEvent>(res)
  },

  async *pull(model: string): AsyncGenerator<ProgressEvent> {
    const res = await fetch(`${api.getBaseUrl()}/api/ollama/pull`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    })
    yield* readNdjson<ProgressEvent>(res)
  },
}
