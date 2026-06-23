import { api } from './client'
import type {
  Conversation,
  ConversationCreate,
  ConversationDetail,
  ConversationMessageRequest,
  ConversationUpdate,
} from '../types/domain'

export const conversationsApi = {
  list: (params?: { type?: string; target_id?: string; limit?: number }) =>
    api.get<Conversation[]>('/api/conversations', params),
  get: (id: string) => api.get<ConversationDetail>(`/api/conversations/${id}`),
  create: (data: ConversationCreate) =>
    api.post<Conversation>('/api/conversations', data),
  update: (id: string, data: ConversationUpdate) =>
    api.patch<Conversation>(`/api/conversations/${id}`, data),
  delete: (id: string) => api.delete<void>(`/api/conversations/${id}`),
  sendMessage: (id: string, data: ConversationMessageRequest) =>
    api.post<{ execution_id: string; conversation_id: string; status: string }>(
      `/api/conversations/${id}/messages`,
      data,
    ),
}
