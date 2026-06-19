import { api } from './client'
import type { Skill, SkillCreate, SkillUpdate } from '../types/domain'

export const skillsApi = {
  list: () => api.get<Skill[]>('/api/skills'),
  get: (id: string) => api.get<Skill>(`/api/skills/${id}`),
  create: (data: SkillCreate) => api.post<Skill>('/api/skills', data),
  update: (id: string, data: SkillUpdate) => api.put<Skill>(`/api/skills/${id}`, data),
  delete: (id: string) => api.delete<{ status: string }>(`/api/skills/${id}`),
  importSkill: (skill: SkillCreate, overwrite = false) =>
    api.post<Skill>(`/api/skills/import${overwrite ? '?overwrite=true' : ''}`, { skill }),
  exportSkill: (id: string) => api.get<SkillCreate>(`/api/skills/${id}/export`),
}
