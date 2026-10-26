"""Errors that agents raise to return a safe JSON response from the host."""


class ServiceUnavailable(RuntimeError):
    """A required service (such as storage) is not configured. The message is safe to show."""


class AgentInputError(Exception):
    """A request input is invalid. The host returns the status code with a safe message."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
