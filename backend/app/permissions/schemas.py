from typing import List
from pydantic import BaseModel


class PermissionCheckRequest(BaseModel):
    tool_name: str
    capabilities: List[str] = []
    explicit_tools: List[str] = []
    blocked_tools: List[str] = []
    workspace_ids: List[str] = []


class PermissionCheckResult(BaseModel):
    allowed: bool
    reason: str = ""
    error_code: str = ""
