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
  | 'execution_waiting_approval'
  | 'execution_resumed'
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
  | 'tool_call_requested'
  | 'tool_call_validated'
  | 'tool_call_denied'
  | 'tool_executed'
  | 'tool_result'
  | 'tool_failed'
  | 'approval_requested'
  | 'approval_approved'
  | 'approval_rejected'
  | 'approval_auto_granted'
  | 'terminal_started'
  | 'terminal_completed'
  | 'terminal_failed'
  | 'terminal_timeout'
  | 'message'
  | 'status'
  | 'tool_call'
  | 'approval_request'
  | 'approval_result'
  | 'memory_lookup'
  | 'memory_write'
  | 'memory_lookup_result'
  | 'memory_created'
  | 'memory_updated'
  | 'memory_deleted'
  | 'memory_embedding_generated'
  | 'memory_embedding_failed'
  | 'memory_usage_recorded'
  | 'subagent_call'
  | 'team_event'
  | 'error'

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired'

export interface ApprovalRequest {
  id: string
  execution_id: string
  agent_id: string
  tool: string
  status: ApprovalStatus
  risk_level: string
  summary: string
  arguments: Record<string, unknown>
  rejection_reason: string | null
  created_at: string
  resolved_at: string | null
}

export interface ToolDefinition {
  name: string
  description: string
  source: string
  capability: string
  critical: boolean
  input_schema: Record<string, unknown>
}

export interface CapabilityInfo {
  name: string
  tools: string[]
}

export interface AgentToolsConfig {
  capabilities: string[]
  explicit_tools: string[]
  blocked_tools: string[]
}

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

export type MemoryScope = 'global' | 'agent' | 'team' | 'workspace'
export type MemoryType =
  | 'profile' | 'preference' | 'project' | 'file_reference'
  | 'task_history' | 'decision' | 'lesson' | 'error_pattern'
  | 'workflow' | 'system_note'

export interface Memory {
  id: string
  scope: MemoryScope
  scope_id: string | null
  type: MemoryType
  title: string
  content: string
  tags: string[]
  confidence: number
  importance: number
  source: Record<string, unknown>
  created_at: string
  updated_at: string
  last_used_at: string | null
  usage_count: number
  deleted_at: string | null
  embedding_status: 'pending' | 'done' | 'failed'
}

export interface MemoryCreate {
  scope: MemoryScope
  scope_id?: string | null
  type: MemoryType
  title: string
  content: string
  tags?: string[]
  confidence?: number
  importance?: number
  source?: Record<string, unknown>
}

export interface MemoryUpdate {
  title?: string
  content?: string
  tags?: string[]
  confidence?: number
  importance?: number
}

export interface MemorySearchRequest {
  query: string
  scopes?: string[]
  mode?: 'text' | 'semantic' | 'hybrid'
  limit?: number
}

export interface MemorySearchResult {
  memory_id: string
  score: number
  scope: string
  scope_id: string | null
  type: string
  title: string
  content: string
  tags: string[]
  confidence: number
  importance: number
  has_embedding: boolean
}

export interface MemorySearchResponse {
  results: MemorySearchResult[]
}

export interface MemoryLinkCreate {
  target_memory_id: string
  relation_type: string
  strength?: number
}
