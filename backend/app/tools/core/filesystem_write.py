import os
import shutil
from pathlib import Path
from typing import Any, Dict

from app.permissions.path_guard import assert_path_in_workspaces
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

FILE_WRITE_PREVIEW_BYTES = 2_000


def _check_not_workspace_root(target: Path, context: ToolExecutionContext) -> None:
    """Raises ToolError if target is the root of any workspace."""
    for root in context.get_workspace_roots():
        if target == root:
            raise ToolError("CANNOT_DELETE_ROOT", f"Cannot delete workspace root directory: {target}")


def _check_not_forbidden_system_path(target: Path) -> None:
    """Raises ToolError if target is a known system-critical path."""
    home = Path(os.path.expanduser("~")).resolve()
    if target == home:
        raise ToolError("FORBIDDEN_PATH", f"Cannot delete home directory: {target}")

    if os.name == "nt":
        try:
            system_root = Path(os.environ.get("SystemRoot", "C:\\Windows")).resolve()
            drive_root = system_root.anchor  # e.g. "C:\\"
            forbidden = {
                Path(drive_root).resolve(),
                system_root,
                system_root / "System32",
                system_root / "SysWOW64",
            }
            if target in forbidden:
                raise ToolError("FORBIDDEN_PATH", f"Cannot delete system path: {target}")
        except ToolError:
            raise
        except Exception:
            pass
    else:
        forbidden = {
            Path("/").resolve(), Path("/etc").resolve(), Path("/usr").resolve(),
            Path("/bin").resolve(), Path("/sbin").resolve(), Path("/lib").resolve(),
        }
        if target in forbidden:
            raise ToolError("FORBIDDEN_PATH", f"Cannot delete system path: {target}")


class FilesystemWriteTool(BaseTool):
    name = "filesystem.write"
    description = "Writes content to a file inside an authorized workspace with write permission."
    capability = "filesystem_write"
    critical = True
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "File path to write.", "required": True},
        "content": {"type": "string", "description": "Content to write.", "required": True},
        "mode": {"type": "string", "description": "Write mode: overwrite, append, create_only.", "default": "overwrite"},
        "create_dirs": {"type": "boolean", "description": "Create intermediate directories if missing.", "default": False},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        content = arguments.get("content", "")
        mode = arguments.get("mode", "overwrite")
        create_dirs = bool(arguments.get("create_dirs", False))

        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")
        if mode not in ("overwrite", "append", "create_only"):
            raise ToolError("INVALID_MODE", f"mode must be overwrite, append, or create_only; got '{mode}'")

        workspace_paths = context.get_workspace_paths_with_permission("write")
        target = assert_path_in_workspaces(path, workspace_paths)

        if mode == "create_only" and target.exists():
            raise ToolError("FILE_EXISTS", f"File already exists: {target} (mode=create_only)")

        if not target.parent.exists():
            if create_dirs:
                target.parent.mkdir(parents=True, exist_ok=True)
            else:
                raise ToolError("DIR_NOT_FOUND", f"Parent directory does not exist: {target.parent}")

        try:
            if mode == "append":
                with open(target, "a", encoding="utf-8") as f:
                    f.write(content)
            else:
                target.write_text(content, encoding="utf-8")
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied writing file: {exc}") from exc

        preview = content[:FILE_WRITE_PREVIEW_BYTES]
        return {
            "path": str(target),
            "bytes_written": len(content.encode("utf-8")),
            "mode": mode,
            "preview": preview,
            "content_truncated_in_preview": len(content) > FILE_WRITE_PREVIEW_BYTES,
        }


class FilesystemDeleteTool(BaseTool):
    name = "filesystem.delete"
    description = "Deletes a file or directory inside an authorized workspace with delete permission."
    capability = "filesystem_delete"
    critical = True
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "Path to delete.", "required": True},
        "recursive": {"type": "boolean", "description": "Delete directories recursively.", "default": False},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        recursive = bool(arguments.get("recursive", False))

        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")

        workspace_paths = context.get_workspace_paths_with_permission("delete")
        target = assert_path_in_workspaces(path, workspace_paths)

        _check_not_workspace_root(target, context)
        _check_not_forbidden_system_path(target)

        if not target.exists():
            raise ToolError("PATH_NOT_FOUND", f"Path does not exist: {target}")

        if target.is_dir() and not recursive:
            raise ToolError("IS_A_DIRECTORY", f"Path is a directory; use recursive=true to delete: {target}")

        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                size_bytes = target.stat().st_size
                target.unlink()
                return {"path": str(target), "deleted": True, "type": "file", "size_bytes": size_bytes}
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied deleting path: {exc}") from exc

        return {"path": str(target), "deleted": True, "type": "directory", "recursive": recursive}


class FilesystemMoveTool(BaseTool):
    name = "filesystem.move"
    description = "Moves a file or directory within authorized workspace(s) with write permission."
    capability = "filesystem_write"
    critical = True
    source = "core"
    input_schema = {
        "source_path": {"type": "string", "description": "Source path.", "required": True},
        "target_path": {"type": "string", "description": "Target path.", "required": True},
        "overwrite": {"type": "boolean", "description": "Overwrite target if it exists.", "default": False},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        source_path = arguments.get("source_path", "")
        target_path = arguments.get("target_path", "")
        overwrite = bool(arguments.get("overwrite", False))

        if not source_path:
            raise ToolError("MISSING_SOURCE_PATH", "Argument 'source_path' is required")
        if not target_path:
            raise ToolError("MISSING_TARGET_PATH", "Argument 'target_path' is required")

        workspace_paths = context.get_workspace_paths_with_permission("write")
        source = assert_path_in_workspaces(source_path, workspace_paths)
        target = assert_path_in_workspaces(target_path, workspace_paths)

        if not source.exists():
            raise ToolError("SOURCE_NOT_FOUND", f"Source path does not exist: {source}")

        if target.exists() and not overwrite:
            raise ToolError("TARGET_EXISTS", f"Target already exists: {target} (use overwrite=true)")

        if not target.parent.exists():
            raise ToolError("TARGET_DIR_NOT_FOUND", f"Target parent directory does not exist: {target.parent}")

        try:
            shutil.move(str(source), str(target))
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied moving path: {exc}") from exc

        return {
            "source_path": str(source),
            "target_path": str(target),
            "moved": True,
        }


class FilesystemCopyTool(BaseTool):
    name = "filesystem.copy"
    description = "Copies a file or directory within authorized workspace(s) with read and write permission."
    capability = "filesystem_write"
    critical = True
    source = "core"
    input_schema = {
        "source_path": {"type": "string", "description": "Source path.", "required": True},
        "target_path": {"type": "string", "description": "Target path.", "required": True},
        "overwrite": {"type": "boolean", "description": "Overwrite target if it exists.", "default": False},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        source_path = arguments.get("source_path", "")
        target_path = arguments.get("target_path", "")
        overwrite = bool(arguments.get("overwrite", False))

        if not source_path:
            raise ToolError("MISSING_SOURCE_PATH", "Argument 'source_path' is required")
        if not target_path:
            raise ToolError("MISSING_TARGET_PATH", "Argument 'target_path' is required")

        readable_paths = context.get_workspace_paths()
        writable_paths = context.get_workspace_paths_with_permission("write")

        source = assert_path_in_workspaces(source_path, readable_paths)
        target = assert_path_in_workspaces(target_path, writable_paths)

        if not source.exists():
            raise ToolError("SOURCE_NOT_FOUND", f"Source path does not exist: {source}")

        if target.exists() and not overwrite:
            raise ToolError("TARGET_EXISTS", f"Target already exists: {target} (use overwrite=true)")

        if not target.parent.exists():
            raise ToolError("TARGET_DIR_NOT_FOUND", f"Target parent directory does not exist: {target.parent}")

        try:
            if source.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(str(source), str(target))
            else:
                shutil.copy2(str(source), str(target))
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied copying: {exc}") from exc

        return {
            "source_path": str(source),
            "target_path": str(target),
            "copied": True,
            "type": "directory" if source.is_dir() else "file",
        }
