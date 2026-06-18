import { api } from './client'
import type { Agent, AgentCreate, AgentUpdate } from '../types/domain'

export const agentsApi = {
  list: () => api.get<Agent[]>('/api/agents'),
  get: (id: string) => api.get<Agent>(`/api/agents/${id}`),
  create: (data: AgentCreate) => api.post<Agent>('/api/agents', data),
  update: (id: string, data: AgentUpdate) => api.put<Agent>(`/api/agents/${id}`, data),
  delete: (id: string) => api.delete<{ status: string }>(`/api/agents/${id}`),
}
