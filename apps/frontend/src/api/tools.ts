import { api } from './client'
import type { ToolDefinition, CapabilityInfo, AgentToolsConfig } from '../types/domain'

export const toolsApi = {
  list: () => api.get<ToolDefinition[]>('/api/tools'),
  listCapabilities: () => api.get<CapabilityInfo[]>('/api/tools/capabilities'),
  getAgentTools: (agentId: string) => api.get<AgentToolsConfig>(`/api/agents/${agentId}/tools`),
  updateAgentTools: (agentId: string, config: AgentToolsConfig) =>
    api.put<AgentToolsConfig>(`/api/agents/${agentId}/tools`, config),
  getAgentAvailableTools: (agentId: string) =>
    api.get<ToolDefinition[]>(`/api/agents/${agentId}/tools/available`),
}
