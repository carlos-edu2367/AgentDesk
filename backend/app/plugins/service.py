import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import AgentModel, AgentPluginModel, AuditLogModel, PluginModel, SkillModel
from app.domain.schemas import SkillCreate
from app.domain.utils import generate_id
from app.skills.service import SkillService
from app.tools.registry import tool_registry

from .errors import PluginConflictError, PluginNotFoundError
from .importer import copy_plugin_to_appdata
from .manifest import PluginManifest
from .runner import PluginTool
from .validator import validate_manifest


class PluginService:
    def __init__(self, db: Session):
        self.db = db

    def import_plugin_folder(self, folder: str) -> PluginModel:
        manifest = validate_manifest(folder)
        install_path = copy_plugin_to_appdata(folder, manifest)

        existing = self.db.query(PluginModel).filter(PluginModel.id == manifest.id).first()
        data = {
            "id": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "enabled": manifest.enabled_by_default,
            "manifest_path": str(install_path / "plugin.json"),
            "install_path": str(install_path),
            "permissions": manifest.permissions,
            "tools_json": [tool.model_dump() for tool in manifest.tools],
            "skills_json": self._load_skill_payloads(install_path, manifest),
            "deleted_at": None,
        }
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            plugin = existing
        else:
            plugin = PluginModel(**data)
            self.db.add(plugin)
        self.db.commit()
        self.db.refresh(plugin)

        self._import_skills(plugin)
        if plugin.enabled:
            self.register_plugin_tools_in_tool_registry(plugin.id)
        self._audit("plugin_imported", f"Plugin imported: {plugin.name}", {"plugin_id": plugin.id}, "high")
        return plugin

    def list_plugins(self) -> list[PluginModel]:
        return (
            self.db.query(PluginModel)
            .filter(PluginModel.deleted_at.is_(None))
            .order_by(PluginModel.name.asc())
            .all()
        )

    def get_plugin(self, plugin_id: str) -> PluginModel:
        plugin = self.db.query(PluginModel).filter(PluginModel.id == plugin_id, PluginModel.deleted_at.is_(None)).first()
        if not plugin:
            raise PluginNotFoundError("Plugin not found")
        return plugin

    def enable_plugin(self, plugin_id: str) -> PluginModel:
        plugin = self.get_plugin(plugin_id)
        plugin.enabled = True
        plugin.updated_at = datetime.utcnow()
        self.db.add(plugin)
        self.db.commit()
        self.db.refresh(plugin)
        self.register_plugin_tools_in_tool_registry(plugin.id)
        self._audit("plugin_enabled", f"Plugin enabled: {plugin.name}", {"plugin_id": plugin.id}, "medium")
        return plugin

    def disable_plugin(self, plugin_id: str) -> PluginModel:
        plugin = self.get_plugin(plugin_id)
        plugin.enabled = False
        plugin.updated_at = datetime.utcnow()
        self.db.add(plugin)
        self.db.commit()
        self.db.refresh(plugin)
        self._audit("plugin_disabled", f"Plugin disabled: {plugin.name}", {"plugin_id": plugin.id}, "medium")
        return plugin

    def delete_plugin(self, plugin_id: str) -> None:
        plugin = self.get_plugin(plugin_id)
        plugin.enabled = False
        plugin.deleted_at = datetime.utcnow()
        plugin.updated_at = datetime.utcnow()
        self.db.add(plugin)
        for skill in self.db.query(SkillModel).filter(SkillModel.plugin_id == plugin_id).all():
            skill.deleted_at = datetime.utcnow()
            self.db.add(skill)
        for agent in self.db.query(AgentModel).all():
            if plugin_id in (agent.plugins or []):
                agent.plugins = [pid for pid in agent.plugins if pid != plugin_id]
                self.db.add(agent)
        self.db.query(AgentPluginModel).filter(AgentPluginModel.plugin_id == plugin_id).delete()
        self.db.commit()
        tool_registry.unregister_plugin(plugin_id)
        self._audit("plugin_removed", f"Plugin removed: {plugin.name}", {"plugin_id": plugin.id}, "high")

    def get_plugin_tools(self, plugin_id: str) -> list[dict]:
        plugin = self.get_plugin(plugin_id)
        return [dict(tool, plugin_id=plugin.id) for tool in (plugin.tools_json or [])]

    def get_plugin_skills(self, plugin_id: str) -> list[SkillModel]:
        self.get_plugin(plugin_id)
        return (
            self.db.query(SkillModel)
            .filter(SkillModel.plugin_id == plugin_id, SkillModel.deleted_at.is_(None))
            .order_by(SkillModel.name.asc())
            .all()
        )

    def register_plugin_tools_in_tool_registry(self, plugin_id: str) -> None:
        plugin = self.get_plugin(plugin_id)
        for tool_spec in plugin.tools_json or []:
            name = tool_spec["name"]
            if tool_registry.exists(name):
                existing = tool_registry.get(name)
                if getattr(existing, "source", "") == "plugin" and getattr(existing, "plugin_id", "") == plugin.id:
                    tool_registry.unregister(name)
                else:
                    raise PluginConflictError(f"Tool '{name}' is already registered")
            tool_registry.register(PluginTool(plugin.id, plugin.install_path, tool_spec))

    def unregister_plugin_tools(self, plugin_id: str) -> None:
        tool_registry.unregister_plugin(plugin_id)

    def get_agent_plugins(self, agent_id: str) -> list[PluginModel]:
        agent = self._get_agent(agent_id)
        ids = list(agent.plugins or [])
        if not ids:
            return []
        plugins = self.db.query(PluginModel).filter(PluginModel.id.in_(ids), PluginModel.deleted_at.is_(None)).all()
        by_id = {plugin.id: plugin for plugin in plugins}
        return [by_id[pid] for pid in ids if pid in by_id]

    def set_agent_plugins(self, agent_id: str, plugin_ids: list[str]) -> list[PluginModel]:
        agent = self._get_agent(agent_id)
        plugins = self._get_plugins_by_ids(plugin_ids)
        agent.plugins = [plugin.id for plugin in plugins]
        self.db.query(AgentPluginModel).filter(AgentPluginModel.agent_id == agent_id).delete()
        for plugin in plugins:
            self.db.add(AgentPluginModel(agent_id=agent_id, plugin_id=plugin.id))
        self.db.add(agent)
        self.db.commit()
        return plugins

    def assign_plugin_to_agent(self, agent_id: str, plugin_id: str) -> list[PluginModel]:
        agent = self._get_agent(agent_id)
        self.get_plugin(plugin_id)
        current = list(agent.plugins or [])
        if plugin_id not in current:
            current.append(plugin_id)
        return self.set_agent_plugins(agent_id, current)

    def remove_plugin_from_agent(self, agent_id: str, plugin_id: str) -> list[PluginModel]:
        agent = self._get_agent(agent_id)
        return self.set_agent_plugins(agent_id, [pid for pid in (agent.plugins or []) if pid != plugin_id])

    def _load_skill_payloads(self, install_path: Path, manifest: PluginManifest) -> list[dict]:
        payloads = []
        for rel_path in manifest.skills:
            data = json.loads((install_path / rel_path).read_text(encoding="utf-8"))
            data["plugin_id"] = manifest.id
            payloads.append(data)
        return payloads

    def _import_skills(self, plugin: PluginModel) -> None:
        for payload in plugin.skills_json or []:
            skill = SkillCreate.model_validate(payload)
            existing = self.db.query(SkillModel).filter(SkillModel.id == skill.id).first()
            if existing and existing.deleted_at is None and existing.plugin_id != plugin.id:
                raise PluginConflictError(f"Skill '{skill.id}' already exists")
            if existing and existing.deleted_at is not None:
                SkillService(self.db).create_skill(skill, audit=False)
            else:
                SkillService(self.db).import_skill_json(skill, overwrite=bool(existing))

    def _get_agent(self, agent_id: str) -> AgentModel:
        agent = self.db.query(AgentModel).filter(AgentModel.id == agent_id).first()
        if not agent:
            raise PluginNotFoundError("Agent not found")
        return agent

    def _get_plugins_by_ids(self, plugin_ids: list[str]) -> list[PluginModel]:
        unique_ids = list(dict.fromkeys(plugin_ids or []))
        plugins = self.db.query(PluginModel).filter(PluginModel.id.in_(unique_ids), PluginModel.deleted_at.is_(None)).all() if unique_ids else []
        by_id = {plugin.id: plugin for plugin in plugins}
        missing = [pid for pid in unique_ids if pid not in by_id]
        if missing:
            raise PluginNotFoundError(f"Plugin not found: {missing[0]}")
        return [by_id[pid] for pid in unique_ids]

    def _audit(self, event_type: str, summary: str, data: dict, risk_level: str = "low") -> None:
        self.db.add(AuditLogModel(
            id=generate_id("audit"),
            execution_id="",
            agent_id="system",
            event_type=event_type,
            risk_level=risk_level,
            summary=summary,
            data=data,
        ))
        self.db.commit()
