class PluginError(Exception):
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class PluginNotFoundError(PluginError):
    status_code = 404


class PluginValidationError(PluginError):
    status_code = 400


class PluginConflictError(PluginError):
    status_code = 409
