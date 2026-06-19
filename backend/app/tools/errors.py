class ToolError(Exception):
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ToolNotFoundError(ToolError):
    def __init__(self, tool_name: str):
        super().__init__("TOOL_NOT_FOUND", f"Tool '{tool_name}' does not exist")
        self.tool_name = tool_name


class ToolDeniedError(ToolError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message)


class PathOutOfWorkspaceError(ToolError):
    def __init__(self, path: str):
        super().__init__("PATH_OUT_OF_WORKSPACE", f"Path '{path}' is outside all authorized workspaces")
        self.path = path


class InvalidPathError(ToolError):
    def __init__(self, path: str, reason: str = ""):
        super().__init__("INVALID_PATH", f"Invalid path '{path}'" + (f": {reason}" if reason else ""))
        self.path = path


class WorkspaceNotFoundError(ToolError):
    def __init__(self, workspace_id: str):
        super().__init__("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found")
        self.workspace_id = workspace_id
