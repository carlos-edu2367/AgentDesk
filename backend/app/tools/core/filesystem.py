import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.permissions.path_guard import assert_path_in_workspaces
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

MAX_READ_BYTES = 200_000
MAX_SEARCH_RESULTS = 200
# When reading by line range we must decode the whole file to count/slice lines;
# guard against loading anything pathologically large into memory.
MAX_LINE_READ_BYTES = 5_000_000


class FilesystemListTool(BaseTool):
    name = "filesystem.list"
    description = "Lists files and directories inside a path within an authorized workspace."
    capability = "filesystem_read"
    critical = False
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "Directory path to list.", "required": True}
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")

        workspace_paths = context.get_workspace_paths()
        target = assert_path_in_workspaces(path, workspace_paths)

        if not target.exists():
            raise ToolError("PATH_NOT_FOUND", f"Path '{path}' does not exist")
        if not target.is_dir():
            raise ToolError("NOT_A_DIRECTORY", f"Path '{path}' is not a directory")

        items = []
        try:
            for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                try:
                    stat = entry.stat()
                    items.append({
                        "name": entry.name,
                        "path": str(entry),
                        "type": "file" if entry.is_file() else "directory",
                        "size_bytes": stat.st_size if entry.is_file() else 0,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
                except (PermissionError, OSError):
                    pass
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied reading directory: {exc}") from exc

        return {"path": str(target), "items": items}


class FilesystemReadTool(BaseTool):
    name = "filesystem.read"
    description = (
        "Reads a text file inside an authorized workspace. Pass 'offset' (1-based "
        "start line) and/or 'limit' (number of lines) to read just a slice of a "
        "large file — useful before filesystem.edit, to grab the exact lines to "
        "change without loading the whole file."
    )
    capability = "filesystem_read"
    critical = False
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "File path to read.", "required": True},
        "max_bytes": {"type": "integer", "description": "Maximum bytes to read (whole-file mode).", "default": MAX_READ_BYTES},
        "offset": {"type": "integer", "description": "1-based line number to start reading from."},
        "limit": {"type": "integer", "description": "Number of lines to read from 'offset'."},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")

        offset = arguments.get("offset")
        limit = arguments.get("limit")
        line_mode = offset is not None or limit is not None

        workspace_paths = context.get_workspace_paths()
        target = assert_path_in_workspaces(path, workspace_paths)

        if not target.exists():
            raise ToolError("PATH_NOT_FOUND", f"File '{path}' does not exist")
        if target.is_dir():
            raise ToolError("IS_A_DIRECTORY", f"Path '{path}' is a directory, not a file")

        size_bytes = target.stat().st_size

        if line_mode:
            return self._read_lines(target, size_bytes, offset, limit)

        max_bytes = int(arguments.get("max_bytes", MAX_READ_BYTES))
        max_bytes = min(max_bytes, MAX_READ_BYTES)
        truncated = False

        try:
            raw = target.read_bytes()
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied reading file: {exc}") from exc

        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
            truncated = True

        content = self._decode(raw)
        return {
            "path": str(target),
            "content": content,
            "truncated": truncated,
            "size_bytes": size_bytes,
        }

    def _read_lines(self, target, size_bytes: int, offset, limit) -> Dict[str, Any]:
        if size_bytes > MAX_LINE_READ_BYTES:
            raise ToolError(
                "FILE_TOO_LARGE",
                f"File is {size_bytes} bytes; line-range reads are capped at "
                f"{MAX_LINE_READ_BYTES} bytes",
            )
        try:
            raw = target.read_bytes()
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied reading file: {exc}") from exc

        lines = self._decode(raw).splitlines()
        total_lines = len(lines)

        start = max(1, int(offset)) if offset is not None else 1
        start_idx = start - 1
        if limit is not None and int(limit) > 0:
            window = lines[start_idx:start_idx + int(limit)]
        else:
            window = lines[start_idx:]

        end_idx = start_idx + len(window)
        return {
            "path": str(target),
            "content": "\n".join(window),
            "truncated": end_idx < total_lines,
            "size_bytes": size_bytes,
            "line_offset": start,
            "lines_returned": len(window),
            "total_lines": total_lines,
        }

    def _decode(self, raw: bytes) -> str:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw.decode("latin-1")
            except UnicodeDecodeError:
                raise ToolError("ENCODING_ERROR", "Could not decode file content as text (UTF-8 or Latin-1)")


class FilesystemStatTool(BaseTool):
    name = "filesystem.stat"
    description = "Returns metadata about a file or directory inside an authorized workspace."
    capability = "filesystem_read"
    critical = False
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "Path to inspect.", "required": True}
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")

        workspace_paths = context.get_workspace_paths()
        target = assert_path_in_workspaces(path, workspace_paths)

        if not target.exists():
            return {"path": str(target), "exists": False}

        stat = target.stat()
        return {
            "path": str(target),
            "exists": True,
            "type": "file" if target.is_file() else "directory",
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }


class FilesystemSearchTool(BaseTool):
    name = "filesystem.search"
    description = "Recursively searches for files/directories by name pattern inside an authorized workspace."
    capability = "filesystem_read"
    critical = False
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "Root directory for search.", "required": True},
        "query": {"type": "string", "description": "Name pattern to search (supports * wildcard).", "required": True},
        "max_results": {"type": "integer", "description": "Maximum results to return.", "default": 50},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        query = arguments.get("query", "")
        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")
        if not query:
            raise ToolError("MISSING_QUERY", "Argument 'query' is required")

        max_results = min(int(arguments.get("max_results", 50)), MAX_SEARCH_RESULTS)

        workspace_paths = context.get_workspace_paths()
        target = assert_path_in_workspaces(path, workspace_paths)

        if not target.exists():
            raise ToolError("PATH_NOT_FOUND", f"Path '{path}' does not exist")
        if not target.is_dir():
            raise ToolError("NOT_A_DIRECTORY", f"Path '{path}' is not a directory")

        pattern = query if "*" in query or "?" in query else f"*{query}*"

        results = []
        try:
            for entry in target.rglob("*"):
                if entry.is_symlink():
                    continue
                if fnmatch.fnmatch(entry.name, pattern):
                    try:
                        stat = entry.stat()
                        results.append({
                            "name": entry.name,
                            "path": str(entry),
                            "type": "file" if entry.is_file() else "directory",
                            "size_bytes": stat.st_size if entry.is_file() else 0,
                        })
                        if len(results) >= max_results:
                            break
                    except (PermissionError, OSError):
                        pass
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied during search: {exc}") from exc

        return {
            "path": str(target),
            "query": query,
            "results": results,
        }
