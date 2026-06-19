# AgentDesk Plugin SDK

## Structure

```txt
my-plugin/
  plugin.json
  tools/
    echo.py
  skills/
    echo.skill.json
```

## plugin.json

`plugin.json` declares identity, tools, skills, permissions, command, and timeout. Keep IDs stable and unique.

```json
{
  "id": "echo-plugin",
  "name": "Echo Plugin",
  "version": "0.1.0",
  "permissions": [],
  "tools": [
    {
      "name": "echo",
      "description": "Return the provided message.",
      "command": "python tools/echo.py",
      "timeout_seconds": 5,
      "input_schema": {
        "message": { "type": "string", "required": true }
      }
    }
  ],
  "skills": ["skills/echo.skill.json"]
}
```

## Tool Runtime

Plugin tools use JSON on stdin/stdout. The backend sends one JSON object to stdin. The tool prints one JSON object to stdout. Stderr is treated as diagnostic output and may be truncated.

## Permissions and Capabilities

Plugin tools do not bypass the Permission Gate. Agents still need explicit tools or capabilities, and critical actions must be approved in manual mode.

## Timeout

Each tool declares `timeout_seconds`. Long-running tools should fail cleanly and avoid background processes.

## Security

Do not put secrets in plugin manifests, stdout, stderr, or skill files. Plugins are local code execution; only import trusted folders. The MVP does not provide a strong sandbox, remote installation, or plugin dependency management.

## Example

See `examples/plugins/echo-plugin`.
