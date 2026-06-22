import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import AuditLogModel, SkillModel
from app.domain.utils import generate_id

logger = logging.getLogger("agentdesk.skills.seeder")


def _base_skills_dir() -> Path:
    """Resolve the bundled base-skills directory, frozen (PyInstaller) or not."""
    if getattr(sys, "frozen", False):
        bundle = os.environ.get("AGENTDESK_BUNDLE_DIR", getattr(sys, "_MEIPASS", ""))
        return Path(bundle) / "resources" / "skills" / "base"
    # backend/app/skills/seeder.py -> parents[2] == backend/
    return Path(__file__).resolve().parents[2] / "resources" / "skills" / "base"


def _apply_content(skill: SkillModel, data: dict) -> None:
    skill.name = data["name"]
    skill.version = data.get("version", "0.1.0")
    skill.description = data.get("description", "")
    skill.tags = data.get("tags", [])
    skill.prompt = data["prompt"]
    skill.examples = data.get("examples", [])


def seed_base_skills(db: Session) -> dict:
    """Idempotently upsert bundled builtin skills into the DB.

    - Missing skill -> insert as origin="builtin".
    - Existing builtin that is soft-deleted or whose bundled version changed ->
      restore content and clear deleted_at.
    - Custom skills (origin="custom") are never touched.
    """
    base_dir = _base_skills_dir()
    seeded: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    if not base_dir.exists():
        logger.warning("Base skills directory not found: %s", base_dir)
        return {"seeded": seeded, "updated": updated, "skipped": skipped}

    for path in sorted(base_dir.glob("*.skill.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = data["id"]
        existing = db.query(SkillModel).filter(SkillModel.id == sid).first()

        if existing is None:
            skill = SkillModel(id=sid, origin="builtin")
            _apply_content(skill, data)
            db.add(skill)
            seeded.append(sid)
        elif existing.origin == "builtin" and (
            existing.deleted_at is not None
            or existing.version != data.get("version", "0.1.0")
        ):
            _apply_content(existing, data)
            existing.deleted_at = None
            existing.updated_at = datetime.utcnow()
            db.add(existing)
            updated.append(sid)
        else:
            skipped.append(sid)

    if seeded or updated:
        db.add(AuditLogModel(
            id=generate_id("audit"),
            execution_id="",
            agent_id="system",
            event_type="skill_seeded",
            risk_level="low",
            summary=f"Base skills seeded: {len(seeded)} new, {len(updated)} updated",
            data={"seeded": seeded, "updated": updated},
        ))

    db.commit()
    logger.info("Base skills: %d seeded, %d updated, %d skipped", len(seeded), len(updated), len(skipped))
    return {"seeded": seeded, "updated": updated, "skipped": skipped}
