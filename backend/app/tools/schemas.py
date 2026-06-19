from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    description: str
    source: str
    capability: str
    critical: bool = False
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}
    plugin_id: Optional[str] = None
    server_id: Optional[str] = None


class ToolCallRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}


class ToolResult(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}
    status: str  # "success" | "error" | "denied"
    result: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    result_preview: Optional[str] = None


class CapabilityInfo(BaseModel):
    name: str
    tools: List[str]


class AgentToolsConfig(BaseModel):
    capabilities: List[str] = []
    explicit_tools: List[str] = []
    blocked_tools: List[str] = []
