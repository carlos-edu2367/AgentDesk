import { api, ApiError } from './client'
import type { Execution, AgentExecutionRequest } from '../types/domain'

export const executionsApi = {
  list: () => api.get<Execution[]>('/api/executions'),
  get: (id: string) => api.get<Execution>(`/api/executions/${id}`),
  runAgent: (data: AgentExecutionRequest) =>
    api.post<{ execution_id: string; status: string }>('/api/executions/agent', data),
  cancel: (id: string) =>
    api.post<{ status: string }>(`/api/executions/${id}/cancel`, {}),
}

export { ApiError }
