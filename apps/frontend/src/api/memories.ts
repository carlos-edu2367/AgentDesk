import { api } from './client'
import type {
  Memory,
  MemoryCreate,
  MemoryUpdate,
  MemorySearchRequest,
  MemorySearchResponse,
  MemoryLinkCreate,
} from '../types/domain'

type MemoryLink = {
  id: string
  source_memory_id: string
  target_memory_id: string
  relation_type: string
  strength: number
}

export const memoriesApi = {
  list: (params?: { scope?: string; scope_id?: string; type?: string }) => {
    const qs = new URLSearchParams()
    if (params?.scope) qs.set('scope', params.scope)
    if (params?.scope_id) qs.set('scope_id', params.scope_id)
    if (params?.type) qs.set('type', params.type)
    const query = qs.toString()
    return api.get<Memory[]>(`/api/memories${query ? `?${query}` : ''}`)
  },

  get: (id: string) =>
    api.get<Memory>(`/api/memories/${id}`),

  create: (data: MemoryCreate) =>
    api.post<Memory>('/api/memories', data),

  update: (id: string, data: MemoryUpdate) =>
    api.put<Memory>(`/api/memories/${id}`, data),

  delete: (id: string) =>
    api.delete<{ status: string }>(`/api/memories/${id}`),

  search: (request: MemorySearchRequest) =>
    api.post<MemorySearchResponse>('/api/memories/search', request),

  reembed: (params?: { scope?: string; scope_id?: string }) => {
    const qs = new URLSearchParams()
    if (params?.scope) qs.set('scope', params.scope)
    if (params?.scope_id) qs.set('scope_id', params.scope_id)
    const query = qs.toString()
    return api.post<{ processed: number; succeeded: number; failed: number }>(
      `/api/memories/reembed${query ? `?${query}` : ''}`,
      {},
    )
  },

  createLink: (memoryId: string, link: MemoryLinkCreate) =>
    api.post<{ id: string }>(`/api/memories/${memoryId}/links`, link),

  getLinks: (memoryId: string) =>
    api.get<MemoryLink[]>(`/api/memories/${memoryId}/links`),
}
