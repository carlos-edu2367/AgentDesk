from typing import Any, Dict, List

from app.permissions.path_guard import assert_path_in_workspaces
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

EDIT_PREVIEW_BYTES = 2_000
MAX_MULTI_EDITS = 50


def _apply_one_edit(text: str, old: str, new: str, replace_all: bool, index: int) -> tuple[str, int]:
    """Applies a single exact-string edit to `text`, returning (new_text, count).
    Raises ToolError (tagged with the edit index) on any mismatch."""
    if not old:
        raise ToolError("MISSING_OLD_STRING", f"edits[{index}]: old_string is required")
    if old == new:
        raise ToolError("NO_CHANGE", f"edits[{index}]: old_string and new_string are identical")
    count = text.count(old)
    if count == 0:
        raise ToolError("STRING_NOT_FOUND", f"edits[{index}]: old_string not found")
    if count > 1 and not replace_all:
        raise ToolError(
            "STRING_NOT_UNIQUE",
            f"edits[{index}]: old_string appears {count} times; add context to make it "
            f"unique, or set replace_all=true",
        )
    updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    return updated, (count if replace_all else 1)


class FilesystemEditTool(BaseTool):
    name = "filesystem.edit"
    description = (
        "Replaces an exact string in an existing file inside an authorized "
        "workspace. PREFER this over filesystem.write for changes to an existing "
        "file: it does NOT require resending the whole file, so it avoids hitting "
        "the output token limit. 'old_string' must match the file exactly "
        "(including whitespace) and be unique, unless 'replace_all' is true."
    )
    capability = "filesystem_write"
    critical = True
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "File to edit.", "required": True},
        "old_string": {"type": "string", "description": "Exact text to replace.", "required": True},
        "new_string": {"type": "string", "description": "Replacement text.", "required": True},
        "replace_all": {"type": "boolean", "description": "Replace every occurrence instead of requiring uniqueness.", "default": False},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        old = arguments.get("old_string", "")
        new = arguments.get("new_string", "")
        replace_all = bool(arguments.get("replace_all", False))

        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")
        if not old:
            raise ToolError("MISSING_OLD_STRING", "Argument 'old_string' is required")
        if old == new:
            raise ToolError("NO_CHANGE", "old_string and new_string are identical; nothing to do")

        workspace_paths = context.get_workspace_paths_with_permission("write")
        target = assert_path_in_workspaces(path, workspace_paths)

        if not target.exists():
            raise ToolError("PATH_NOT_FOUND", f"File '{path}' does not exist")
        if target.is_dir():
            raise ToolError("IS_A_DIRECTORY", f"Path '{path}' is a directory, not a file")

        try:
            text = target.read_text(encoding="utf-8")
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied reading file: {exc}") from exc
        except UnicodeDecodeError:
            raise ToolError("ENCODING_ERROR", "Could not decode file content as UTF-8 text")

        count = text.count(old)
        if count == 0:
            raise ToolError("STRING_NOT_FOUND", "old_string was not found in the file")
        if count > 1 and not replace_all:
            raise ToolError(
                "STRING_NOT_UNIQUE",
                f"old_string appears {count} times; include more surrounding context "
                f"to make it unique, or set replace_all=true",
            )

        updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
        replacements = count if replace_all else 1

        try:
            target.write_text(updated, encoding="utf-8")
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied writing file: {exc}") from exc

        return {
            "path": str(target),
            "replacements": replacements,
            "new_preview": new[:EDIT_PREVIEW_BYTES],
            "preview_truncated": len(new) > EDIT_PREVIEW_BYTES,
        }


class FilesystemMultiEditTool(BaseTool):
    name = "filesystem.multi_edit"
    description = (
        "Applies several exact-string edits to a single file in one atomic call. "
        "Edits run in order, each on the result of the previous one. It's "
        "all-or-nothing: if ANY edit fails to match, NO change is written. Prefer "
        "this over multiple filesystem.edit calls when changing several spots in "
        "the same file."
    )
    capability = "filesystem_write"
    critical = True
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "File to edit.", "required": True},
        "edits": {
            "type": "array",
            "description": "Ordered list of {old_string, new_string, replace_all?} edits.",
            "required": True,
        },
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        edits = arguments.get("edits")

        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")
        if not isinstance(edits, list) or not edits:
            raise ToolError("MISSING_EDITS", "Argument 'edits' must be a non-empty array")
        if len(edits) > MAX_MULTI_EDITS:
            raise ToolError("TOO_MANY_EDITS", f"At most {MAX_MULTI_EDITS} edits per call")

        workspace_paths = context.get_workspace_paths_with_permission("write")
        target = assert_path_in_workspaces(path, workspace_paths)

        if not target.exists():
            raise ToolError("PATH_NOT_FOUND", f"File '{path}' does not exist")
        if target.is_dir():
            raise ToolError("IS_A_DIRECTORY", f"Path '{path}' is a directory, not a file")

        try:
            text = target.read_text(encoding="utf-8")
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied reading file: {exc}") from exc
        except UnicodeDecodeError:
            raise ToolError("ENCODING_ERROR", "Could not decode file content as UTF-8 text")

        # Apply all edits in memory first; only persist if every one succeeds.
        per_edit: List[int] = []
        updated = text
        for i, edit in enumerate(edits):
            if not isinstance(edit, dict):
                raise ToolError("INVALID_EDIT", f"edits[{i}] must be an object")
            updated, count = _apply_one_edit(
                updated,
                edit.get("old_string", ""),
                edit.get("new_string", ""),
                bool(edit.get("replace_all", False)),
                i,
            )
            per_edit.append(count)

        try:
            target.write_text(updated, encoding="utf-8")
        except PermissionError as exc:
            raise ToolError("PERMISSION_DENIED", f"Permission denied writing file: {exc}") from exc

        return {
            "path": str(target),
            "edits_applied": len(edits),
            "replacements_per_edit": per_edit,
            "total_replacements": sum(per_edit),
        }
