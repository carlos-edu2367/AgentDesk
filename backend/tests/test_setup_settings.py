from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.models import Base
from app.setup import settings_store


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_get_missing_returns_default():
    db = _session()
    assert settings_store.get(db, "onboarding_completed", "false") == "false"


def test_set_then_get_roundtrip():
    db = _session()
    settings_store.set(db, "onboarding_completed", "true")
    assert settings_store.get(db, "onboarding_completed") == "true"


def test_set_is_idempotent_upsert():
    db = _session()
    settings_store.set(db, "k", "a")
    settings_store.set(db, "k", "b")
    assert settings_store.get(db, "k") == "b"
