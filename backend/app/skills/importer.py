from app.domain.schemas import SkillCreate


def parse_skill_import(payload: dict) -> SkillCreate:
    return SkillCreate.model_validate(payload)
