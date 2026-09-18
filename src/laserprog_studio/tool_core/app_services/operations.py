"""Operation registration, preview and apply services."""
from __future__ import annotations

from dataclasses import dataclass, field
import traceback
from typing import Any, Callable, Iterable, Sequence

from .common import ToolServiceError

OperationFunc = Callable[[Sequence[Any], dict[str, Any], Any], "OperationResult"]


@dataclass(frozen=True, slots=True)
class OperationResult:
    ok: bool
    meshes: tuple[Any, ...] = ()
    report: str = ""
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, meshes: Iterable[Any] = (), *, report: str = "", warnings: Iterable[str] = (), metadata: dict[str, Any] | None = None) -> "OperationResult":
        return cls(True, tuple(meshes), report=report, warnings=tuple(warnings), metadata=dict(metadata or {}))

    @classmethod
    def failure(cls, error: str, *, report: str = "", metadata: dict[str, Any] | None = None) -> "OperationResult":
        return cls(False, (), report=report, errors=(str(error),), metadata=dict(metadata or {}))


class OperationManager:
    """Operation/session API for modifiers and generated tools."""

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._operations: dict[str, OperationFunc] = {}

    def bind_context(self, ctx: Any) -> "OperationManager":
        self._ctx = ctx
        return self

    def register(self, name: str, func: OperationFunc, *, replace: bool = False) -> None:
        key = str(name).strip()
        if not key:
            raise ToolServiceError("Operation name must be non-empty.")
        if key in self._operations and not replace:
            raise ToolServiceError(f"Operation {key!r} is already registered.")
        self._operations[key] = func

    def run(self, name: str, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None) -> OperationResult:
        key = str(name)
        if key not in self._operations:
            return OperationResult.failure(f"Unknown operation: {key}")
        try:
            result = self._operations[key](tuple(inputs or ()), dict(params or {}), self._require_ctx())
            if isinstance(result, OperationResult):
                return result
            if isinstance(result, tuple):
                return OperationResult.success(result)
            return OperationResult.success((result,) if result is not None else ())
        except Exception as exc:  # pragma: no cover - defensive, verified through tests indirectly
            return OperationResult.failure(str(exc), metadata={"traceback": traceback.format_exc()})

    def run_preview(
        self,
        name: str,
        *,
        inputs: Iterable[Any] | None = None,
        params: dict[str, Any] | None = None,
        owner_tool: str = "tool",
        label: str | None = None,
    ) -> OperationResult:
        ctx = self._require_ctx()
        result = self.run(name, inputs=inputs, params=params)
        if result.ok and result.meshes:
            session = ctx.preview_session.start(owner_tool=owner_tool, label=label or f"{name} preview")
            session.show_meshes(result.meshes)
        if result.ok:
            ctx.status.info(result.report or f"Operation {name!r} preview ready")
        else:
            ctx.status.error("; ".join(result.errors) or f"Operation {name!r} failed")
        return result

    def preview(
        self,
        name: str,
        *,
        inputs: Iterable[Any] | None = None,
        params: dict[str, Any] | None = None,
        owner_tool: str = "tool",
        label: str | None = None,
    ) -> OperationResult:
        """Alias for run_preview used by creator examples."""

        return self.run_preview(name, inputs=inputs, params=params, owner_tool=owner_tool, label=label)


    def primitive_generate(self, *, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("primitive_generate", inputs=(), params=params, preview=preview, owner_tool=owner_tool)

    def box_generate(self, *, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("box_generate", inputs=(), params=params, preview=preview, owner_tool=owner_tool)

    def layflat(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("layflat", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def joint_build(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("joint_build", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def split_plane(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("split_plane", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def texture_project(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("texture_project", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def texture_clear(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("texture_clear", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def relief_text(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("relief_text", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def acoustic_diffuser(self, *, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("acoustic_diffuser", inputs=(), params=params, preview=preview, owner_tool=owner_tool)

    def cavity_volume(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("cavity_volume", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def engraving_assign(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("engraving_assign", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def repair(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("repair", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def simplify(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("simplify", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def hollow(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("hollow", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def split(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("split", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def extrude_down(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("extrude_down", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def boolean_union(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("boolean_union", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def boolean_subtract(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("boolean_subtract", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def relief(self, *, inputs: Iterable[Any] | None = None, params: dict[str, Any] | None = None, preview: bool = False, owner_tool: str = "tool") -> OperationResult:
        return self._run_standard("relief", inputs=inputs, params=params, preview=preview, owner_tool=owner_tool)

    def _run_standard(
        self,
        name: str,
        *,
        inputs: Iterable[Any] | None = None,
        params: dict[str, Any] | None = None,
        preview: bool = False,
        owner_tool: str = "tool",
    ) -> OperationResult:
        ctx = self._require_ctx()
        if inputs is None:
            selected = getattr(ctx, "scene_selection", None)
            selected_meshes = tuple(selected.selected_meshes()) if selected is not None else ()
            inputs = selected_meshes or ctx.document.meshes(include_preview=False)
        key = str(name)
        if key not in self._operations:
            backend_result = self._run_backend_operation(key, tuple(inputs or ()), dict(params or {}))
            if backend_result is not None:
                result = backend_result
            else:
                result = OperationResult.failure(f"Unknown operation: {key}")
        else:
            result = self.run(key, inputs=inputs, params=params)
        if preview and result.ok and result.meshes:
            session = ctx.preview_session.start(owner_tool=owner_tool, label=f"{key} preview")
            session.show_meshes(result.meshes)
        if result.ok:
            ctx.status.info(result.report or f"Operation {key!r} ready")
        else:
            ctx.status.error("; ".join(result.errors) or f"Operation {key!r} failed")
        return result

    def _run_backend_operation(self, name: str, inputs: tuple[Any, ...], params: dict[str, Any]) -> OperationResult | None:
        ctx = self._require_ctx()
        aliases = {"split_plane": "split", "relief_text": "relief"}
        candidate_names = (name, aliases.get(name, ""))
        method_names = tuple(method for candidate in candidate_names if candidate for method in (f"operation_{candidate}", f"run_{candidate}", candidate))
        backends = (
            getattr(ctx.document, "raw", None),
            getattr(ctx, "scene", None),
            getattr(ctx, "owner", None),
        )
        for backend in backends:
            if backend is None:
                continue
            for method_name in method_names:
                method = getattr(backend, method_name, None)
                if not callable(method):
                    continue
                try:
                    data = method(inputs=inputs, params=params, ctx=ctx)
                except TypeError:
                    try:
                        data = method(inputs, params, ctx)
                    except TypeError:
                        data = method(inputs, params)
                if isinstance(data, OperationResult):
                    return data
                if isinstance(data, tuple):
                    return OperationResult.success(data)
                return OperationResult.success((data,) if data is not None else ())
        return None

    def apply(self, result: OperationResult, *, label: str = "Apply operation") -> bool:
        if not result.ok:
            raise ToolServiceError("Cannot apply a failed operation result.")
        if not result.meshes:
            return False
        self._require_ctx().document.set_meshes(result.meshes, label=label, push_undo=True)
        return True

    def _require_ctx(self) -> Any:
        if self._ctx is None:
            raise ToolServiceError("OperationManager is not bound to a ToolContext.")
        return self._ctx
