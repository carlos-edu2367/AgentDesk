import pytest
from app.storage.appdata import get_appdata_dir, get_db_path

def test_alembic_startup(client):
    """
    Quando o TestClient é criado na fixture `client` (que usa o lifespan), 
    ele roda as migrations do Alembic. 
    Vamos checar se o banco SQLite foi de fato criado e se a tabela de agents existe.
    """
    db_path = get_db_path()
    assert db_path.exists()
    
    # Check tables
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    assert "alembic_version" in tables
    assert "agents" in tables
    assert "providers" in tables
