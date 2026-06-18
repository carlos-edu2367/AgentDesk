from enum import Enum

class ProviderType(str, Enum):
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"

class ExecutionType(str, Enum):
    AGENT = "agent"
    TEAM = "team"

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class EventType(str, Enum):
    EXECUTION_CREATED = "execution_created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_WAITING_APPROVAL = "execution_waiting_approval"
    EXECUTION_RESUMED = "execution_resumed"
    AGENT_STARTED = "agent_started"
    PROMPT_BUILT = "prompt_built"
    MODEL_REQUEST_STARTED = "model_request_started"
    MODEL_CHUNK = "model_chunk"
    MODEL_COMPLETED = "model_completed"
    AGENT_COMPLETED = "agent_completed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    TOOL_CALL_IGNORED = "tool_call_ignored"
    TOOL_CALL_REQUESTED = "tool_call_requested"
    TOOL_CALL_VALIDATED = "tool_call_validated"
    TOOL_CALL_DENIED = "tool_call_denied"
    TOOL_EXECUTED = "tool_executed"
    TOOL_RESULT = "tool_result"
    TOOL_FAILED = "tool_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_AUTO_GRANTED = "approval_auto_granted"
    TERMINAL_STARTED = "terminal_started"
    TERMINAL_COMPLETED = "terminal_completed"
    TERMINAL_FAILED = "terminal_failed"
    TERMINAL_TIMEOUT = "terminal_timeout"

    MESSAGE = "message"
    STATUS = "status"
    TOOL_CALL = "tool_call"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESULT = "approval_result"
    MEMORY_LOOKUP = "memory_lookup"
    MEMORY_LOOKUP_RESULT = "memory_lookup_result"
    MEMORY_CREATED = "memory_created"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_deleted"
    MEMORY_EMBEDDING_GENERATED = "memory_embedding_generated"
    MEMORY_EMBEDDING_FAILED = "memory_embedding_failed"
    MEMORY_USAGE_RECORDED = "memory_usage_recorded"
    SUBAGENT_CALL = "subagent_call"
    TEAM_EVENT = "team_event"
    ERROR = "error"

class ToolSource(str, Enum):
    CORE = "core"
    PLUGIN = "plugin"
    MCP = "mcp"

class MemoryScope(str, Enum):
    GLOBAL = "global"
    AGENT = "agent"
    TEAM = "team"
    WORKSPACE = "workspace"

class MemoryType(str, Enum):
    PROFILE = "profile"
    PREFERENCE = "preference"
    PROJECT = "project"
    FILE_REFERENCE = "file_reference"
    TASK_HISTORY = "task_history"
    DECISION = "decision"
    LESSON = "lesson"
    ERROR_PATTERN = "error_pattern"
    WORKFLOW = "workflow"
    SYSTEM_NOTE = "system_note"

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class ApprovalMode(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"
