class MCPError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class MCPServerNotFoundError(MCPError):
    def __init__(self, server_id: str):
        super().__init__("MCP_SERVER_NOT_FOUND", f"MCP server '{server_id}' was not found")


class MCPConnectionError(MCPError):
    def __init__(self, message: str = "Failed to initialize MCP server.", details: dict | None = None):
        super().__init__("MCP_CONNECTION_FAILED", message, details)


class MCPInitializeError(MCPError):
    def __init__(self, message: str = "Failed to initialize MCP server.", details: dict | None = None):
        super().__init__("MCP_INITIALIZE_FAILED", message, details)


class MCPToolListError(MCPError):
    def __init__(self, message: str = "Failed to list MCP tools.", details: dict | None = None):
        super().__init__("MCP_TOOL_LIST_FAILED", message, details)

