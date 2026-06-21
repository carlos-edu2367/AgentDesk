import { api } from './client'
import type {
  Conversation,
  ConversationCreate,
  ConversationDetail,
  ConversationMessageRequest,
} from '../types/domain'

export const conversationsApi = {
  list: (params?: { type?: string; target_id?: string }) =>
    api.get<Conversation[]>('/api/conversations', params),
  get: (id: string) => api.get<ConversationDetail>(`/api/conversations/${id}`),
  create: (data: ConversationCreate) =>
    api.post<Conversation>('/api/conversations', data),
  sendMessage: (id: string, data: ConversationMessageRequest) =>
    api.post<{ execution_id: string; conversation_id: string; status: string }>(
      `/api/conversations/${id}/messages`,
      data,
    ),
}
