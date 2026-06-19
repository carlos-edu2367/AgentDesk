import { api } from './client'
import type { MCPServer, Skill, Team, TeamCreate, TeamUpdate } from '../types/domain'

export const teamsApi = {
  list: () => api.get<Team[]>('/api/teams'),
  get: (id: string) => api.get<Team>(`/api/teams/${id}`),
  create: (data: TeamCreate) => api.post<Team>('/api/teams', data),
  update: (id: string, data: TeamUpdate) => api.put<Team>(`/api/teams/${id}`, data),
  delete: (id: string) => api.delete<{ status: string }>(`/api/teams/${id}`),
  getSkills: (id: string) => api.get<Skill[]>(`/api/teams/${id}/skills`),
  updateSkills: (id: string, skillIds: string[]) =>
    api.put<Skill[]>(`/api/teams/${id}/skills`, { skill_ids: skillIds }),
  getMcp: (id: string) => api.get<MCPServer[]>(`/api/teams/${id}/mcp`),
  updateMcp: (id: string, serverIds: string[]) =>
    api.put<MCPServer[]>(`/api/teams/${id}/mcp`, { server_ids: serverIds }),
}
