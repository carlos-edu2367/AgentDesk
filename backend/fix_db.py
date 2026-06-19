import os
import shutil
from pathlib import Path
from alembic.config import Config
from alembic import command
from app.storage.appdata import get_db_path

# 1. Delete versions
versions_dir = "alembic/versions"
if os.path.exists(versions_dir):
    shutil.rmtree(versions_dir)
os.makedirs(versions_dir, exist_ok=True)

# 2. Delete db
db_path = get_db_path()
if db_path.exists():
    try:
        os.remove(db_path)
        print("Deleted database.")
    except Exception as e:
        print(f"Could not delete db: {e}")

# 3. Generate
try:
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message="Initial schema")
    print("Migration generated.")
except Exception as e:
    print(f"Failed: {e}")
