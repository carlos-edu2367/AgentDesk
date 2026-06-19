from pathlib import Path
from typing import List

from app.tools.errors import InvalidPathError, PathOutOfWorkspaceError


def resolve_safe_path(raw_path: str) -> Path:
    """Resolves and normalizes a path. Raises InvalidPathError if the path is empty."""
    if not raw_path or not raw_path.strip():
        raise InvalidPathError(raw_path, "path cannot be empty")
    try:
        return Path(raw_path).resolve()
    except Exception as exc:
        raise InvalidPathError(raw_path, str(exc)) from exc


def assert_path_in_workspaces(path: str, workspace_paths: List[str]) -> Path:
    """
    Validates that 'path' is inside at least one workspace path.
    Returns the resolved Path on success.
    Raises PathOutOfWorkspaceError if no workspace contains the path.
    Also catches path traversal attempts (../ etc) via Path.resolve().
    """
    target = resolve_safe_path(path)

    if not workspace_paths:
        raise PathOutOfWorkspaceError(path)

    for ws_raw in workspace_paths:
        try:
            workspace = Path(ws_raw).resolve()
            target.relative_to(workspace)
            return target  # Path is inside this workspace
        except ValueError:
            continue

    raise PathOutOfWorkspaceError(path)
