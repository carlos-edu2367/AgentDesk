import json
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, JSON, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserModel(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    settings = Column(JSON, default=dict)

class ProviderModel(Base):
    __tablename__ = "providers"
    id = Column(String, primary_key=True)
    type = Column(String)
    name = Column(String)
    base_url = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    config = Column(JSON, default=dict)

class AgentModel(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True)
    name = Column(String)
    description = Column(String, default="")
    system_prompt = Column(Text, default="")
    model_config = Column(JSON, default=dict)
    capabilities = Column(JSON, default=list)
    explicit_tools = Column(JSON, default=list)
    blocked_tools = Column(JSON, default=list)
    skills = Column(JSON, default=list)
    plugins = Column(JSON, default=list)
    mcp_servers = Column(JSON, default=list)
    memory_config = Column(JSON, default=dict)
    subagents = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TeamModel(Base):
    __tablename__ = "teams"
    id = Column(String, primary_key=True)
    name = Column(String)
    description = Column(String, default="")
    leader_agent_id = Column(String, ForeignKey("agents.id"))
    member_agent_ids = Column(JSON, default=list)
    skills = Column(JSON, default=list)
    execution_strategy = Column(String, default="leader_managed")
    memory_config = Column(JSON, default=dict)
    tools_policy = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WorkspaceModel(Base):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True)
    name = Column(String)
    paths = Column(JSON, default=list)
    permissions = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ConversationModel(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True)
    type = Column(String)            # "agent" | "team"
    target_id = Column(String)       # agent id or team id
    title = Column(String, default="")
    workspace_ids = Column(JSON, default=list)  # workspaces granted to this chat
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExecutionModel(Base):
    __tablename__ = "executions"
    id = Column(String, primary_key=True)
    type = Column(String)
    target_id = Column(String)
    user_input = Column(Text)
    status = Column(String)
    approval_mode = Column(String)
    workspace_ids = Column(JSON, default=list)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

class ExecutionEventModel(Base):
    __tablename__ = "execution_events"
    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("executions.id"))
    type = Column(String)
    source = Column(String)
    source_id = Column(String)
    content = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class MemoryModel(Base):
    __tablename__ = "memories"
    id = Column(String, primary_key=True)
    scope = Column(String)
    scope_id = Column(String, nullable=True)
    type = Column(String)
    title = Column(String)
    content = Column(Text)
    tags = Column(JSON, default=list)
    confidence = Column(Float, default=1.0)
    importance = Column(Float, default=1.0)
    source = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    deleted_at = Column(DateTime, nullable=True)
    embedding_status = Column(String, default="pending")

class MemoryEmbeddingModel(Base):
    __tablename__ = "memory_embeddings"
    id = Column(String, primary_key=True)
    memory_id = Column(String, ForeignKey("memories.id"))
    embedding_model = Column(String)
    embedding_vector = Column(Text)  # JSON-serialized list[float]
    created_at = Column(DateTime, default=datetime.utcnow)

class MemoryLinkModel(Base):
    __tablename__ = "memory_links"
    id = Column(String, primary_key=True)
    source_memory_id = Column(String, ForeignKey("memories.id"))
    target_memory_id = Column(String, ForeignKey("memories.id"))
    relation_type = Column(String)  # related_to, contradicts, updates, supports, belongs_to_project, derived_from
    strength = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class MemoryUsageModel(Base):
    __tablename__ = "memory_usage"
    id = Column(String, primary_key=True)
    memory_id = Column(String, ForeignKey("memories.id"))
    execution_id = Column(String, ForeignKey("executions.id"), nullable=True)
    agent_id = Column(String)
    used_at = Column(DateTime, default=datetime.utcnow)
    score = Column(Float, default=0.0)

class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True)
    execution_id = Column(String)
    agent_id = Column(String)
    event_type = Column(String)
    risk_level = Column(String, default="low")
    summary = Column(Text)
    data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class SkillModel(Base):
    __tablename__ = "skills"
    id = Column(String, primary_key=True)
    name = Column(String)
    version = Column(String, default="0.1.0")
    description = Column(String, default="")
    tags = Column(JSON, default=list)
    prompt = Column(Text)
    examples = Column(JSON, default=list)
    plugin_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class AgentSkillModel(Base):
    __tablename__ = "agent_skills"
    agent_id = Column(String, ForeignKey("agents.id"), primary_key=True)
    skill_id = Column(String, ForeignKey("skills.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TeamSkillModel(Base):
    __tablename__ = "team_skills"
    team_id = Column(String, ForeignKey("teams.id"), primary_key=True)
    skill_id = Column(String, ForeignKey("skills.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class PluginModel(Base):
    __tablename__ = "plugins"
    id = Column(String, primary_key=True)
    name = Column(String)
    version = Column(String, default="0.1.0")
    description = Column(String, default="")
    enabled = Column(Boolean, default=True)
    manifest_path = Column(String, default="")
    install_path = Column(String, default="")
    permissions = Column(JSON, default=list)
    tools_json = Column(JSON, default=list)
    skills_json = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class AgentPluginModel(Base):
    __tablename__ = "agent_plugins"
    agent_id = Column(String, ForeignKey("agents.id"), primary_key=True)
    plugin_id = Column(String, ForeignKey("plugins.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TeamPluginModel(Base):
    __tablename__ = "team_plugins"
    team_id = Column(String, ForeignKey("teams.id"), primary_key=True)
    plugin_id = Column(String, ForeignKey("plugins.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class MCPServerModel(Base):
    __tablename__ = "mcp_servers"
    id = Column(String, primary_key=True)
    name = Column(String)
    enabled = Column(Boolean, default=True)
    transport = Column(String, default="stdio")
    command = Column(String)
    args = Column(JSON, default=list)
    env = Column(JSON, default=dict)
    tools_cache_json = Column(JSON, default=list)
    last_connected_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class AgentMCPServerModel(Base):
    __tablename__ = "agent_mcp_servers"
    agent_id = Column(String, ForeignKey("agents.id"), primary_key=True)
    mcp_server_id = Column(String, ForeignKey("mcp_servers.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TeamMCPServerModel(Base):
    __tablename__ = "team_mcp_servers"
    team_id = Column(String, ForeignKey("teams.id"), primary_key=True)
    mcp_server_id = Column(String, ForeignKey("mcp_servers.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ApprovalRequestModel(Base):
    __tablename__ = "execution_approvals"
    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("executions.id"))
    agent_id = Column(String)
    tool = Column(String)
    status = Column(String, default="pending")
    risk_level = Column(String, default="medium")
    summary = Column(Text)
    arguments = Column(JSON, default=dict)
    pending_state = Column(JSON, default=dict)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
