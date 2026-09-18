"""Version helpers for the public creator API."""
from __future__ import annotations

from dataclasses import dataclass

from .errors import ToolApiCompatibilityError, ToolApiValidationError

TOOL_API_VERSION = "0.13.0"
TOOL_API_STABILITY = "provisional"
CREATOR_UI_RUNTIME_CONTRACT = "native_non_overridable"


@dataclass(frozen=True, slots=True)
class ToolApiVersion:
    major: int
    minor: int
    patch: int = 0

    @classmethod
    def parse(cls, value: str | "ToolApiVersion") -> "ToolApiVersion":
        if isinstance(value, ToolApiVersion):
            return value
        raw = str(value).strip()
        parts = raw.split(".")
        if not 1 <= len(parts) <= 3:
            raise ToolApiValidationError(f"Invalid tool API version {value!r}. Expected 'MAJOR.MINOR[.PATCH]'.")
        try:
            numbers = [int(part) for part in parts]
        except ValueError as exc:
            raise ToolApiValidationError(f"Invalid tool API version {value!r}. Version parts must be integers.") from exc
        while len(numbers) < 3:
            numbers.append(0)
        if any(number < 0 for number in numbers):
            raise ToolApiValidationError(f"Invalid tool API version {value!r}. Version parts must be positive.")
        return cls(*numbers[:3])

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def _tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __lt__(self, other: str | "ToolApiVersion") -> bool:
        return self._tuple() < self.parse(other)._tuple()

    def __le__(self, other: str | "ToolApiVersion") -> bool:
        return self._tuple() <= self.parse(other)._tuple()

    def __gt__(self, other: str | "ToolApiVersion") -> bool:
        return self._tuple() > self.parse(other)._tuple()

    def __ge__(self, other: str | "ToolApiVersion") -> bool:
        return self._tuple() >= self.parse(other)._tuple()


CURRENT_TOOL_API_VERSION = ToolApiVersion.parse(TOOL_API_VERSION)


def require_tool_api(min_version: str, *, max_major: int | None = None) -> ToolApiVersion:
    """Validate that the current creator API can run a tool.

    ``max_major`` is useful for external plugins that have not opted into a
    future breaking major version.  The function returns the parsed current
    version so plugin modules can keep a single import-time guard.
    """

    minimum = ToolApiVersion.parse(min_version)
    if CURRENT_TOOL_API_VERSION < minimum:
        raise ToolApiCompatibilityError(
            f"Tool requires creator API >= {minimum}, but this build exposes {CURRENT_TOOL_API_VERSION}."
        )
    if max_major is not None and CURRENT_TOOL_API_VERSION.major > int(max_major):
        raise ToolApiCompatibilityError(
            f"Tool supports creator API major <= {int(max_major)}, but this build exposes {CURRENT_TOOL_API_VERSION}."
        )
    return CURRENT_TOOL_API_VERSION


__all__ = [
    "CREATOR_UI_RUNTIME_CONTRACT",
    "CURRENT_TOOL_API_VERSION",
    "TOOL_API_STABILITY",
    "TOOL_API_VERSION",
    "ToolApiVersion",
    "require_tool_api",
]
