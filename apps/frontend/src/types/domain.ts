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
  | 'model_reasoning_chunk'
  | 'model_output_truncated'
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
  | 'plugin_tool_call_requested'
  | 'plugin_tool_started'
  | 'plugin_tool_completed'
  | 'plugin_tool_failed'
  | 'plugin_disabled_tool_blocked'
  | 'mcp_tool_call_requested'
  | 'mcp_tool_started'
  | 'mcp_tool_completed'
  | 'mcp_tool_failed'
  | 'mcp_server_disabled_tool_blocked'
  | 'mcp_server_not_associated'
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
  | 'skills_loaded'
  | 'skills_truncated'
  | 'skill_injected'
  | 'skill_load_failed'
  | 'subagent_call'
  | 'subagent_call_requested'
  | 'subagent_started'
  | 'subagent_completed'
  | 'subagent_failed'
  | 'team_started'
  | 'leader_started'
  | 'leader_plan_created'
  | 'member_assigned'
  | 'member_started'
  | 'member_completed'
  | 'member_failed'
  | 'leader_review_started'
  | 'leader_finalized'
  | 'team_completed'
  | 'team_failed'
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
  output_schema?: Record<string, unknown>
  plugin_id?: string
  server_id?: string
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
  subagents?: AgentSubagentsConfig
  created_at: string
  updated_at: string
}

export interface AgentSubagentsConfig {
  can_call: boolean
  allowed_agent_ids: string[]
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
  explicit_tools?: string[]
  blocked_tools?: string[]
  skills?: string[]
  plugins?: string[]
  mcp_servers?: string[]
}

export interface MCPToolInfo {
  name: string
  original_name: string
  description: string
  input_schema: Record<string, unknown>
  server_id: string
  critical: boolean
}

export interface MCPServer {
  id: string
  name: string
  enabled: boolean
  transport: 'stdio'
  command: string
  args: string[]
  env: Record<string, string>
  tools_cache_json: MCPToolInfo[]
  last_connected_at: string | null
  last_error: string | null
  created_at: string
  updated_at: string
  deleted_at?: string | null
}

export interface MCPServerCreate {
  id: string
  name: string
  enabled: boolean
  transport: 'stdio'
  command: string
  args: string[]
  env: Record<string, string>
}

export interface MCPServerUpdate {
  name?: string
  enabled?: boolean
  transport?: 'stdio'
  command?: string
  args?: string[]
  env?: Record<string, string>
}

export interface MCPTestResponse {
  server_id: string
  status: 'ok' | 'error'
  tools: MCPToolInfo[]
  error?: { code: string; message: string } | null
}

export interface Skill {
  id: string
  name: string
  version: string
  description: string
  tags: string[]
  prompt: string
  examples: Record<string, unknown>[]
  plugin_id?: string | null
  created_at?: string | null
  updated_at?: string | null
  deleted_at?: string | null
}

export interface PluginToolManifest {
  name: string
  description?: string
  entrypoint?: string
  runtime?: string
  capability: string
  critical?: boolean
  input_schema?: Record<string, unknown>
  plugin_id?: string
}

export interface Plugin {
  id: string
  name: string
  version: string
  description: string
  enabled: boolean
  manifest_path: string
  install_path: string
  permissions: string[]
  tools_json: PluginToolManifest[]
  skills_json: Array<{ id: string; name?: string; description?: string }>
  created_at?: string
  updated_at?: string
  deleted_at?: string | null
}

export interface PluginImportResponse {
  id: string
  name: string
  version: string
  enabled: boolean
  tools: string[]
  skills: string[]
}

export interface SkillCreate {
  id: string
  name: string
  version: string
  description: string
  tags?: string[]
  prompt: string
  examples?: Record<string, unknown>[]
}

export interface SkillUpdate {
  name?: string
  version?: string
  description?: string
  tags?: string[]
  prompt?: string
  examples?: Record<string, unknown>[]
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

export interface Conversation {
  id: string
  type: 'agent' | 'team'
  target_id: string
  title: string
  workspace_ids: string[]
  max_steps?: number | null
  created_at: string
  updated_at: string
}

export interface ConversationUpdate {
  title?: string
  workspace_ids?: string[]
  max_steps?: number | null
}

export interface ConversationTurn {
  execution: Execution
  events: ExecutionEvent[]
}

export interface ConversationDetail {
  conversation: Conversation
  turns: ConversationTurn[]
}

export interface ConversationCreate {
  type: 'agent' | 'team'
  target_id: string
  title?: string
}

export interface ConversationMessageRequest {
  message: string
  approval_mode?: ApprovalMode
  workspace_ids?: string[]
  max_steps?: number | null
  stream?: boolean
}

export interface AuditLog {
  id: string
  execution_id: string
  agent_id: string
  team_id?: string | null
  event_type: string
  risk_level: 'low' | 'medium' | 'high' | 'critical' | string
  summary: string
  data: Record<string, unknown>
  tool?: string | null
  source?: string | null
  source_id?: string | null
  approval_mode?: ApprovalMode | string | null
  status?: string | null
  duration_ms?: number | null
  created_at: string
}

export interface PaginatedAuditLogs {
  items: AuditLog[]
  total: number
  limit: number
  offset: number
}

export interface AuditLogFilters {
  date_from?: string
  date_to?: string
  execution_id?: string
  agent_id?: string
  team_id?: string
  event_type?: string
  risk_level?: string
  tool?: string
  source?: string
  status?: string
  approval_mode?: string
  query?: string
  limit?: number
  offset?: number
}

export interface ExecutionFilters {
  date_from?: string
  date_to?: string
  type?: 'agent' | 'team' | ''
  target_id?: string
  agent_id?: string
  team_id?: string
  status?: ExecutionStatus | ''
  approval_mode?: ApprovalMode | ''
  query?: string
  limit?: number
  offset?: number
}

export interface ExecutionDetailSummary {
  total_events: number
  total_audit_logs: number
  tools_used: string[]
  agents_involved: string[]
  mcp_servers_used: string[]
  plugins_used: string[]
  skills_used: string[]
  memories_used: string[]
  approval_mode: string
  critical_actions_count: number
  auto_approved_count: number
  manual_approved_count: number
  manual_rejected_count: number
}

export interface ExecutionDetailResponse {
  execution: Execution
  events: ExecutionEvent[]
  audit_logs: AuditLog[]
  approvals: ApprovalRequest[]
  artifacts: Record<string, unknown>[]
  summary: ExecutionDetailSummary
}

export interface ExecutionExportResponse {
  format: string
  path: string
  content: unknown
}

export interface AgentExecutionRequest {
  agent_id: string
  message: string
  approval_mode?: ApprovalMode
  workspace_ids?: string[]
  stream?: boolean
}

export interface TeamMemoryConfig {
  use_global: boolean
  use_team_memory: boolean
  allow_member_memories: boolean
}

export interface TeamToolsPolicy {
  inherit_from_agents: boolean
  additional_capabilities: string[]
  blocked_tools: string[]
}

export interface Team {
  id: string
  name: string
  description: string
  leader_agent_id: string
  member_agent_ids: string[]
  skills: string[]
  execution_strategy: 'leader_managed'
  memory_config: TeamMemoryConfig
  tools_policy: TeamToolsPolicy
  mcp_servers?: string[]
  created_at: string
  updated_at: string
}

export interface TeamCreate {
  name: string
  description?: string
  leader_agent_id: string
  member_agent_ids?: string[]
  skills?: string[]
  execution_strategy?: 'leader_managed'
  memory_config?: TeamMemoryConfig
  tools_policy?: TeamToolsPolicy
  mcp_servers?: string[]
}

export interface TeamUpdate {
  name?: string
  description?: string
  leader_agent_id?: string
  member_agent_ids?: string[]
  skills?: string[]
  execution_strategy?: 'leader_managed'
  memory_config?: TeamMemoryConfig
  tools_policy?: TeamToolsPolicy
}

export interface TeamExecutionRequest {
  team_id: string
  message: string
  approval_mode?: ApprovalMode
  workspace_ids?: string[]
  stream?: boolean
}

export interface HealthResponse {
  status: string
  version?: string
  storage_ready?: boolean
  database_ready?: boolean
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
