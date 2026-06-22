import type { ApprovalRequest } from '../types/domain'
import { api } from './client'

export const approvalsApi = {
  list: (status?: string): Promise<ApprovalRequest[]> =>
    api.get<ApprovalRequest[]>('/api/approvals', status ? { status } : undefined),

  get: (approvalId: string): Promise<ApprovalRequest> =>
    api.get<ApprovalRequest>(`/api/approvals/${approvalId}`),

  listForExecution: (executionId: string): Promise<ApprovalRequest[]> =>
    api.get<ApprovalRequest[]>(`/api/executions/${executionId}/approvals`),

  resolve: (
    executionId: string,
    approvalId: string,
    approved: boolean,
    reason?: string,
    approvalMode?: string,
  ): Promise<{ status: string }> =>
    api.post<{ status: string }>(`/api/executions/${executionId}/approvals/${approvalId}`, {
      approved,
      reason,
      approval_mode: approvalMode,
    }),
}
