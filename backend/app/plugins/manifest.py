from typing import Any

from pydantic import BaseModel, Field, field_validator


class PluginToolManifest(BaseModel):
    name: str
    description: str
    entrypoint: str
    runtime: str = "python"
    capability: str
    critical: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("runtime")
    @classmethod
    def validate_runtime(cls, value: str) -> str:
        if value != "python":
            raise ValueError("Only python plugin tools are supported in the MVP")
        return value


class PluginManifest(BaseModel):
    id: str
    name: str
    version: str
    description: str
    author: str = "local"
    homepage: str = ""
    license: str = ""
    agentdesk_version: str = ">=0.1.0"
    enabled_by_default: bool = False
    permissions: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[PluginToolManifest] = Field(default_factory=list)

    @field_validator("id", "name", "version", "description")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("Field is required")
        return str(value).strip()
