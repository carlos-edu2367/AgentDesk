import glob
import json
import re
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, SkillModel
from app.skills.seeder import seed_base_skills


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


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
    assert result2["updated"] == []
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
    row.version = "0.0.1"
    row.prompt = "stale"
    db.commit()
    result = seed_base_skills(db)
    assert "skill_dev_tdd" in result["updated"]
    row = db.query(SkillModel).filter_by(id="skill_dev_tdd").one()
    assert row.version == "0.1.0" and row.prompt != "stale"


def test_deleted_builtin_is_revived(db):
    seed_base_skills(db)
    row = db.query(SkillModel).filter_by(id="skill_dev_tdd").one()
    row.deleted_at = datetime.utcnow()
    db.commit()
    seed_base_skills(db)
    row = db.query(SkillModel).filter_by(id="skill_dev_tdd").one()
    assert row.deleted_at is None
