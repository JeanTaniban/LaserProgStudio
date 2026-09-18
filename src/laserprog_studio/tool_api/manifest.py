"""Small manifest contract for external creator tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Literal

from .errors import ToolApiValidationError
from .versioning import require_tool_api

ToolManifestCategory = Literal["tool", "modifier"]


@dataclass(frozen=True, slots=True)
class ToolManifest:
    """Metadata an external tool package can expose next to its entrypoint."""

    id: str
    label: str
    entrypoint: str
    api_min: str = "0.13.0"
    category: ToolManifestCategory = "tool"
    description: str = ""
    author: str = ""
    permissions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _clean_required("id", self.id))
        object.__setattr__(self, "label", _clean_required("label", self.label))
        object.__setattr__(self, "entrypoint", _clean_required("entrypoint", self.entrypoint))
        object.__setattr__(self, "api_min", _clean_required("api_min", self.api_min))
        object.__setattr__(self, "category", str(self.category))
        object.__setattr__(self, "permissions", tuple(str(value).strip() for value in self.permissions if str(value).strip()))
        if ":" not in self.entrypoint:
            raise ToolApiValidationError(
                f"Tool manifest {self.id!r} entrypoint must use 'module:function' syntax."
            )
        if self.category not in {"tool", "modifier"}:
            raise ToolApiValidationError(f"Tool manifest {self.id!r} category must be 'tool' or 'modifier'.")

    def validate_runtime(self) -> None:
        require_tool_api(self.api_min)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "entrypoint": self.entrypoint,
            "api_min": self.api_min,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "permissions": list(self.permissions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ToolManifest":
        permissions = data.get("permissions", ())
        if isinstance(permissions, str):
            permissions = (permissions,)
        return cls(
            id=str(data.get("id", "")),
            label=str(data.get("label", "")),
            entrypoint=str(data.get("entrypoint", "")),
            api_min=str(data.get("api_min", "0.13.0")),
            category=str(data.get("category", "tool")),  # type: ignore[arg-type]
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            permissions=tuple(str(value) for value in permissions if str(value).strip()) if isinstance(permissions, Iterable) else (),
        )


def _clean_required(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise ToolApiValidationError(f"Tool manifest field {name!r} must be non-empty.")
    return text


__all__ = ["ToolManifest", "ToolManifestCategory"]
