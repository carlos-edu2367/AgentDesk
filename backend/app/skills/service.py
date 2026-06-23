from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.db.models import AgentModel, AgentSkillModel, AuditLogModel, PluginModel, SkillModel, TeamModel, TeamSkillModel
from app.domain.schemas import SkillCreate, SkillUpdate
from app.domain.utils import generate_id
from .errors import SkillAlreadyExistsError, SkillNotFoundError
from .exporter import export_skill


@dataclass
class FormattedSkills:
    text: str
    loaded: list[dict]
    injected: list[dict]
    truncated: bool


class SkillService:
    max_skills_per_prompt = 10
    max_skill_chars_per_item = 1200
    max_total_skill_chars = 6000

    def __init__(self, db: Session):
        self.db = db

    def list_skills(self) -> list[SkillModel]:
        return (
            self.db.query(SkillModel)
            .filter(SkillModel.deleted_at.is_(None))
            .order_by(SkillModel.name.asc())
            .all()
        )

    def get_skill(self, skill_id: str) -> SkillModel:
        skill = (
            self.db.query(SkillModel)
            .filter(SkillModel.id == skill_id, SkillModel.deleted_at.is_(None))
            .first()
        )
        if not skill:
            raise SkillNotFoundError("Skill not found")
        return skill

    def create_skill(self, skill_in: SkillCreate, audit: bool = True) -> SkillModel:
        existing = self.db.query(SkillModel).filter(SkillModel.id == skill_in.id).first()
        if existing and existing.deleted_at is None:
            raise SkillAlreadyExistsError("Skill already exists")

        data = skill_in.model_dump()
        if existing:
            for field, value in data.items():
                setattr(existing, field, value)
            existing.deleted_at = None
            existing.updated_at = datetime.utcnow()
            skill = existing
        else:
            skill = SkillModel(**data)
            self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        if audit:
            self._audit("skill_created", f"Skill created: {skill.name}", {"skill_id": skill.id})
        return skill

    def update_skill(self, skill_id: str, skill_in: SkillUpdate) -> SkillModel:
        skill = self.get_skill(skill_id)
        data = skill_in.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(skill, field, value)
        skill.updated_at = datetime.utcnow()
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        self._audit("skill_updated", f"Skill updated: {skill.name}", {"skill_id": skill.id})
        return skill

    def delete_skill(self, skill_id: str) -> None:
        skill = self.get_skill(skill_id)
        skill.deleted_at = datetime.utcnow()
        skill.updated_at = datetime.utcnow()
        self.db.add(skill)
        self._remove_skill_from_all_associations(skill_id)
        self.db.commit()
        self._audit("skill_deleted", f"Skill deleted: {skill.name}", {"skill_id": skill.id})

    def import_skill_json(self, skill_in: SkillCreate, overwrite: bool = False) -> SkillModel:
        existing = self.db.query(SkillModel).filter(SkillModel.id == skill_in.id).first()
        if existing and existing.deleted_at is None and not overwrite:
            raise SkillAlreadyExistsError("Skill already exists")
        if existing:
            skill = self.update_skill(skill_in.id, SkillUpdate(**skill_in.model_dump(exclude={"id"})))
        else:
            skill = self.create_skill(skill_in, audit=False)
        self._audit("skill_imported", f"Skill imported: {skill.name}", {"skill_id": skill.id, "overwrite": overwrite})
        return skill

    def export_skill_json(self, skill_id: str) -> dict:
        return export_skill(self.get_skill(skill_id))

    def get_agent_skills(self, agent_id: str) -> list[SkillModel]:
        agent = self._get_agent(agent_id)
        return self._get_skills_by_ids(agent.skills or [])

    def set_agent_skills(self, agent_id: str, skill_ids: list[str]) -> list[SkillModel]:
        agent = self._get_agent(agent_id)
        skills = self._get_skills_by_ids(skill_ids, require_all=True)
        agent.skills = [skill.id for skill in skills]
        self._sync_agent_skill_rows(agent.id, agent.skills)
        self.db.add(agent)
        self.db.commit()
        self._audit("skill_assigned_to_agent", "Agent skills updated", {"agent_id": agent_id, "skill_ids": agent.skills})
        return skills

    def assign_skill_to_agent(self, agent_id: str, skill_id: str) -> list[SkillModel]:
        agent = self._get_agent(agent_id)
        self.get_skill(skill_id)
        current = list(agent.skills or [])
        if skill_id not in current:
            current.append(skill_id)
        return self.set_agent_skills(agent_id, current)

    def remove_skill_from_agent(self, agent_id: str, skill_id: str) -> list[SkillModel]:
        agent = self._get_agent(agent_id)
        return self.set_agent_skills(agent_id, [sid for sid in (agent.skills or []) if sid != skill_id])

    def get_team_skills(self, team_id: str) -> list[SkillModel]:
        team = self._get_team(team_id)
        return self._get_skills_by_ids(team.skills or [])

    def set_team_skills(self, team_id: str, skill_ids: list[str]) -> list[SkillModel]:
        team = self._get_team(team_id)
        skills = self._get_skills_by_ids(skill_ids, require_all=True)
        team.skills = [skill.id for skill in skills]
        self._sync_team_skill_rows(team.id, team.skills)
        self.db.add(team)
        self.db.commit()
        self._audit("skill_assigned_to_team", "Team skills updated", {"team_id": team_id, "skill_ids": team.skills})
        return skills

    def assign_skill_to_team(self, team_id: str, skill_id: str) -> list[SkillModel]:
        team = self._get_team(team_id)
        self.get_skill(skill_id)
        current = list(team.skills or [])
        if skill_id not in current:
            current.append(skill_id)
        return self.set_team_skills(team_id, current)

    def remove_skill_from_team(self, team_id: str, skill_id: str) -> list[SkillModel]:
        team = self._get_team(team_id)
        return self.set_team_skills(team_id, [sid for sid in (team.skills or []) if sid != skill_id])

    def format_skills_for_prompt(self, agent_skill_ids: Iterable[str], team_skill_ids: Iterable[str] = ()) -> FormattedSkills:
        agent_ids = list(agent_skill_ids or [])
        team_ids = [sid for sid in (team_skill_ids or []) if sid not in agent_ids]
        ordered_ids = agent_ids + team_ids
        skills = self._get_skills_by_ids(ordered_ids)

        if not skills:
            return FormattedSkills(text="", loaded=[], injected=[], truncated=False)

        lines: list[str] = [
            "[AVAILABLE SKILLS]",
            'To load a skill use the standard tool call JSON: {"type": "tool_call", "tool": "skill.use", "arguments": {"skill_id": "<id>"}}',
            "Invoke the relevant skill BEFORE starting the corresponding task.",
            "",
        ]
        loaded: list[dict] = []
        injected: list[dict] = []
        truncated = False

        for skill in skills:
            if len(injected) >= self.max_skills_per_prompt:
                truncated = True
                break
            description = (skill.description or "").replace("\n", " ").strip()
            lines.append(f"- {skill.id} | {skill.name} | {description}")
            item = {"id": skill.id, "name": skill.name}
            loaded.append(item)
            injected.append(item)

        text = "\n".join(lines)
        return FormattedSkills(text=text, loaded=loaded, injected=injected, truncated=truncated)

    def _get_agent(self, agent_id: str) -> AgentModel:
        agent = self.db.query(AgentModel).filter(AgentModel.id == agent_id).first()
        if not agent:
            raise SkillNotFoundError("Agent not found")
        return agent

    def _get_team(self, team_id: str) -> TeamModel:
        team = self.db.query(TeamModel).filter(TeamModel.id == team_id).first()
        if not team:
            raise SkillNotFoundError("Team not found")
        return team

    def _get_skills_by_ids(self, skill_ids: Iterable[str], require_all: bool = False) -> list[SkillModel]:
        unique_ids = list(dict.fromkeys(skill_ids or []))
        if not unique_ids:
            return []
        skills = (
            self.db.query(SkillModel)
            .filter(SkillModel.id.in_(unique_ids), SkillModel.deleted_at.is_(None))
            .all()
        )
        enabled_plugin_ids = {
            plugin.id
            for plugin in self.db.query(PluginModel).filter(
                PluginModel.enabled.is_(True),
                PluginModel.deleted_at.is_(None),
            ).all()
        }
        skills = [
            skill for skill in skills
            if not skill.plugin_id or skill.plugin_id in enabled_plugin_ids
        ]
        by_id = {skill.id: skill for skill in skills}
        if require_all:
            missing = [skill_id for skill_id in unique_ids if skill_id not in by_id]
            if missing:
                raise SkillNotFoundError(f"Skill not found: {missing[0]}")
        return [by_id[skill_id] for skill_id in unique_ids if skill_id in by_id]

    def _sync_agent_skill_rows(self, agent_id: str, skill_ids: list[str]) -> None:
        self.db.query(AgentSkillModel).filter(AgentSkillModel.agent_id == agent_id).delete()
        for skill_id in skill_ids:
            self.db.add(AgentSkillModel(agent_id=agent_id, skill_id=skill_id))

    def _sync_team_skill_rows(self, team_id: str, skill_ids: list[str]) -> None:
        self.db.query(TeamSkillModel).filter(TeamSkillModel.team_id == team_id).delete()
        for skill_id in skill_ids:
            self.db.add(TeamSkillModel(team_id=team_id, skill_id=skill_id))

    def _remove_skill_from_all_associations(self, skill_id: str) -> None:
        for agent in self.db.query(AgentModel).all():
            if skill_id in (agent.skills or []):
                agent.skills = [sid for sid in agent.skills if sid != skill_id]
                self.db.add(agent)
        for team in self.db.query(TeamModel).all():
            if skill_id in (team.skills or []):
                team.skills = [sid for sid in team.skills if sid != skill_id]
                self.db.add(team)
        self.db.query(AgentSkillModel).filter(AgentSkillModel.skill_id == skill_id).delete()
        self.db.query(TeamSkillModel).filter(TeamSkillModel.skill_id == skill_id).delete()

    def _audit(self, event_type: str, summary: str, data: dict) -> None:
        self.db.add(AuditLogModel(
            id=generate_id("audit"),
            execution_id="",
            agent_id="system",
            event_type=event_type,
            risk_level="low",
            summary=summary,
            data=data,
        ))
        self.db.commit()
