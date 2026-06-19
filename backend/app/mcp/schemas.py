from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPToolSpec:
    name: str
    original_name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    server_id: str = ""
    critical: bool = True

