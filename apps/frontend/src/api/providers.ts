import { api } from './client'
import type { Provider, ProviderCreate, ProviderUpdate, ProviderHealth, ModelInfo } from '../types/domain'

export const providersApi = {
  list: () => api.get<Provider[]>('/api/providers'),
  get: (id: string) => api.get<Provider>(`/api/providers/${id}`),
  create: (data: ProviderCreate) => api.post<Provider>('/api/providers', data),
  update: (id: string, data: ProviderUpdate) => api.put<Provider>(`/api/providers/${id}`, data),
  delete: (id: string) => api.delete<{ status: string }>(`/api/providers/${id}`),
  health: (id: string) => api.post<ProviderHealth>(`/api/providers/${id}/health`, {}),
  models: (id: string) => api.get<ModelInfo[]>(`/api/providers/${id}/models`),
}
