import { api, ApiError } from './client'
import type {
  Execution,
  AgentExecutionRequest,
  TeamExecutionRequest,
  ExecutionFilters,
  ExecutionDetailResponse,
  ExecutionExportResponse,
} from '../types/domain'

export const executionsApi = {
  list: (filters?: ExecutionFilters) => api.get<Execution[]>('/api/executions', filters),
  get: (id: string) => api.get<Execution>(`/api/executions/${id}`),
  detail: (id: string) => api.get<ExecutionDetailResponse>(`/api/executions/${id}/detail`),
  export: (id: string, format: 'json' | 'markdown') =>
    api.post<ExecutionExportResponse>(`/api/executions/${id}/export`, { format }),
  runAgent: (data: AgentExecutionRequest) =>
    api.post<{ execution_id: string; status: string }>('/api/executions/agent', data),
  runTeam: (data: TeamExecutionRequest) =>
    api.post<{ execution_id: string; status: string }>('/api/executions/team', data),
  cancel: (id: string) =>
    api.post<{ status: string }>(`/api/executions/${id}/cancel`, {}),
}

export { ApiError }
