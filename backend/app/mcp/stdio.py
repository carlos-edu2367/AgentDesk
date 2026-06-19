from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from .errors import MCPConnectionError, MCPInitializeError, MCPToolListError
from .utils import preview


DEFAULT_TIMEOUT_SECONDS = 30


class StdioMCPClient:
    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.timeout_seconds = timeout_seconds
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self.stderr_preview = ""

    async def __aenter__(self) -> "StdioMCPClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        try:
            self._proc = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **self.env},
            )
        except Exception as exc:
            raise MCPConnectionError("Failed to start MCP stdio process.", {"error": str(exc)}) from exc

    async def initialize(self) -> dict[str, Any]:
        try:
            return await self.request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "AgentDesk", "version": "0.1.0"},
            })
        except Exception as exc:
            if isinstance(exc, MCPConnectionError):
                raise MCPInitializeError("Failed to initialize MCP server.", exc.details) from exc
            raise

    async def list_tools(self) -> list[dict[str, Any]]:
        try:
            result = await self.request("tools/list", {})
        except Exception as exc:
            if isinstance(exc, MCPConnectionError):
                raise MCPToolListError("Failed to list MCP tools.", exc.details) from exc
            raise
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            raise MCPToolListError("MCP tools/list returned an invalid response.")
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.request("tools/call", {"name": name, "arguments": arguments or {}})

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            raise MCPConnectionError("MCP process is not running.")

        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        self._proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

        try:
            line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError as exc:
            await self._capture_stderr()
            raise MCPConnectionError("MCP request timed out.", {"stderr_preview": self.stderr_preview}) from exc

        if not line:
            await self._capture_stderr()
            raise MCPConnectionError("MCP process exited without a response.", {"stderr_preview": self.stderr_preview})

        try:
            response = json.loads(line.decode("utf-8"))
        except Exception as exc:
            await self._capture_stderr()
            raise MCPConnectionError("MCP server returned invalid JSON.", {"stderr_preview": self.stderr_preview}) from exc

        if response.get("id") != request_id:
            raise MCPConnectionError("MCP server returned a response with an invalid id.")
        if response.get("error"):
            error = response["error"]
            raise MCPConnectionError(str(error.get("message") or "MCP request failed"), {"error": error})
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPConnectionError("MCP server returned an invalid result.")
        return result

    async def close(self) -> None:
        if not self._proc:
            return
        await self._capture_stderr()
        if self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()

    async def _capture_stderr(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        try:
            stderr = await asyncio.wait_for(self._proc.stderr.read(4096), timeout=0.05)
        except Exception:
            return
        if stderr:
            self.stderr_preview = preview(stderr.decode("utf-8", errors="replace"))

