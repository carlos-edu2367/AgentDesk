# Base Skills Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 17 builtin (base) skills bundled with AgentDesk that seed into the local DB on startup, are clearly distinguished from user skills, and survive upgrades without clobbering user data.

**Architecture:** Base skills live as read-only JSON under `backend/resources/skills/base/`. A new `origin` column on `SkillModel` separates `builtin` from `custom`. A `seed_base_skills(db)` routine runs in the FastAPI lifespan after migrations: it inserts missing builtins, revives soft-deleted builtins, updates builtins whose bundled `version` changed, and never touches `custom` rows. PyInstaller bundles the JSON so it travels with the packaged app.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest, PyInstaller.

---

## Key constraints discovered

- **Skill ID regex:** `skill_[a-z0-9_]+` (enforced in `SkillBase.validate_id`, hyphens normalized to `_`). All base IDs use the `skill_` prefix, e.g. `skill_dev_tdd`.
- **Prompt length:** runtime truncates any prompt > 1200 chars (`SkillService.max_skill_chars_per_item`). Every bundled prompt is ≤ 1200 (verified ≤ 848 in the spec).
- **Migration head:** current head is `b2c3d4e5f6a7`; the new migration's `down_revision` is `"b2c3d4e5f6a7"`.
- **`origin` is read-only to the API:** it is NOT added to `SkillCreate`/`SkillBase`, so users cannot forge `builtin`. Only the seeder sets it.

## File Structure

- Create: `backend/resources/skills/base/skill_*.skill.json` — 17 bundled base skills.
- Create: `backend/app/skills/seeder.py` — `seed_base_skills(db)` + path resolver.
- Create: `backend/alembic/versions/c1d2e3f4a5b6_add_skill_origin.py` — adds `skills.origin`.
- Create: `backend/tests/test_base_skills.py` — catalog validation + seeder behavior.
- Modify: `backend/app/db/models.py:157-169` — add `origin` column to `SkillModel`.
- Modify: `backend/app/domain/schemas.py` (`Skill` response schema ~304) — add read-only `origin` field.
- Modify: `backend/app/skills/exporter.py` — include `origin` in export.
- Modify: `backend/app/main.py` (lifespan) — call `seed_base_skills(db)`.
- Modify: `backend/pyinstaller/agentdesk-backend.spec:22-26` — bundle `resources/`.

---

## The 17 base skill IDs (final, regex-valid)

Engineering: `skill_dev_tdd`, `skill_dev_debugging`, `skill_dev_code_review`, `skill_dev_planning`, `skill_dev_architecture_adr`
Design: `skill_design_critique`, `skill_design_ux_copy`, `skill_design_accessibility`, `skill_design_research_synthesis`
Research: `skill_research_quick`, `skill_research_deep`, `skill_research_fact_check`, `skill_research_summarize`
Writing/PM: `skill_writing_clear`, `skill_report_structured`, `skill_product_brainstorm`, `skill_pm_task_planning`

Prompt content for each is in the design doc (`docs/superpowers/specs/2026-06-22-base-skills-catalog-design.md` §5).

---

## Task 1: Add `origin` to the model + schema + migration

**Files:**
- Modify: `backend/app/db/models.py:157-169`
- Modify: `backend/app/domain/schemas.py` (`Skill` class)
- Modify: `backend/app/skills/exporter.py`
- Create: `backend/alembic/versions/c1d2e3f4a5b6_add_skill_origin.py`

- [ ] **Step 1:** Add column to `SkillModel` after `plugin_id`:

```python
    plugin_id = Column(String, nullable=True)
    origin = Column(String, nullable=False, default="custom", server_default="custom")
```

- [ ] **Step 2:** Add read-only field to the `Skill` response schema (NOT `SkillBase`):

```python
class Skill(SkillBase):
    origin: str = "custom"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 3:** Include `origin` in `export_skill` (`exporter.py`), after `examples`:

```python
        "examples": skill.examples or [],
        "origin": getattr(skill, "origin", "custom"),
```

- [ ] **Step 4:** Create the migration `c1d2e3f4a5b6_add_skill_origin.py`:

```python
"""add skill origin

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f6a7
Create Date: 2026-06-22 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("origin", sa.String(), nullable=False, server_default="custom"))


def downgrade() -> None:
    op.drop_column("skills", "origin")
```

- [ ] **Step 5:** Run migration against a scratch DB to confirm it applies:

Run: `cd backend && python -c "from alembic.config import Config; from alembic import command; c=Config('alembic.ini'); command.upgrade(c,'head')"`
Expected: completes without error (uses AppData DB; harmless).

---

## Task 2: Author the 17 bundled JSON files

**Files:** Create `backend/resources/skills/base/skill_*.skill.json` (17 files).

- [ ] **Step 1:** Create the directory and one file per skill. Each file shape (example `skill_dev_tdd.skill.json`):

```json
{
  "id": "skill_dev_tdd",
  "name": "Test-Driven Development",
  "version": "0.1.0",
  "description": "Use when implementing a feature or bugfix, before writing implementation code.",
  "tags": ["engineering", "testing", "tdd"],
  "prompt": "<prompt text from design doc §5.1>",
  "examples": [
    {"input": "Add a function that validates emails", "behavior": "Write a failing test for one valid and one invalid email first, watch it fail, then implement minimally."}
  ]
}
```

Repeat for all 17, copying `name`/`tags`/`prompt` verbatim from the design doc and adding one realistic `examples` entry each.

- [ ] **Step 2:** Validate every file parses and respects limits:

Run: `cd backend && python -c "import json,glob,re; fs=glob.glob('resources/skills/base/*.skill.json'); [ (lambda d: (json.dumps(d), [print(d['id'],'BAD ID') for _ in [0] if not re.fullmatch(r'skill_[a-z0-9_]+', d['id'])], [print(d['id'],'TOO LONG', len(d['prompt'])) for _ in [0] if len(d['prompt'])>1200]))(json.load(open(f,encoding='utf-8'))) for f in fs ]; print(len(fs),'files ok')"`
Expected: `17 files ok`, no BAD ID / TOO LONG lines.

---

## Task 3: Implement the seeder (TDD)

**Files:**
- Create: `backend/app/skills/seeder.py`
- Create: `backend/tests/test_base_skills.py`

- [ ] **Step 1: Write failing tests** in `backend/tests/test_base_skills.py`:

```python
import json, glob, re
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, SkillModel
from app.skills.seeder import seed_base_skills


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def test_catalog_files_valid():
    files = glob.glob("resources/skills/base/*.skill.json")
    assert len(files) == 17
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        assert re.fullmatch(r"skill_[a-z0-9_]+", d["id"]), d["id"]
        assert len(d["prompt"]) <= 1200
        assert d["name"] and d["description"] and d["tags"]


def test_seed_inserts_all_as_builtin(db):
    result = seed_base_skills(db)
    assert len(result["seeded"]) == 17
    rows = db.query(SkillModel).all()
    assert len(rows) == 17
    assert all(r.origin == "builtin" for r in rows)


def test_seed_is_idempotent(db):
    seed_base_skills(db)
    result2 = seed_base_skills(db)
    assert result2["seeded"] == []
    assert db.query(SkillModel).count() == 17


def test_seed_preserves_custom_skills(db):
    db.add(SkillModel(id="skill_my_custom", name="Mine", version="0.1.0", prompt="x", origin="custom"))
    db.commit()
    seed_base_skills(db)
    mine = db.query(SkillModel).filter_by(id="skill_my_custom").one()
    assert mine.origin == "custom" and mine.prompt == "x"


def test_version_bump_updates_builtin(db):
    seed_base_skills(db)
    row = db.query(SkillModel).filter_by(id="skill_dev_tdd").one()
    row.version = "0.0.1"; row.prompt = "stale"
    db.commit()
    seed_base_skills(db)
    row = db.query(SkillModel).filter_by(id="skill_dev_tdd").one()
    assert row.version == "0.1.0" and row.prompt != "stale"


def test_deleted_builtin_is_revived(db):
    seed_base_skills(db)
    row = db.query(SkillModel).filter_by(id="skill_dev_tdd").one()
    from datetime import datetime
    row.deleted_at = datetime.utcnow()
    db.commit()
    seed_base_skills(db)
    row = db.query(SkillModel).filter_by(id="skill_dev_tdd").one()
    assert row.deleted_at is None
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd backend && python -m pytest tests/test_base_skills.py -q`
Expected: FAIL (ImportError: `seed_base_skills` not defined).

- [ ] **Step 3: Implement `backend/app/skills/seeder.py`:**

```python
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

_CONTENT_FIELDS = ("name", "version", "description", "tags", "prompt", "examples")


def _base_skills_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundle = os.environ.get("AGENTDESK_BUNDLE_DIR", getattr(sys, "_MEIPASS", ""))
        return Path(bundle) / "resources" / "skills" / "base"
    return Path(__file__).resolve().parents[2] / "resources" / "skills" / "base"


def _apply_content(skill: SkillModel, data: dict) -> None:
    skill.name = data["name"]
    skill.version = data.get("version", "0.1.0")
    skill.description = data.get("description", "")
    skill.tags = data.get("tags", [])
    skill.prompt = data["prompt"]
    skill.examples = data.get("examples", [])


def seed_base_skills(db: Session) -> dict:
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
            existing.deleted_at is not None or existing.version != data.get("version", "0.1.0")
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
    return {"seeded": seeded, "updated": updated, "skipped": skipped}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `cd backend && python -m pytest tests/test_base_skills.py -q`
Expected: 6 passed.

---

## Task 4: Wire the seeder into startup

**Files:** Modify `backend/app/main.py` (lifespan).

- [ ] **Step 1:** In the existing lifespan `db` session block (where MCP is registered), add seeding before the MCP call:

```python
    db = database.SessionLocal()
    try:
        from app.skills.seeder import seed_base_skills
        seed_result = seed_base_skills(db)
        logger.info(f"Base skills seeded: {seed_result['seeded']}, updated: {seed_result['updated']}")

        from app.mcp.service import MCPService
        MCPService(db).list_servers()
        logger.info("Cached MCP tools registered.")
    finally:
        db.close()
```

- [ ] **Step 2:** Smoke-test startup wiring with the API client (in-memory DB seeds builtins):

Run: `cd backend && python -m pytest tests/test_base_skills.py -q && python -c "import app.main"`
Expected: tests pass; import has no errors.

---

## Task 5: Bundle resources in PyInstaller

**Files:** Modify `backend/pyinstaller/agentdesk-backend.spec:22-26`.

- [ ] **Step 1:** Add the resources dir to `datas`:

```python
    datas=[
        (str(backend_dir / "alembic.ini"), "."),
        (str(backend_dir / "alembic"), "alembic"),
        (str(backend_dir / "resources"), "resources"),
    ],
```

- [ ] **Step 2:** Add the seeder to `hiddenimports` (dynamic import in lifespan):

```python
        "app.api.routers.logs",
        "app.skills.seeder",
```

---

## Task 6: Full regression + commit

- [ ] **Step 1:** Run the full backend suite:

Run: `cd backend && python -m pytest -q`
Expected: all pass (prior 236 + new base-skills tests).

- [ ] **Step 2:** Commit on `main`:

```bash
git add backend/resources/skills/base backend/app/skills/seeder.py backend/app/db/models.py backend/app/domain/schemas.py backend/app/skills/exporter.py backend/app/main.py backend/alembic/versions/c1d2e3f4a5b6_add_skill_origin.py backend/pyinstaller/agentdesk-backend.spec backend/tests/test_base_skills.py docs/superpowers
git commit -m "feat(skills): ship 17 builtin base skills with startup seeding"
```

---

## Self-Review

- **Spec coverage:** origin column ✓ (T1), 17 bundled JSON ✓ (T2), idempotent upsert + revive + version-update + custom-preserve ✓ (T3), startup hook ✓ (T4), packaging ✓ (T5), audit `skill_seeded` ✓ (T3), exporter origin ✓ (T1), acceptance criteria covered by tests in T3. No API endpoint changes required (spec §6).
- **Placeholder scan:** prompts referenced from design doc §5 (verbatim source exists), all code shown. No TBD/TODO.
- **Type consistency:** `seed_base_skills(db) -> {"seeded","updated","skipped"}` used identically in tests, seeder, and main.py. `origin` default `"custom"` consistent across model, schema, exporter.
- **Frontend builtin labeling** (design §4 UI notes) is intentionally deferred — backend returns `origin` so the UI can adopt it later; not required for acceptance.
```
