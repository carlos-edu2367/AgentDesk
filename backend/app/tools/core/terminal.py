import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict

from app.permissions.path_guard import assert_path_in_workspaces
from app.storage.appdata import get_appdata_dir
from app.domain.utils import generate_id
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError

TERMINAL_DEFAULT_TIMEOUT = 60
TERMINAL_MAX_TIMEOUT = 300
STDOUT_PREVIEW_BYTES = 4_000
STDERR_PREVIEW_BYTES = 2_000
POLL_TAIL_BYTES = 8_000


# Registry of background processes spawned by terminal.exec, keyed by a generated
# process_id. Lives at module scope so it survives across tool calls within the
# same server process. terminal.poll reads/kills them.
_BACKGROUND: Dict[str, Dict[str, Any]] = {}


def _bg_log_dir() -> Path:
    d = get_appdata_dir() / "temp" / "executions" / "terminal"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tail(path: Path, max_bytes: int) -> tuple[str, bool]:
    """Returns (text, truncated) reading at most the last max_bytes of a file."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read()
        return data.decode("utf-8", errors="replace"), size > max_bytes
    except FileNotFoundError:
        return "", False


class TerminalExecTool(BaseTool):
    name = "terminal.exec"
    description = (
        "Executes a shell command in a working directory inside an authorized "
        "workspace with execute permission. Set background=true for long-running "
        "processes (dev servers, watchers): it returns a process_id immediately "
        "without blocking; read its output later with terminal.poll."
    )
    capability = "terminal"
    critical = True
    source = "core"
    input_schema = {
        "command": {"type": "string", "description": "Command to execute.", "required": True},
        "cwd": {"type": "string", "description": "Working directory (must be inside an authorized workspace).", "required": True},
        "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (max 300). Foreground only.", "default": 60},
        "background": {"type": "boolean", "description": "Run detached and return a process_id immediately.", "default": False},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        command = arguments.get("command", "")
        cwd = arguments.get("cwd", "")
        background = bool(arguments.get("background", False))
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

        if background:
            return await self._run_background(command, target_cwd)

        return await self._run_foreground(command, target_cwd, timeout_seconds)

    async def _run_foreground(self, command: str, target_cwd: Path, timeout_seconds: int) -> Dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        try:
            proc = await asyncio.create_subprocess_shell(
                command, cwd=str(target_cwd),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
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
                raise ToolError("TERMINAL_TIMEOUT", f"Command timed out after {timeout_seconds}s: {command}")
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError("TERMINAL_ERROR", f"Failed to execute command: {exc}") from exc

        duration_ms = int(time.monotonic() * 1000) - start_ms
        stdout_full = stdout_bytes.decode("utf-8", errors="replace")
        stderr_full = stderr_bytes.decode("utf-8", errors="replace")
        return {
            "command": command,
            "cwd": str(target_cwd),
            "exit_code": proc.returncode if proc.returncode is not None else -1,
            "stdout": stdout_full[:STDOUT_PREVIEW_BYTES],
            "stderr": stderr_full[:STDERR_PREVIEW_BYTES],
            "stdout_truncated": len(stdout_full) > STDOUT_PREVIEW_BYTES,
            "stderr_truncated": len(stderr_full) > STDERR_PREVIEW_BYTES,
            "duration_ms": duration_ms,
            "background": False,
        }

    async def _run_background(self, command: str, target_cwd: Path) -> Dict[str, Any]:
        process_id = generate_id("proc")
        log_dir = _bg_log_dir()
        stdout_path = log_dir / f"{process_id}.out"
        stderr_path = log_dir / f"{process_id}.err"

        try:
            out_f = open(stdout_path, "wb")
            err_f = open(stderr_path, "wb")
            proc = await asyncio.create_subprocess_shell(
                command, cwd=str(target_cwd), stdout=out_f, stderr=err_f,
            )
        except Exception as exc:
            raise ToolError("TERMINAL_ERROR", f"Failed to start background command: {exc}") from exc

        _BACKGROUND[process_id] = {
            "proc": proc,
            "command": command,
            "cwd": str(target_cwd),
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
            "files": (out_f, err_f),
            "started_at": time.time(),
        }
        return {
            "command": command,
            "cwd": str(target_cwd),
            "background": True,
            "process_id": process_id,
            "status": "running",
        }


class TerminalPollTool(BaseTool):
    name = "terminal.poll"
    description = (
        "Checks a background process started by terminal.exec (background=true): "
        "returns its status (running/exited), exit code, and the tail of its "
        "stdout/stderr. Set kill=true to terminate it."
    )
    capability = "terminal"
    critical = False
    source = "core"
    input_schema = {
        "process_id": {"type": "string", "description": "The process_id from terminal.exec.", "required": True},
        "kill": {"type": "boolean", "description": "Terminate the process.", "default": False},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        process_id = arguments.get("process_id", "")
        kill = bool(arguments.get("kill", False))

        if not process_id:
            raise ToolError("MISSING_PROCESS_ID", "Argument 'process_id' is required")

        entry = _BACKGROUND.get(process_id)
        if not entry:
            raise ToolError("PROCESS_NOT_FOUND", f"No background process with id '{process_id}'")

        proc = entry["proc"]

        if kill and proc.returncode is None:
            try:
                proc.kill()
                await asyncio.sleep(0)
            except Exception:
                pass

        running = proc.returncode is None
        stdout, stdout_truncated = _tail(entry["stdout_path"], POLL_TAIL_BYTES)
        stderr, stderr_truncated = _tail(entry["stderr_path"], POLL_TAIL_BYTES)

        # Once finished, close the log file handles and drop it from the registry.
        if not running:
            try:
                out_f, err_f = entry.get("files", (None, None))
                if out_f:
                    out_f.close()
                if err_f:
                    err_f.close()
            except Exception:
                pass
            _BACKGROUND.pop(process_id, None)

        return {
            "process_id": process_id,
            "command": entry["command"],
            "status": "running" if running else "exited",
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
