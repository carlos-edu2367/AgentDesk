import json
import sys


TOOLS = [
    {
        "name": "echo",
        "description": "Echo text for AgentDesk smoke tests.",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    }
]


def respond(message_id, result):
    print(json.dumps({"jsonrpc": "2.0", "id": message_id, "result": result}), flush=True)


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        method = request.get("method")
        if method == "initialize":
            respond(request.get("id"), {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "agentdesk-mock", "version": "0.1.0"}})
        elif method == "tools/list":
            respond(request.get("id"), {"tools": TOOLS})
        elif method == "tools/call":
            args = request.get("params", {}).get("arguments", {})
            respond(request.get("id"), {"content": [{"type": "text", "text": str(args.get("message", ""))}]})
        else:
            respond(request.get("id"), {})


if __name__ == "__main__":
    main()
