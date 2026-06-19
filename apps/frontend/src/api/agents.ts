import { api } from './client'
import type { Agent, AgentCreate, AgentUpdate, MCPServer, Plugin, Skill } from '../types/domain'

export const agentsApi = {
  list: () => api.get<Agent[]>('/api/agents'),
  get: (id: string) => api.get<Agent>(`/api/agents/${id}`),
  create: (data: AgentCreate) => api.post<Agent>('/api/agents', data),
  update: (id: string, data: AgentUpdate) => api.put<Agent>(`/api/agents/${id}`, data),
  delete: (id: string) => api.delete<{ status: string }>(`/api/agents/${id}`),
  getSkills: (id: string) => api.get<Skill[]>(`/api/agents/${id}/skills`),
  updateSkills: (id: string, skillIds: string[]) =>
    api.put<Skill[]>(`/api/agents/${id}/skills`, { skill_ids: skillIds }),
  getPlugins: (id: string) => api.get<Plugin[]>(`/api/agents/${id}/plugins`),
  updatePlugins: (id: string, pluginIds: string[]) =>
    api.put<Plugin[]>(`/api/agents/${id}/plugins`, { plugin_ids: pluginIds }),
  getMcpServers: (id: string) => api.get<MCPServer[]>(`/api/agents/${id}/mcp`),
  updateMcpServers: (id: string, serverIds: string[]) =>
    api.put<MCPServer[]>(`/api/agents/${id}/mcp`, { server_ids: serverIds }),
}
