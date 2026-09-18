"""Private orchestration class for official Creator UI motifs.

The public API lives in :mod:`laserprog_studio.tool_api.ui_motifs`.  The large
motif row builders are split into focused private modules so this file stays as
an orchestration layer instead of another runtime blob.
"""
from __future__ import annotations

from typing import Any, Iterable

from laserprog_studio.tool_core.preview import PreviewKind
from laserprog_studio.tool_core.selection import ToolActor

from ._ui_motif_actor_rows import (
    _build_actor_interaction_motifs,
    _build_actor_kind_motifs,
    _handle_position,
    _refresh_handle_dependencies,
    _render_actor_motif,
)
from ._ui_motif_contract import (
    FAMILY_ACTOR_INTERACTIONS,
    FAMILY_ACTOR_KINDS,
    FAMILY_LINE_STYLES,
    FAMILY_MANIPULATORS,
    FAMILY_OVERLAYS,
    FAMILY_POINT_STYLES,
    FAMILY_PREVIEWS,
    FAMILY_VISUAL_STATES,
    CreatorUiMotifSnapshot,
    normalize_creator_ui_motif_families,
)
from ._ui_motif_runtime import (
    _label,
    _register_actor_motif,
    _register_existing_family_handles_as_actors,
    _register_handle_actor,
    _show_handle,
    _sync_handle_actor_visual,
)
from ._ui_motif_showcase_rows import (
    _build_manipulator_motifs,
    _build_overlay_motifs,
    _build_preview_motifs,
)
from ._ui_motif_style_rows import (
    _build_line_style_motifs,
    _build_point_style_motifs,
    _build_visual_state_motifs,
)


class CreatorUiMotifBuilder:
    """Build and refresh the official UI/Gizmo motif scene.

    This class owns orchestration, lifecycle and snapshots.  The concrete row
    builders live in focused private modules to keep public behaviour stable
    while making future migrations safe and local.
    """

    _register_actor_motif = _register_actor_motif
    _register_handle_actor = _register_handle_actor
    _sync_handle_actor_visual = _sync_handle_actor_visual
    _register_existing_family_handles_as_actors = _register_existing_family_handles_as_actors
    _label = _label
    _show_handle = _show_handle
    _build_actor_kind_motifs = _build_actor_kind_motifs
    _render_actor_motif = _render_actor_motif
    _handle_position = _handle_position
    _refresh_handle_dependencies = _refresh_handle_dependencies
    _build_actor_interaction_motifs = _build_actor_interaction_motifs
    _build_visual_state_motifs = _build_visual_state_motifs
    _build_point_style_motifs = _build_point_style_motifs
    _build_line_style_motifs = _build_line_style_motifs
    _build_manipulator_motifs = _build_manipulator_motifs
    _build_preview_motifs = _build_preview_motifs
    _build_overlay_motifs = _build_overlay_motifs

    def __init__(self, ctx: Any, *, owner_tool: str) -> None:
        self.ctx = ctx
        self.owner_tool = str(owner_tool)
        self._dirty_handle_ids: set[str] = set()
        self._dirty_preview_ids: set[str] = set()

    def build(self, families: Iterable[str] | None = None) -> CreatorUiMotifSnapshot:
        selected = self._normalize_families(families)
        self.clear()
        return self.refresh(selected)

    def refresh(self, families: Iterable[str] | None = None) -> CreatorUiMotifSnapshot:
        """Re-render official motif visuals while preserving registered actors."""

        selected = self._normalize_families(families)
        owner = self.owner_tool
        self.ctx.preview.clear_tool(owner)
        self.ctx.gizmos.clear_tool(owner)
        self.ctx.overlay.close_tool_windows(owner, include_persistent=True)
        if FAMILY_ACTOR_KINDS in selected:
            self._build_actor_kind_motifs()
        if FAMILY_ACTOR_INTERACTIONS in selected:
            self._build_actor_interaction_motifs()
        if FAMILY_VISUAL_STATES in selected:
            self._build_visual_state_motifs()
        if FAMILY_POINT_STYLES in selected:
            self._build_point_style_motifs()
        if FAMILY_LINE_STYLES in selected:
            self._build_line_style_motifs()
        if FAMILY_MANIPULATORS in selected:
            self._build_manipulator_motifs()
        if FAMILY_PREVIEWS in selected:
            self._build_preview_motifs()
        if FAMILY_OVERLAYS in selected:
            self._build_overlay_motifs(visible=True)
        try:
            self.ctx.scene_cache.rebuild(self.ctx, scope="snap")
        except Exception:
            pass
        return self.snapshot(selected)

    def refresh_interaction_visuals(
        self,
        *,
        changed_actor_ids: Iterable[str] | None = None,
        position_only: bool = False,
        return_snapshot: bool = True,
    ) -> CreatorUiMotifSnapshot | None:
        """Update interactive motif visuals without clearing/rebuilding them.

        ``return_snapshot=False`` skips the trailing :meth:`snapshot` call.
        The snapshot walks every preview, overlay window, actor and handle for
        the owner tool to build a count summary; it is useful for tests and
        diagnostics but unused by viewport-side drag/hover refreshes that
        merely need the visuals updated. Skipping it shaved off a notable
        share of per-mouse-move CPU in dense Plan tracer sketches.
        """

        self._dirty_handle_ids.clear()
        self._dirty_preview_ids.clear()
        changed = None if changed_actor_ids is None else tuple(dict.fromkeys(str(value) for value in changed_actor_ids))
        if changed is None:
            try:
                self.ctx.profiler.increment("creator.ui.refresh.owner_scan")
            except Exception:
                pass
            actors_to_sync = tuple(self.ctx.selection.actors(owner_tool=self.owner_tool))
        else:
            try:
                self.ctx.profiler.increment("creator.ui.refresh.direct_lookup", len(changed))
            except Exception:
                pass
            # Hover/cursor/drag hot paths usually know the exact actor ids that
            # changed.  Do not call ``selection.actors(owner_tool=...)`` here: it
            # walks every tool actor and was visible in Plan Tracer mouse-move
            # timings after the snap cache itself had been fixed.
            direct: list = []
            for actor_id in changed:
                actor = self.ctx.selection.actor(actor_id)
                if actor is not None and actor.owner_tool == self.owner_tool:
                    direct.append(actor)
            actors_to_sync = tuple(direct)

        self.ctx.gizmos.begin_interactive_update()
        try:
            for actor in actors_to_sync:
                self._refresh_interaction_actor(actor, position_only=position_only)
        finally:
            self.ctx.gizmos.end_interactive_update()
        try:
            self.ctx.selection.state.dirty_visual_handle_ids = tuple(sorted(self._dirty_handle_ids))
            self.ctx.selection.state.dirty_visual_preview_ids = tuple(sorted(self._dirty_preview_ids))
        except Exception:
            pass
        if not return_snapshot:
            return None
        return self.snapshot()

    def _refresh_interaction_actor(self, actor: ToolActor, *, position_only: bool) -> None:
        family = str(actor.metadata.get("motif_family", ""))
        if actor.metadata.get("motif_kind") == "handle":
            self._sync_handle_actor_visual(actor, position_only=position_only)
            self._refresh_handle_dependencies(actor)
        elif family in {FAMILY_ACTOR_KINDS, FAMILY_ACTOR_INTERACTIONS} or str(actor.id).startswith(f"{self.owner_tool}:{FAMILY_ACTOR_KINDS}:"):
            self._render_actor_motif(actor, family or FAMILY_ACTOR_KINDS)
        elif family:
            # Public Creator/Plan2D tools also use the official actor motif
            # metadata.  Selection/hover feedback must therefore refresh their
            # linework too, not only the diagnostic catalogue families.
            self._render_actor_motif(actor, family)

    def clear(self) -> None:
        owner = self.owner_tool
        self.ctx.preview.clear_tool(owner)
        self.ctx.gizmos.clear_tool(owner)
        self.ctx.selection.clear_tool(owner)
        self.ctx.overlay.close_tool_windows(owner, include_persistent=True)
        try:
            self.ctx.scene_cache.clear_tool_targets(owner)
        except Exception:
            pass

    def snapshot(self, families: Iterable[str] | None = None) -> CreatorUiMotifSnapshot:
        owner = self.owner_tool
        selected = self._normalize_families(families)
        previews = self.ctx.preview.items(owner_tool=owner)
        labels = sum(1 for item in previews if getattr(item.kind, "value", item.kind) in {PreviewKind.TEXT.value, "text"})
        windows = tuple(window for window in self.ctx.overlay.windows.values() if window.owner_tool == owner)
        return CreatorUiMotifSnapshot(
            owner_tool=owner,
            families=selected,
            actors=len(self.ctx.selection.actors(owner_tool=owner)),
            handles=len(self.ctx.gizmos.handles(owner_tool=owner)),
            previews=len(previews),
            labels=labels,
            overlay_windows=len(windows),
        )

    @staticmethod
    def _normalize_families(families: Iterable[str] | None = None) -> tuple[str, ...]:
        return normalize_creator_ui_motif_families(families)

    def _id(self, family: str, *parts: object) -> str:
        suffix = ":".join(str(part).replace(" ", "_") for part in parts if str(part) != "")
        return f"{self.owner_tool}:{family}:{suffix}" if suffix else f"{self.owner_tool}:{family}"

    @staticmethod
    def _kind(family: str, *parts: object) -> str:
        suffix = ":".join(str(part).replace(" ", "_") for part in parts if str(part) != "")
        return f"catalog:{family}:{suffix}" if suffix else f"catalog:{family}"

    def _family_from_actor_id(self, actor_id: str) -> str:
        prefix = f"{self.owner_tool}:"
        value = str(actor_id)
        if value.startswith(prefix):
            return value[len(prefix):].split(":", 1)[0]
        return ""


__all__ = ["CreatorUiMotifBuilder"]
