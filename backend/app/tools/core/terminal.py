import asyncio
import os
import time
from typing import Any, Dict

from app.permissions.path_guard import assert_path_in_workspaces
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

TERMINAL_DEFAULT_TIMEOUT = 60
TERMINAL_MAX_TIMEOUT = 300
STDOUT_PREVIEW_BYTES = 4_000
STDERR_PREVIEW_BYTES = 2_000


class TerminalExecTool(BaseTool):
    name = "terminal.exec"
    description = "Executes a shell command in a working directory inside an authorized workspace with execute permission."
    capability = "terminal"
    critical = True
    source = "core"
    input_schema = {
        "command": {"type": "string", "description": "Command to execute.", "required": True},
        "cwd": {"type": "string", "description": "Working directory (must be inside an authorized workspace).", "required": True},
        "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (max 300).", "default": 60},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        command = arguments.get("command", "")
        cwd = arguments.get("cwd", "")
        timeout_seconds = min(int(arguments.get("timeout_seconds", TERMINAL_DEFAULT_TIMEOUT)), TERMINAL_MAX_TIMEOUT)

        if not command:
            raise ToolError("MISSING_COMMAND", "Argument 'command' is required")
        if not cwd:
            raise ToolError("MISSING_CWD", "Argument 'cwd' is required - never execute without a working directory")

        workspace_paths = context.get_workspace_paths_with_permission("execute")
        target_cwd = assert_path_in_workspaces(cwd, workspace_paths)

        if not target_cwd.exists():
            raise ToolError("CWD_NOT_FOUND", f"Working directory does not exist: {cwd}")
        if not target_cwd.is_dir():
            raise ToolError("CWD_NOT_DIRECTORY", f"Working directory is not a directory: {cwd}")

        start_ms = int(time.monotonic() * 1000)

        try:
            if os.name == "nt":
                proc = await asyncio.create_subprocess_shell(
                    command,
                    cwd=str(target_cwd),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    cwd=str(target_cwd),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                duration_ms = int(time.monotonic() * 1000) - start_ms
                raise ToolError(
                    "TERMINAL_TIMEOUT",
                    f"Command timed out after {timeout_seconds}s: {command}"
                )

        except ToolError:
            raise
        except Exception as exc:
            raise ToolError("TERMINAL_ERROR", f"Failed to execute command: {exc}") from exc

        duration_ms = int(time.monotonic() * 1000) - start_ms

        stdout_full = stdout_bytes.decode("utf-8", errors="replace")
        stderr_full = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = proc.returncode if proc.returncode is not None else -1

        stdout_preview = stdout_full[:STDOUT_PREVIEW_BYTES]
        stderr_preview = stderr_full[:STDERR_PREVIEW_BYTES]

        return {
            "command": command,
            "cwd": str(target_cwd),
            "exit_code": exit_code,
            "stdout": stdout_preview,
            "stderr": stderr_preview,
            "stdout_truncated": len(stdout_full) > STDOUT_PREVIEW_BYTES,
            "stderr_truncated": len(stderr_full) > STDERR_PREVIEW_BYTES,
            "duration_ms": duration_ms,
        }
