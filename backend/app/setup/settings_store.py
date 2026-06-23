from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import AppSettingModel


def get(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.query(AppSettingModel).filter(AppSettingModel.key == key).first()
    return row.value if row else default


def set(db: Session, key: str, value: str) -> None:
    row = db.query(AppSettingModel).filter(AppSettingModel.key == key).first()
    if row:
        row.value = value
    else:
        row = AppSettingModel(key=key, value=value)
        db.add(row)
    db.commit()
