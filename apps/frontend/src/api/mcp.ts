import { api } from './client'
import type { MCPServer, MCPServerCreate, MCPServerUpdate, MCPTestResponse, MCPToolInfo } from '../types/domain'

export const mcpApi = {
  list: () => api.get<MCPServer[]>('/api/mcp'),
  get: (id: string) => api.get<MCPServer>(`/api/mcp/${id}`),
  create: (data: MCPServerCreate) => api.post<MCPServer>('/api/mcp', data),
  update: (id: string, data: MCPServerUpdate) => api.put<MCPServer>(`/api/mcp/${id}`, data),
  delete: (id: string) => api.delete<{ status: string }>(`/api/mcp/${id}`),
  enable: (id: string) => api.post<MCPServer>(`/api/mcp/${id}/enable`, {}),
  disable: (id: string) => api.post<MCPServer>(`/api/mcp/${id}/disable`, {}),
  test: (id: string) => api.post<MCPTestResponse>(`/api/mcp/${id}/test`, {}),
  tools: (id: string) => api.get<MCPToolInfo[]>(`/api/mcp/${id}/tools`),
}
