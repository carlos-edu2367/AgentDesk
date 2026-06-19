import { api } from './client'
import type { Plugin, PluginImportResponse, PluginToolManifest, Skill } from '../types/domain'

export const pluginsApi = {
  list: () => api.get<Plugin[]>('/api/plugins'),
  get: (id: string) => api.get<Plugin>(`/api/plugins/${id}`),
  importPlugin: (path: string) => api.post<PluginImportResponse>('/api/plugins/import', { path }),
  enable: (id: string) => api.post<Plugin>(`/api/plugins/${id}/enable`, {}),
  disable: (id: string) => api.post<Plugin>(`/api/plugins/${id}/disable`, {}),
  delete: (id: string) => api.delete<{ status: string }>(`/api/plugins/${id}`),
  tools: (id: string) => api.get<PluginToolManifest[]>(`/api/plugins/${id}/tools`),
  skills: (id: string) => api.get<Skill[]>(`/api/plugins/${id}/skills`),
}
