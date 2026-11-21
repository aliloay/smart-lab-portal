"""Errors with stable codes and exit codes, so agents can self-correct."""
from __future__ import annotations

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_AUTH, EXIT_UNAVAILABLE, EXIT_FORBIDDEN = 0, 1, 2, 3, 4, 5


class SmartlabError(Exception):
    code = "ERROR"
    exit_code = EXIT_ERROR

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def as_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.hint:
            d["hint"] = self.hint
        return d


class AuthRequired(SmartlabError):
    code = "AUTH_REQUIRED"
    exit_code = EXIT_AUTH


class Unavailable(SmartlabError):
    code = "UNAVAILABLE"
    exit_code = EXIT_UNAVAILABLE


class Forbidden(SmartlabError):
    """A request outside the read-only allow-list. Raised before anything is sent."""
    code = "FORBIDDEN_BY_CLI_POLICY"
    exit_code = EXIT_FORBIDDEN


class NotFound(SmartlabError):
    code = "NOT_FOUND"


class InvalidInput(SmartlabError):
    code = "INVALID_INPUT"
    exit_code = EXIT_USAGE
