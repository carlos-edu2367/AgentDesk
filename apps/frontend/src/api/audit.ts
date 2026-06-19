import { api } from './client'
import type { AuditLog, AuditLogFilters, PaginatedAuditLogs } from '../types/domain'

export const auditApi = {
  list: (filters?: AuditLogFilters) => api.get<PaginatedAuditLogs>('/api/audit', filters),
  get: (id: string) => api.get<AuditLog>(`/api/audit/${id}`),
  forExecution: (executionId: string) => api.get<AuditLog[]>(`/api/executions/${executionId}/audit`),
}
