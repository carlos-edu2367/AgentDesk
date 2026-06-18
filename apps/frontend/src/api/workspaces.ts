import { api } from './client'
import type { Workspace, WorkspaceCreate, WorkspaceUpdate } from '../types/domain'

export const workspacesApi = {
  list: () => api.get<Workspace[]>('/api/workspaces'),
  get: (id: string) => api.get<Workspace>(`/api/workspaces/${id}`),
  create: (data: WorkspaceCreate) => api.post<Workspace>('/api/workspaces', data),
  update: (id: string, data: WorkspaceUpdate) => api.put<Workspace>(`/api/workspaces/${id}`, data),
  delete: (id: string) => api.delete<{ status: string }>(`/api/workspaces/${id}`),
}
