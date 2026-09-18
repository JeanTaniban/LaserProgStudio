"""Shared types and errors for ToolContext application services."""
from __future__ import annotations


class ToolServiceError(RuntimeError):
    """Raised by creator services when no compatible application backend exists."""
