from app.db.repositories.base import BaseRepository
from app.db import models
from app.domain import schemas

agent_repo = BaseRepository[models.AgentModel, schemas.AgentCreate, schemas.AgentUpdate](models.AgentModel)
team_repo = BaseRepository[models.TeamModel, schemas.TeamCreate, schemas.TeamUpdate](models.TeamModel)
workspace_repo = BaseRepository[models.WorkspaceModel, schemas.WorkspaceCreate, schemas.WorkspaceUpdate](models.WorkspaceModel)
provider_repo = BaseRepository[models.ProviderModel, schemas.ProviderCreate, schemas.ProviderUpdate](models.ProviderModel)
execution_repo = BaseRepository[models.ExecutionModel, schemas.ExecutionCreate, schemas.ExecutionUpdate](models.ExecutionModel)
execution_event_repo = BaseRepository[models.ExecutionEventModel, schemas.ExecutionEventCreate, schemas.ExecutionEventCreate](models.ExecutionEventModel)
memory_repo = BaseRepository[models.MemoryModel, schemas.MemoryCreate, schemas.MemoryUpdate](models.MemoryModel)
memory_embedding_repo = BaseRepository[models.MemoryEmbeddingModel, object, object](models.MemoryEmbeddingModel)
memory_link_repo = BaseRepository[models.MemoryLinkModel, schemas.MemoryLinkCreate, schemas.MemoryLinkCreate](models.MemoryLinkModel)
memory_usage_repo = BaseRepository[models.MemoryUsageModel, object, object](models.MemoryUsageModel)
audit_log_repo = BaseRepository[models.AuditLogModel, schemas.AuditLogCreate, schemas.AuditLogCreate](models.AuditLogModel)
approval_repo = BaseRepository[models.ApprovalRequestModel, schemas.ApprovalRequestCreate, schemas.ApprovalRequestUpdate](models.ApprovalRequestModel)

skill_repo = BaseRepository[models.SkillModel, schemas.SkillCreate, schemas.SkillUpdate](models.SkillModel)
mcp_repo = BaseRepository[models.MCPServerModel, schemas.MCPServerCreate, schemas.MCPServerUpdate](models.MCPServerModel)
plugin_repo = BaseRepository[models.PluginModel, schemas.PluginCreate, schemas.PluginUpdate](models.PluginModel)
