from app.storage.appdata import get_appdata_dir

def test_storage_info(client):
    response = client.get("/api/storage/info")
    assert response.status_code == 200
    data = response.json()
    assert "appdata_path" in data
    assert "database_path" in data

def test_appdata_structure_created(mock_appdata):
    from app.storage.appdata import ensure_appdata_structure
    ensure_appdata_structure()
    
    base_dir = get_appdata_dir()
    assert base_dir == mock_appdata / "AgentDesk"
    assert (base_dir / "config" / "app.config.json").exists()
    assert (base_dir / "database").exists()
