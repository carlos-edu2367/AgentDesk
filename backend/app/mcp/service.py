from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AgentMCPServerModel, AgentModel, AuditLogModel, MCPServerModel, TeamMCPServerModel, TeamModel
from app.domain.schemas import MCPServerCreate, MCPServerUpdate
from app.domain.utils import generate_id

from .errors import MCPConnectionError, MCPError, MCPServerNotFoundError
from .registry import register_mcp_tools
from .stdio import StdioMCPClient
from .utils import mask_secrets, mcp_tool_name, normalize_part


class MCPService:
    def __init__(self, db: Session):
        self.db = db

    def list_servers(self) -> list[MCPServerModel]:
        servers = (
            self.db.query(MCPServerModel)
            .filter(MCPServerModel.deleted_at.is_(None))
            .order_by(MCPServerModel.name.asc())
            .all()
        )
        for server in servers:
            register_mcp_tools(server)
        return servers

    def get_server(self, server_id: str) -> MCPServerModel:
        server = (
            self.db.query(MCPServerModel)
            .filter(MCPServerModel.id == normalize_part(server_id), MCPServerModel.deleted_at.is_(None))
            .first()
        )
        if not server:
            raise MCPServerNotFoundError(server_id)
        register_mcp_tools(server)
        return server

    def create_server(self, payload: MCPServerCreate) -> MCPServerModel:
        data = payload.model_dump()
        data["id"] = normalize_part(data["id"])
        server = MCPServerModel(**data)
        self.db.add(server)
        self.db.commit()
        self.db.refresh(server)
        self._audit("mcp_server_created", f"MCP server created: {server.name}", self._server_audit_data(server), "high")
        return server

    def update_server(self, server_id: str, payload: MCPServerUpdate) -> MCPServerModel:
        server = self.get_server(server_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(server, key, value)
        server.updated_at = datetime.utcnow()
        self.db.add(server)
        self.db.commit()
        self.db.refresh(server)
        register_mcp_tools(server)
        self._audit("mcp_server_updated", f"MCP server updated: {server.name}", self._server_audit_data(server), "high")
        return server

    def delete_server(self, server_id: str) -> None:
        server = self.get_server(server_id)
        server.enabled = False
        server.deleted_at = datetime.utcnow()
        server.updated_at = datetime.utcnow()
        self.db.add(server)
        for agent in self.db.query(AgentModel).all():
            if server.id in (agent.mcp_servers or []):
                agent.mcp_servers = [sid for sid in agent.mcp_servers if sid != server.id]
                self.db.add(agent)
        self.db.query(AgentMCPServerModel).filter(AgentMCPServerModel.mcp_server_id == server.id).delete()
        self.db.query(TeamMCPServerModel).filter(TeamMCPServerModel.mcp_server_id == server.id).delete()
        self.db.commit()
        register_mcp_tools(server)
        self._audit("mcp_server_removed", f"MCP server removed: {server.name}", {"server_id": server.id}, "high")

    def enable_server(self, server_id: str) -> MCPServerModel:
        server = self.get_server(server_id)
        server.enabled = True
        server.updated_at = datetime.utcnow()
        self.db.add(server)
        self.db.commit()
        self.db.refresh(server)
        register_mcp_tools(server)
        self._audit("mcp_server_enabled", f"MCP server enabled: {server.name}", {"server_id": server.id}, "medium")
        return server

    def disable_server(self, server_id: str) -> MCPServerModel:
        server = self.get_server(server_id)
        server.enabled = False
        server.updated_at = datetime.utcnow()
        self.db.add(server)
        self.db.commit()
        self.db.refresh(server)
        register_mcp_tools(server)
        self._audit("mcp_server_disabled", f"MCP server disabled: {server.name}", {"server_id": server.id}, "medium")
        return server

    async def test_connection(self, server_id: str) -> tuple[str, list[dict], MCPError | None]:
        server = self.get_server(server_id)
        try:
            async with StdioMCPClient(server.command, server.args or [], server.env or {}) as client:
                await client.initialize()
                raw_tools = await client.list_tools()
        except MCPError as exc:
            server.last_error = exc.message
            server.updated_at = datetime.utcnow()
            self.db.add(server)
            self.db.commit()
            self._audit("mcp_server_tested", f"MCP server test failed: {server.name}", {
                **self._server_audit_data(server),
                "error": {"code": exc.code, "message": exc.message},
            }, "high")
            return "error", [], exc
        except Exception as exc:
            error = MCPConnectionError("Failed to initialize MCP server.", {"error": str(exc)})
            server.last_error = error.message
            server.updated_at = datetime.utcnow()
            self.db.add(server)
            self.db.commit()
            self._audit("mcp_server_tested", f"MCP server test failed: {server.name}", {
                **self._server_audit_data(server),
                "error": {"code": error.code, "message": error.message},
            }, "high")
            return "error", [], error

        tools = [self._tool_payload(server.id, tool) for tool in raw_tools]
        server.tools_cache_json = tools
        server.last_connected_at = datetime.utcnow()
        server.last_error = ""
        server.updated_at = datetime.utcnow()
        self.db.add(server)
        self.db.commit()
        self.db.refresh(server)
        register_mcp_tools(server)
        self._audit("mcp_server_tested", f"MCP server tested: {server.name}", {
            **self._server_audit_data(server),
            "tool_count": len(tools),
        }, "medium")
        return "ok", tools, None

    def get_tools(self, server_id: str) -> list[dict]:
        return list(self.get_server(server_id).tools_cache_json or [])

    def get_agent_servers(self, agent_id: str) -> list[MCPServerModel]:
        agent = self._get_agent(agent_id)
        return self._servers_by_ids(agent.mcp_servers or [])

    def set_agent_servers(self, agent_id: str, server_ids: list[str]) -> list[MCPServerModel]:
        agent = self._get_agent(agent_id)
        servers = self._servers_by_ids(server_ids)
        agent.mcp_servers = [server.id for server in servers]
        self.db.query(AgentMCPServerModel).filter(AgentMCPServerModel.agent_id == agent_id).delete()
        for server in servers:
            self.db.add(AgentMCPServerModel(agent_id=agent_id, mcp_server_id=server.id))
        self.db.add(agent)
        self.db.commit()
        return servers

    def assign_agent_server(self, agent_id: str, server_id: str) -> list[MCPServerModel]:
        agent = self._get_agent(agent_id)
        self.get_server(server_id)
        current = list(agent.mcp_servers or [])
        normalized = normalize_part(server_id)
        if normalized not in current:
            current.append(normalized)
        return self.set_agent_servers(agent_id, current)

    def remove_agent_server(self, agent_id: str, server_id: str) -> list[MCPServerModel]:
        agent = self._get_agent(agent_id)
        normalized = normalize_part(server_id)
        return self.set_agent_servers(agent_id, [sid for sid in (agent.mcp_servers or []) if sid != normalized])

    def get_team_servers(self, team_id: str) -> list[MCPServerModel]:
        team = self._get_team(team_id)
        ids = (team.tools_policy or {}).get("mcp_servers", [])
        return self._servers_by_ids(ids)

    def set_team_servers(self, team_id: str, server_ids: list[str]) -> list[MCPServerModel]:
        team = self._get_team(team_id)
        servers = self._servers_by_ids(server_ids)
        policy = dict(team.tools_policy or {})
        policy["mcp_servers"] = [server.id for server in servers]
        team.tools_policy = policy
        self.db.query(TeamMCPServerModel).filter(TeamMCPServerModel.team_id == team_id).delete()
        for server in servers:
            self.db.add(TeamMCPServerModel(team_id=team_id, mcp_server_id=server.id))
        self.db.add(team)
        self.db.commit()
        return servers

    def assign_team_server(self, team_id: str, server_id: str) -> list[MCPServerModel]:
        current = [server.id for server in self.get_team_servers(team_id)]
        normalized = normalize_part(server_id)
        if normalized not in current:
            current.append(normalized)
        return self.set_team_servers(team_id, current)

    def remove_team_server(self, team_id: str, server_id: str) -> list[MCPServerModel]:
        normalized = normalize_part(server_id)
        current = [sid for sid in [server.id for server in self.get_team_servers(team_id)] if sid != normalized]
        return self.set_team_servers(team_id, current)

    def _tool_payload(self, server_id: str, raw: dict) -> dict:
        original = raw.get("name", "")
        return {
            "name": mcp_tool_name(server_id, original),
            "original_name": original,
            "description": raw.get("description") or "",
            "input_schema": raw.get("inputSchema") or raw.get("input_schema") or {},
            "server_id": server_id,
            "critical": True,
        }

    def _servers_by_ids(self, server_ids: list[str]) -> list[MCPServerModel]:
        ids = [normalize_part(sid) for sid in dict.fromkeys(server_ids or [])]
        if not ids:
            return []
        servers = self.db.query(MCPServerModel).filter(MCPServerModel.id.in_(ids), MCPServerModel.deleted_at.is_(None)).all()
        by_id = {server.id: server for server in servers}
        missing = [sid for sid in ids if sid not in by_id]
        if missing:
            raise MCPServerNotFoundError(missing[0])
        return [by_id[sid] for sid in ids]

    def _get_agent(self, agent_id: str) -> AgentModel:
        agent = self.db.query(AgentModel).filter(AgentModel.id == agent_id).first()
        if not agent:
            raise MCPServerNotFoundError("agent")
        return agent

    def _get_team(self, team_id: str) -> TeamModel:
        team = self.db.query(TeamModel).filter(TeamModel.id == team_id).first()
        if not team:
            raise MCPServerNotFoundError("team")
        return team

    def _server_audit_data(self, server: MCPServerModel) -> dict:
        return {
            "server_id": server.id,
            "transport": server.transport,
            "command": server.command,
            "args": mask_secrets(server.args or []),
            "env": mask_secrets(server.env or {}),
        }

    def _audit(self, event_type: str, summary: str, data: dict, risk_level: str = "low") -> None:
        self.db.add(AuditLogModel(
            id=generate_id("audit"),
            execution_id="",
            agent_id="system",
            event_type=event_type,
            risk_level=risk_level,
            summary=summary,
            data=mask_secrets(data),
        ))
        self.db.commit()

