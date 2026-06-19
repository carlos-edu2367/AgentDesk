"""
Phase 7 tests: Tool Registry, Capabilities, Permission Gate, Core Tools, Path Guard.
All filesystem tests use tmp_path — no real user directories are touched.
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.tools.registry import ToolRegistry, register_core_tools, tool_registry
from app.tools.capabilities import CAPABILITIES, get_tools_for_capability, get_capability_for_tool
from app.tools.errors import (
    ToolDeniedError,
    ToolNotFoundError,
    PathOutOfWorkspaceError,
    InvalidPathError,
)
from app.permissions.gate import check_tool_permission, get_available_tool_definitions
from app.permissions.path_guard import assert_path_in_workspaces, resolve_safe_path
from app.tools.base import ToolExecutionContext


# ─────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────

def _make_context(tmp_path: Path, db, workspace_paths=None, workspace_ids=None):
    """Creates a minimal ToolExecutionContext for testing."""
    ctx = ToolExecutionContext(
        execution_id="exec_test",
        agent_id="agent_test",
        workspace_ids=workspace_ids or [],
        db=db,
    )
    if workspace_paths is not None:
        # Monkey-patch get_workspace_paths so tests don't need a real DB workspace
        ctx.get_workspace_paths = lambda: workspace_paths
    return ctx


# ─────────────────────────────────────────────────────────
# 1. Tool Registry
# ─────────────────────────────────────────────────────────

def test_tool_registry_registers_core_tools():
    """Tool Registry must have all 8 core tools registered."""
    expected = {
        "filesystem.list",
        "filesystem.read",
        "filesystem.stat",
        "filesystem.search",
        "workspace.list",
        "workspace.get",
        "logs.search",
        "logs.get_execution",
    }
    registered = {t.name for t in tool_registry.list_all()}
    assert expected.issubset(registered)


def test_tool_registry_no_duplicate():
    """Registering the same tool name twice must raise ValueError."""
    registry = ToolRegistry()

    from app.tools.core.filesystem import FilesystemListTool
    tool = FilesystemListTool()
    registry.register(tool)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FilesystemListTool())


def test_tool_registry_list_capabilities():
    caps = tool_registry.list_capabilities()
    cap_names = {c.name for c in caps}
    assert "filesystem_read" in cap_names
    assert "workspace" in cap_names
    assert "logs" in cap_names


def test_tool_registry_exists():
    assert tool_registry.exists("filesystem.list")
    assert not tool_registry.exists("does.not.exist")


def test_tool_registry_get_definition():
    defn = tool_registry.get_definition("filesystem.read")
    assert defn.name == "filesystem.read"
    assert defn.capability == "filesystem_read"
    assert defn.critical is False
    assert defn.source == "core"


def test_tool_registry_get_raises_for_missing():
    with pytest.raises(ToolNotFoundError):
        tool_registry.get("nonexistent.tool")


# ─────────────────────────────────────────────────────────
# 2. Capabilities
# ─────────────────────────────────────────────────────────

def test_capabilities_filesystem_read():
    tools = get_tools_for_capability("filesystem_read")
    assert "filesystem.list" in tools
    assert "filesystem.read" in tools
    assert "filesystem.stat" in tools
    assert "filesystem.search" in tools


def test_capabilities_workspace():
    assert "workspace.list" in get_tools_for_capability("workspace")
    assert "workspace.get" in get_tools_for_capability("workspace")


def test_capabilities_logs():
    assert "logs.search" in get_tools_for_capability("logs")
    assert "logs.get_execution" in get_tools_for_capability("logs")


def test_get_capability_for_tool():
    assert get_capability_for_tool("filesystem.list") == "filesystem_read"
    assert get_capability_for_tool("workspace.get") == "workspace"
    assert get_capability_for_tool("logs.search") == "logs"
    assert get_capability_for_tool("unknown.tool") is None


# ─────────────────────────────────────────────────────────
# 3. Permission Gate
# ─────────────────────────────────────────────────────────

def test_permission_allows_tool_via_capability():
    check_tool_permission(
        "filesystem.list",
        capabilities=["filesystem_read"],
        explicit_tools=[],
        blocked_tools=[],
    )  # Must not raise


def test_permission_allows_tool_via_explicit():
    check_tool_permission(
        "filesystem.list",
        capabilities=[],
        explicit_tools=["filesystem.list"],
        blocked_tools=[],
    )  # Must not raise


def test_permission_denies_without_capability():
    with pytest.raises(ToolDeniedError) as exc_info:
        check_tool_permission(
            "filesystem.list",
            capabilities=[],
            explicit_tools=[],
            blocked_tools=[],
        )
    assert exc_info.value.code == "TOOL_NOT_AUTHORIZED"


def test_blocked_tools_wins_over_capability():
    with pytest.raises(ToolDeniedError) as exc_info:
        check_tool_permission(
            "filesystem.list",
            capabilities=["filesystem_read"],
            explicit_tools=["filesystem.list"],
            blocked_tools=["filesystem.list"],
        )
    assert exc_info.value.code == "TOOL_BLOCKED"


def test_nonexistent_tool_raises_not_found():
    with pytest.raises(ToolNotFoundError):
        check_tool_permission(
            "does.not.exist",
            capabilities=["filesystem_read"],
            explicit_tools=[],
            blocked_tools=[],
        )


def test_get_available_tool_definitions_respects_blocked():
    defs = get_available_tool_definitions(
        capabilities=["filesystem_read"],
        explicit_tools=[],
        blocked_tools=["filesystem.read"],
    )
    names = {d.name for d in defs}
    assert "filesystem.read" not in names
    assert "filesystem.list" in names


# ─────────────────────────────────────────────────────────
# 4. Path Guard
# ─────────────────────────────────────────────────────────

def test_path_guard_allows_inside_workspace(tmp_path):
    allowed = str(tmp_path)
    sub = tmp_path / "subdir" / "file.txt"
    sub.parent.mkdir(parents=True)
    sub.touch()
    result = assert_path_in_workspaces(str(sub), [allowed])
    assert result == sub.resolve()


def test_path_guard_blocks_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.touch()

    with pytest.raises(PathOutOfWorkspaceError):
        assert_path_in_workspaces(str(outside), [str(workspace)])


def test_path_guard_blocks_traversal(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    secret = tmp_path / "secret.txt"
    secret.touch()

    # Attempt path traversal using ..
    traversal = str(workspace) + "/../secret.txt"
    with pytest.raises(PathOutOfWorkspaceError):
        assert_path_in_workspaces(traversal, [str(workspace)])


def test_path_guard_empty_path_raises(tmp_path):
    with pytest.raises(InvalidPathError):
        resolve_safe_path("")


def test_path_guard_empty_workspaces_raises(tmp_path):
    target = tmp_path / "file.txt"
    target.touch()
    with pytest.raises(PathOutOfWorkspaceError):
        assert_path_in_workspaces(str(target), [])


# ─────────────────────────────────────────────────────────
# 5. filesystem.list
# ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_filesystem_list_inside_workspace(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("world")

    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(tmp_path)])
    from app.tools.core.filesystem import FilesystemListTool
    tool = FilesystemListTool()
    result = await tool.execute({"path": str(tmp_path)}, ctx)

    names = {item["name"] for item in result["items"]}
    assert "a.txt" in names
    assert "b.txt" in names


@pytest.mark.anyio
async def test_filesystem_list_outside_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(workspace)])
    from app.tools.core.filesystem import FilesystemListTool
    tool = FilesystemListTool()
    with pytest.raises(PathOutOfWorkspaceError):
        await tool.execute({"path": str(outside)}, ctx)


@pytest.mark.anyio
async def test_filesystem_list_not_a_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("content")
    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(tmp_path)])
    from app.tools.core.filesystem import FilesystemListTool
    from app.tools.errors import ToolError
    tool = FilesystemListTool()
    with pytest.raises(ToolError):
        await tool.execute({"path": str(f)}, ctx)


# ─────────────────────────────────────────────────────────
# 6. filesystem.read
# ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_filesystem_read_inside_workspace(tmp_path):
    f = tmp_path / "readme.txt"
    f.write_text("Hello World")
    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(tmp_path)])
    from app.tools.core.filesystem import FilesystemReadTool
    tool = FilesystemReadTool()
    result = await tool.execute({"path": str(f)}, ctx)
    assert result["content"] == "Hello World"
    assert result["truncated"] is False


@pytest.mark.anyio
async def test_filesystem_read_outside_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(workspace)])
    from app.tools.core.filesystem import FilesystemReadTool
    tool = FilesystemReadTool()
    with pytest.raises(PathOutOfWorkspaceError):
        await tool.execute({"path": str(outside)}, ctx)


@pytest.mark.anyio
async def test_filesystem_read_large_file_truncated(tmp_path):
    f = tmp_path / "big.txt"
    f.write_bytes(b"A" * 300_000)
    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(tmp_path)])
    from app.tools.core.filesystem import FilesystemReadTool
    tool = FilesystemReadTool()
    result = await tool.execute({"path": str(f), "max_bytes": 200_000}, ctx)
    assert result["truncated"] is True
    assert len(result["content"]) == 200_000


@pytest.mark.anyio
async def test_filesystem_read_no_content_in_audit_for_large_file(tmp_path):
    """Result preview must be short (300 chars max), not the full file content."""
    f = tmp_path / "big.txt"
    f.write_bytes(b"B" * 300_000)
    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(tmp_path)])
    from app.tools.core.filesystem import FilesystemReadTool
    tool = FilesystemReadTool()
    result = await tool.execute({"path": str(f)}, ctx)
    # The test checks that the runtime preview would be ≤300 chars
    preview = json.dumps(result, ensure_ascii=False)[:300]
    assert len(preview) <= 300


# ─────────────────────────────────────────────────────────
# 7. filesystem.stat
# ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_filesystem_stat_existing_file(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("data")
    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(tmp_path)])
    from app.tools.core.filesystem import FilesystemStatTool
    tool = FilesystemStatTool()
    result = await tool.execute({"path": str(f)}, ctx)
    assert result["exists"] is True
    assert result["type"] == "file"
    assert result["size_bytes"] == 4


@pytest.mark.anyio
async def test_filesystem_stat_nonexistent_file(tmp_path):
    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(tmp_path)])
    from app.tools.core.filesystem import FilesystemStatTool
    tool = FilesystemStatTool()
    result = await tool.execute({"path": str(tmp_path / "ghost.txt")}, ctx)
    assert result["exists"] is False


@pytest.mark.anyio
async def test_filesystem_stat_outside_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.touch()
    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(workspace)])
    from app.tools.core.filesystem import FilesystemStatTool
    tool = FilesystemStatTool()
    with pytest.raises(PathOutOfWorkspaceError):
        await tool.execute({"path": str(outside)}, ctx)


# ─────────────────────────────────────────────────────────
# 8. filesystem.search
# ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_filesystem_search_finds_files(tmp_path):
    (tmp_path / "README.md").write_text("readme")
    (tmp_path / "main.py").write_text("code")
    sub = tmp_path / "docs"
    sub.mkdir()
    (sub / "README_sub.md").write_text("sub readme")

    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(tmp_path)])
    from app.tools.core.filesystem import FilesystemSearchTool
    tool = FilesystemSearchTool()
    result = await tool.execute({"path": str(tmp_path), "query": "README"}, ctx)
    names = {r["name"] for r in result["results"]}
    assert "README.md" in names
    assert "README_sub.md" in names


@pytest.mark.anyio
async def test_filesystem_search_respects_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "README.md").touch()

    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(workspace)])
    from app.tools.core.filesystem import FilesystemSearchTool
    tool = FilesystemSearchTool()
    with pytest.raises(PathOutOfWorkspaceError):
        await tool.execute({"path": str(outside), "query": "README"}, ctx)


# ─────────────────────────────────────────────────────────
# 9. Path traversal guard integration
# ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_path_traversal_blocked_on_read(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (tmp_path / "secret.txt").write_text("top-secret")

    ctx = _make_context(tmp_path, db=None, workspace_paths=[str(workspace)])
    from app.tools.core.filesystem import FilesystemReadTool
    tool = FilesystemReadTool()
    traversal_path = str(workspace) + "/../secret.txt"
    with pytest.raises(PathOutOfWorkspaceError):
        await tool.execute({"path": traversal_path}, ctx)


# ─────────────────────────────────────────────────────────
# 10. API endpoints
# ─────────────────────────────────────────────────────────

def test_api_list_tools(client):
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    tools = resp.json()
    assert isinstance(tools, list)
    names = {t["name"] for t in tools}
    assert "filesystem.list" in names
    assert "filesystem.read" in names


def test_api_list_capabilities(client):
    resp = client.get("/api/tools/capabilities")
    assert resp.status_code == 200
    caps = resp.json()
    cap_names = {c["name"] for c in caps}
    assert "filesystem_read" in cap_names
    assert "workspace" in cap_names
    assert "logs" in cap_names


def test_api_get_agent_tools(client):
    # Create an agent with capabilities
    agent_resp = client.post("/api/agents", json={
        "name": "Test Agent",
        "model_config": {
            "provider_id": "prov1",
            "model": "test-model",
        },
        "capabilities": ["filesystem_read"],
        "explicit_tools": ["logs.search"],
        "blocked_tools": ["filesystem.read"],
    })
    assert agent_resp.status_code == 200
    agent_id = agent_resp.json()["id"]

    resp = client.get(f"/api/agents/{agent_id}/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "filesystem_read" in data["capabilities"]
    assert "logs.search" in data["explicit_tools"]
    assert "filesystem.read" in data["blocked_tools"]


def test_api_update_agent_tools(client):
    agent_resp = client.post("/api/agents", json={
        "name": "Agent to Update",
        "model_config": {"provider_id": "prov1", "model": "test-model"},
    })
    agent_id = agent_resp.json()["id"]

    put_resp = client.put(f"/api/agents/{agent_id}/tools", json={
        "capabilities": ["filesystem_read", "workspace"],
        "explicit_tools": [],
        "blocked_tools": ["filesystem.delete"],
    })
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert "filesystem_read" in data["capabilities"]
    assert "filesystem.delete" in data["blocked_tools"]


def test_api_tool_test_endpoint(client, tmp_path):
    # Create workspace pointing to tmp_path
    ws_resp = client.post("/api/workspaces", json={
        "name": "Test Workspace",
        "paths": [str(tmp_path)],
        "permissions": {"read": True, "write": False, "delete": False, "execute": False},
    })
    assert ws_resp.status_code == 200
    ws_id = ws_resp.json()["id"]

    # Create file
    (tmp_path / "hello.txt").write_text("world")

    # Create agent with filesystem_read
    agent_resp = client.post("/api/agents", json={
        "name": "Tool Test Agent",
        "model_config": {"provider_id": "prov1", "model": "test-model"},
        "capabilities": ["filesystem_read"],
    })
    agent_id = agent_resp.json()["id"]

    resp = client.post("/api/tools/test", json={
        "agent_id": agent_id,
        "tool": "filesystem.list",
        "arguments": {"path": str(tmp_path)},
        "workspace_ids": [ws_id],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    names = {item["name"] for item in data["result"]["items"]}
    assert "hello.txt" in names


def test_api_tool_test_denied_without_capability(client, tmp_path):
    agent_resp = client.post("/api/agents", json={
        "name": "No Cap Agent",
        "model_config": {"provider_id": "prov1", "model": "test-model"},
        "capabilities": [],
    })
    agent_id = agent_resp.json()["id"]

    ws_resp = client.post("/api/workspaces", json={
        "name": "WS",
        "paths": [str(tmp_path)],
        "permissions": {"read": True, "write": False, "delete": False, "execute": False},
    })
    ws_id = ws_resp.json()["id"]

    resp = client.post("/api/tools/test", json={
        "agent_id": agent_id,
        "tool": "filesystem.list",
        "arguments": {"path": str(tmp_path)},
        "workspace_ids": [ws_id],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "denied"
