import json
import sys


TOOLS = [
    {
        "name": "echo",
        "description": "Echoes the provided arguments.",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
        },
    }
]


def respond(message, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": message.get("id")}
    if error:
        payload["error"] = error
    else:
        payload["result"] = result
    print(json.dumps(payload), flush=True)


for line in sys.stdin:
    if not line.strip():
        continue
    request = json.loads(line)
    method = request.get("method")
    if method == "initialize":
        respond(request, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mock-mcp", "version": "0.1.0"},
        })
    elif method == "tools/list":
        respond(request, {"tools": TOOLS})
    elif method == "tools/call":
        params = request.get("params") or {}
        if params.get("name") != "echo":
            respond(request, error={"code": -32601, "message": "Tool not found"})
        else:
            respond(request, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "called": params.get("name"),
                            "arguments": params.get("arguments") or {},
                        }),
                    }
                ]
            })
    else:
        respond(request, error={"code": -32601, "message": f"Unknown method {method}"})
