export type ProviderType = 'ollama' | 'openrouter'

export type ExecutionStatus =
  | 'pending'
  | 'running'
  | 'waiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type ApprovalMode = 'manual' | 'auto'

export type EventType =
  | 'execution_created'
  | 'execution_started'
  | 'agent_started'
  | 'prompt_built'
  | 'model_request_started'
  | 'model_chunk'
  | 'model_completed'
  | 'agent_completed'
  | 'execution_completed'
  | 'execution_failed'
  | 'execution_cancelled'
  | 'tool_call_ignored'
  | 'message'
  | 'status'
  | 'tool_call'
  | 'tool_result'
  | 'approval_request'
  | 'approval_result'
  | 'memory_lookup'
  | 'memory_write'
  | 'subagent_call'
  | 'team_event'
  | 'error'

export interface ModelConfig {
  provider_id: string
  model: string
  temperature: number
  top_p: number
  context_window: number
  max_tokens: number
  stream: boolean
}

export interface MemoryConfig {
  use_global: boolean
  use_agent_memory: boolean
  use_team_memory: boolean
}

export interface Agent {
  id: string
  name: string
  description: string
  system_prompt: string
  model_config: ModelConfig
  capabilities: string[]
  explicit_tools: string[]
  blocked_tools: string[]
  skills: string[]
  plugins: string[]
  mcp_servers: string[]
  memory_config: MemoryConfig
  created_at: string
  updated_at: string
}

export interface AgentCreate {
  name: string
  description?: string
  system_prompt?: string
  model_config: ModelConfig
  capabilities?: string[]
  explicit_tools?: string[]
  blocked_tools?: string[]
  skills?: string[]
  plugins?: string[]
  mcp_servers?: string[]
}

export interface AgentUpdate {
  name?: string
  description?: string
  system_prompt?: string
  model_config?: ModelConfig
  capabilities?: string[]
}

export interface Provider {
  id: string
  type: ProviderType
  name: string
  base_url: string | null
  enabled: boolean
  config: Record<string, unknown>
}

export interface ProviderCreate {
  type: ProviderType
  name: string
  base_url?: string
  enabled?: boolean
  config?: Record<string, unknown>
}

export interface ProviderUpdate {
  type?: ProviderType
  name?: string
  base_url?: string
  enabled?: boolean
  config?: Record<string, unknown>
}

export interface ProviderHealth {
  healthy: boolean
  latency_ms?: number
  error?: string
}

export interface ModelInfo {
  id: string
  name: string
  context_length?: number
}

export interface WorkspacePermissions {
  read: boolean
  write: boolean
  delete: boolean
  execute: boolean
}

export interface Workspace {
  id: string
  name: string
  paths: string[]
  permissions: WorkspacePermissions
  created_at: string
  updated_at: string
}

export interface WorkspaceCreate {
  name: string
  paths?: string[]
  permissions?: Partial<WorkspacePermissions>
}

export interface WorkspaceUpdate {
  name?: string
  paths?: string[]
  permissions?: Partial<WorkspacePermissions>
}

export interface Execution {
  id: string
  type: 'agent' | 'team'
  target_id: string
  user_input: string
  status: ExecutionStatus
  approval_mode: ApprovalMode
  workspace_ids: string[]
  created_at: string
  updated_at: string
  completed_at: string | null
  result: string | null
  error: string | null
}

export interface ExecutionEvent {
  id: string
  execution_id: string
  type: EventType
  source: string
  source_id: string
  content: Record<string, unknown>
  created_at: string
}

export interface AgentExecutionRequest {
  agent_id: string
  message: string
  approval_mode?: ApprovalMode
  workspace_ids?: string[]
  stream?: boolean
}

export interface HealthResponse {
  status: string
}

export interface StorageInfo {
  appdata_path: string
  database_path: string
}
