from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError


class SkillUseTool(BaseTool):
    name = "skill.use"
    description = "Load the full instructions for a skill by its ID. Call this when the index lists a skill relevant to your current task."
    capability = "skill_control"
    critical = False
    source = "core"
    input_schema = {
        "type": "object",
        "properties": {
            "skill_id": {"type": "string", "description": "The ID of the skill to load"}
        },
        "required": ["skill_id"],
    }
    output_schema = {
        "skill_id": "string",
        "name": "string",
        "prompt": "string",
    }

    async def execute(self, arguments: dict, context: ToolExecutionContext) -> dict:
        from app.skills.service import SkillService
        from app.skills.errors import SkillNotFoundError

        skill_id = str(arguments.get("skill_id") or "").strip()
        if not skill_id:
            raise ToolError("INVALID_ARGUMENTS", "skill_id is required")

        try:
            skill = SkillService(context.db).get_skill(skill_id)
        except SkillNotFoundError:
            raise ToolError("SKILL_NOT_FOUND", f"Skill '{skill_id}' not found")

        # Verify the skill is assigned to this agent or the active team.
        from app.db.repositories.registry import agent_repo, team_repo
        agent_model = agent_repo.get(context.db, id=context.agent_id)
        agent_skills = list(agent_model.skills or []) if agent_model else []

        team_skills: list[str] = []
        team_id = context.extra.get("team_id")
        if team_id:
            team_model = team_repo.get(context.db, id=team_id)
            team_skills = list(team_model.skills or []) if team_model else []

        if skill_id not in agent_skills and skill_id not in team_skills:
            raise ToolError("SKILL_NOT_FOUND", f"Skill '{skill_id}' is not available to this agent")

        return {
            "skill_id": skill.id,
            "name": skill.name,
            "prompt": skill.prompt or "",
        }
