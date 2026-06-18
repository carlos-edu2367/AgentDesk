from typing import Any, Dict

from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError
from app.memory.service import MemoryService
from app.domain.schemas import MemoryCreate, MemorySearchRequest
from app.domain.enums import MemoryScope, MemoryType


class MemorySearchTool(BaseTool):
    name = "memory.search"
    description = "Search agent memories by text, semantic similarity, or hybrid mode"
    capability = "memory"
    critical = False
    source = "core"
    input_schema = {
        "query": {"type": "string", "description": "Search query"},
        "scopes": {"type": "array", "items": {"type": "string"}, "description": "Scopes: global, agent:<id>, team:<id>"},
        "mode": {"type": "string", "description": "text | semantic | hybrid", "default": "hybrid"},
        "limit": {"type": "integer", "default": 10},
    }
    output_schema = {
        "results": {"type": "array"},
        "count": {"type": "integer"},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        query = arguments.get("query", "").strip()
        if not query:
            raise ToolError("MISSING_ARGUMENT", "memory.search requires 'query'")

        scopes = arguments.get("scopes", ["global"])
        mode = arguments.get("mode", "hybrid")
        limit = min(int(arguments.get("limit", 10)), 100)

        svc = MemoryService(context.db)
        request = MemorySearchRequest(query=query, scopes=scopes, mode=mode, limit=limit)
        response = await svc.search(request)

        return {
            "results": [r.model_dump() for r in response.results],
            "count": len(response.results),
        }


class MemoryCreateTool(BaseTool):
    name = "memory.create"
    description = "Create a new memory entry (global, agent, or team scope)"
    capability = "memory"
    critical = False
    source = "core"
    input_schema = {
        "title": {"type": "string", "description": "Short descriptive title"},
        "content": {"type": "string", "description": "Memory content"},
        "scope": {"type": "string", "description": "global | agent | team", "default": "global"},
        "scope_id": {"type": "string", "description": "Agent or team ID (if scope is agent/team)", "nullable": True},
        "type": {"type": "string", "description": "preference | decision | lesson | workflow | ...", "default": "preference"},
        "tags": {"type": "array", "items": {"type": "string"}, "default": []},
        "confidence": {"type": "number", "default": 0.8},
        "importance": {"type": "number", "default": 0.7},
    }
    output_schema = {
        "memory_id": {"type": "string"},
        "status": {"type": "string"},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        title = arguments.get("title", "").strip()
        content = arguments.get("content", "").strip()
        if not title:
            raise ToolError("MISSING_ARGUMENT", "memory.create requires 'title'")
        if not content:
            raise ToolError("MISSING_ARGUMENT", "memory.create requires 'content'")

        scope_str = arguments.get("scope", "global")
        try:
            scope = MemoryScope(scope_str)
        except ValueError:
            valid = [s.value for s in MemoryScope]
            raise ToolError("INVALID_ARGUMENT", f"Invalid scope '{scope_str}'. Valid values: {valid}")

        type_str = arguments.get("type", "preference")
        try:
            mem_type = MemoryType(type_str)
        except ValueError:
            valid = [t.value for t in MemoryType]
            raise ToolError("INVALID_ARGUMENT", f"Invalid type '{type_str}'. Valid values: {valid}")

        mem_in = MemoryCreate(
            scope=scope,
            scope_id=arguments.get("scope_id"),
            type=mem_type,
            title=title,
            content=content,
            tags=arguments.get("tags", []),
            confidence=float(arguments.get("confidence", 0.8)),
            importance=float(arguments.get("importance", 0.7)),
            source={
                "type": "agent_observation",
                "execution_id": context.execution_id,
                "agent_id": context.agent_id,
            },
        )
        svc = MemoryService(context.db)
        mem = await svc.create_memory(mem_in)
        return {"memory_id": mem.id, "status": "created"}
