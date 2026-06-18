from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from app.domain.enums import (
    ProviderType, ExecutionType, ExecutionStatus, EventType,
    ToolSource, MemoryScope, MemoryType, ApprovalStatus, ApprovalMode
)
from app.domain.utils import generate_id

# User
class UserBase(BaseModel):
    name: str = "Local User"
    settings: Dict[str, Any] = Field(default_factory=dict)

class User(UserBase):
    id: str = "user_local"
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Provider
class ProviderBase(BaseModel):
    type: ProviderType
    name: str
    base_url: Optional[str] = None
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

class ProviderCreate(ProviderBase):
    pass

class ProviderUpdate(BaseModel):
    type: Optional[ProviderType] = None
    name: Optional[str] = None
    base_url: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

class Provider(ProviderBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

# ModelConfig
class ModelConfig(BaseModel):
    provider_id: str
    model: str
    temperature: float = 0.4
    top_p: float = 0.9
    context_window: int = 8192
    max_tokens: int = 2048
    stream: bool = True

class MemoryConfig(BaseModel):
    use_global: bool = True
    use_agent_memory: bool = True
    use_team_memory: bool = False

class AgentSubagentsConfig(BaseModel):
    can_call: bool = True
    allowed_agent_ids: List[str] = Field(default_factory=lambda: ["*"])

# Agent
class AgentBase(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    llm_config: ModelConfig = Field(alias="model_config")
    capabilities: List[str] = Field(default_factory=list)
    explicit_tools: List[str] = Field(default_factory=list)
    blocked_tools: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    plugins: List[str] = Field(default_factory=list)
    mcp_servers: List[str] = Field(default_factory=list)
    memory_config: MemoryConfig = Field(default_factory=MemoryConfig)
    subagents: AgentSubagentsConfig = Field(default_factory=AgentSubagentsConfig)

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_config: Optional[ModelConfig] = Field(default=None, alias="model_config")
    capabilities: Optional[List[str]] = None
    explicit_tools: Optional[List[str]] = None
    blocked_tools: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    plugins: Optional[List[str]] = None
    mcp_servers: Optional[List[str]] = None
    memory_config: Optional[MemoryConfig] = None
    subagents: Optional[AgentSubagentsConfig] = None

class Agent(AgentBase):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Team
class TeamMemoryConfig(BaseModel):
    use_global: bool = True
    use_team_memory: bool = True
    allow_member_memories: bool = True

class TeamToolsPolicy(BaseModel):
    inherit_from_agents: bool = True
    additional_capabilities: List[str] = Field(default_factory=list)
    blocked_tools: List[str] = Field(default_factory=list)

class TeamBase(BaseModel):
    name: str
    description: str = ""
    leader_agent_id: str
    member_agent_ids: List[str] = Field(default_factory=list)
    execution_strategy: str = "leader_managed"
    memory_config: TeamMemoryConfig = Field(default_factory=TeamMemoryConfig)
    tools_policy: TeamToolsPolicy = Field(default_factory=TeamToolsPolicy)

class TeamCreate(TeamBase):
    pass

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    leader_agent_id: Optional[str] = None
    member_agent_ids: Optional[List[str]] = None
    execution_strategy: Optional[str] = None
    memory_config: Optional[TeamMemoryConfig] = None
    tools_policy: Optional[TeamToolsPolicy] = None

class Team(TeamBase):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Workspace
class WorkspacePermissions(BaseModel):
    read: bool = True
    write: bool = True
    delete: bool = False
    execute: bool = False

class WorkspaceBase(BaseModel):
    name: str
    paths: List[str] = Field(default_factory=list)
    permissions: WorkspacePermissions = Field(default_factory=WorkspacePermissions)

class WorkspaceCreate(WorkspaceBase):
    pass

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    paths: Optional[List[str]] = None
    permissions: Optional[WorkspacePermissions] = None

class Workspace(WorkspaceBase):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Execution
class ExecutionBase(BaseModel):
    type: ExecutionType
    target_id: str
    user_input: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    approval_mode: ApprovalMode = ApprovalMode.MANUAL
    workspace_ids: List[str] = Field(default_factory=list)

class ExecutionCreate(ExecutionBase):
    pass

class ExecutionUpdate(BaseModel):
    status: Optional[ExecutionStatus] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None

class Execution(ExecutionBase):
    id: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ExecutionEventBase(BaseModel):
    execution_id: str
    type: EventType
    source: str
    source_id: str
    content: Dict[str, Any] = Field(default_factory=dict)

class ExecutionEventCreate(ExecutionEventBase):
    pass

class ExecutionEvent(ExecutionEventBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Outros
class SkillBase(BaseModel):
    name: str
    version: str = "0.1.0"
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    prompt: str
    examples: List[Dict[str, Any]] = Field(default_factory=list)

class SkillCreate(SkillBase):
    pass

class SkillUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    prompt: Optional[str] = None
    examples: Optional[List[Dict[str, Any]]] = None

class Skill(SkillBase):
    id: str

class PluginBase(BaseModel):
    name: str
    version: str = "0.1.0"
    description: str = ""
    enabled: bool = True
    manifest_path: str = ""
    permissions: List[str] = Field(default_factory=list)

class PluginCreate(PluginBase):
    pass

class PluginUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    manifest_path: Optional[str] = None
    permissions: Optional[List[str]] = None

class Plugin(PluginBase):
    id: str
    created_at: datetime
    updated_at: datetime

class MCPServerBase(BaseModel):
    name: str
    enabled: bool = True
    transport: str = "stdio"
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)

class MCPServerCreate(MCPServerBase):
    pass

class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    transport: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None

class MCPServer(MCPServerBase):
    id: str
    created_at: datetime
    updated_at: datetime

class AuditLogCreate(BaseModel):
    execution_id: str
    agent_id: str
    event_type: str
    risk_level: str = "low"
    summary: str
    data: Dict[str, Any] = Field(default_factory=dict)

class AuditLog(AuditLogCreate):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ApprovalRequest
class ApprovalRequestCreate(BaseModel):
    execution_id: str
    agent_id: str
    tool: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    risk_level: str = "medium"
    summary: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    pending_state: Dict[str, Any] = Field(default_factory=dict)

class ApprovalRequestUpdate(BaseModel):
    status: Optional[ApprovalStatus] = None
    rejection_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None

class ApprovalRequest(ApprovalRequestCreate):
    id: str
    rejection_reason: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class ApprovalResolutionRequest(BaseModel):
    approved: bool
    reason: Optional[str] = None

class MemoryBase(BaseModel):
    scope: MemoryScope
    scope_id: Optional[str] = None
    type: MemoryType
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    importance: float = 1.0
    source: Dict[str, Any] = Field(default_factory=dict)

class MemoryCreate(MemoryBase):
    pass

class MemoryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    confidence: Optional[float] = None
    importance: Optional[float] = None
    last_used_at: Optional[datetime] = None
    usage_count: Optional[int] = None

class Memory(MemoryBase):
    id: str
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    deleted_at: Optional[datetime] = None
    embedding_status: str = "pending"
    model_config = ConfigDict(from_attributes=True)

class MemoryLinkCreate(BaseModel):
    target_memory_id: str
    relation_type: str
    strength: float = 1.0

class MemoryLink(MemoryLinkCreate):
    id: str
    source_memory_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class MemorySearchRequest(BaseModel):
    query: str
    scopes: List[str] = Field(default_factory=lambda: ["global"])
    mode: str = "hybrid"
    limit: int = 10

class MemorySearchResult(BaseModel):
    memory_id: str
    score: float
    scope: str
    scope_id: Optional[str]
    type: str
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    confidence: float
    importance: float
    has_embedding: bool

class MemorySearchResponse(BaseModel):
    results: List[MemorySearchResult]
