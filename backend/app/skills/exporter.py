from app.db.models import SkillModel


def export_skill(skill: SkillModel) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "version": skill.version,
        "description": skill.description,
        "tags": skill.tags or [],
        "prompt": skill.prompt,
        "examples": skill.examples or [],
    }
