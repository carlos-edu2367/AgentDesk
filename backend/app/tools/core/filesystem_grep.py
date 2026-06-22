import fnmatch
import re
from typing import Any, Dict

from app.permissions.path_guard import assert_path_in_workspaces
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

MAX_GREP_RESULTS = 500
MAX_GREP_FILE_BYTES = 2_000_000  # skip files larger than this
MAX_LINE_CHARS = 500             # truncate very long matching lines


class FilesystemGrepTool(BaseTool):
    name = "filesystem.grep"
    description = (
        "Searches file CONTENTS by regular expression, recursively, inside an "
        "authorized workspace. Use this to locate code/text (e.g. a class or "
        "function) without reading whole files. Returns matching lines with their "
        "file path and line number. Filter which files are scanned with 'glob' "
        "(e.g. '*.js')."
    )
    capability = "filesystem_read"
    critical = False
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "Root directory to search in.", "required": True},
        "pattern": {"type": "string", "description": "Regular expression to match against each line.", "required": True},
        "glob": {"type": "string", "description": "Filename filter (e.g. '*.js'). Default: all files.", "default": "*"},
        "case_insensitive": {"type": "boolean", "description": "Case-insensitive match.", "default": False},
        "max_results": {"type": "integer", "description": "Maximum matches to return.", "default": 100},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        pattern = arguments.get("pattern", "")
        glob = arguments.get("glob", "*") or "*"
        case_insensitive = bool(arguments.get("case_insensitive", False))
        max_results = min(int(arguments.get("max_results", 100)), MAX_GREP_RESULTS)

        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")
        if not pattern:
            raise ToolError("MISSING_PATTERN", "Argument 'pattern' is required")

        try:
            regex = re.compile(pattern, re.IGNORECASE if case_insensitive else 0)
        except re.error as exc:
            raise ToolError("INVALID_PATTERN", f"Invalid regular expression: {exc}") from exc

        workspace_paths = context.get_workspace_paths()
        target = assert_path_in_workspaces(path, workspace_paths)

        if not target.exists():
            raise ToolError("PATH_NOT_FOUND", f"Path '{path}' does not exist")
        if not target.is_dir():
            raise ToolError("NOT_A_DIRECTORY", f"Path '{path}' is not a directory")

        results = []
        truncated = False

        try:
            for entry in target.rglob("*"):
                if len(results) >= max_results:
                    truncated = True
                    break
                if entry.is_symlink() or not entry.is_file():
                    continue
                if not fnmatch.fnmatch(entry.name, glob):
                    continue
                try:
                    if entry.stat().st_size > MAX_GREP_FILE_BYTES:
                        continue
                    raw = entry.read_bytes()
                except (PermissionError, OSError):
                    continue
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue  # skip binary / non-text files

                for line_no, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        results.append({
                            "path": str(entry),
                            "line": line_no,
                            "text": line[:MAX_LINE_CHARS],
                        })
                        if len(results) >= max_results:
                            truncated = True
                            break
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied during search: {exc}") from exc

        return {
            "path": str(target),
            "pattern": pattern,
            "count": len(results),
            "truncated": truncated,
            "results": results,
        }
