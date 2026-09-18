"""Public exceptions for creator-tool API failures."""
from __future__ import annotations


class ToolApiError(Exception):
    """Base class for errors raised by the public creator API."""


class ToolApiUsageError(ToolApiError, RuntimeError):
    """Raised when an API call is made in an invalid runtime state."""


class ToolApiValidationError(ToolApiError, ValueError):
    """Raised when a creator-facing declaration is invalid."""


class ToolApiCompatibilityError(ToolApiError, RuntimeError):
    """Raised when a tool targets an incompatible API version."""


__all__ = [
    "ToolApiCompatibilityError",
    "ToolApiError",
    "ToolApiUsageError",
    "ToolApiValidationError",
]
