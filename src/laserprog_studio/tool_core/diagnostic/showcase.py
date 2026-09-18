"""Visual GUI/gizmo showcase scenarios for the shared tool-core layer.

The scenarios are deterministic and renderer-independent. They populate the
shared managers with the same kinds of primitives real tools will need: large
handles, hover/selected states, batched linework, circles/arcs, text anchors,
faces, overlays and drag stress updates.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin

from ..context import ToolContext
from ..gizmos import GizmoHandle
from ..overlay import ToolButtonSpec, ToolPanelSpec

Point3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class UiShowcaseSnapshot:
    handles: int
    previews: int
    labels: int
    overlay_buttons: int
    drag_updates: int
    notes: tuple[str, ...]


class UiShowcaseBuilder:
    owner_tool = "tool_core_diag"

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self.notes: list[str] = []

    def reset_visuals(self) -> None:
        self.ctx.gizmos.clear_tool(self.owner_tool)
        # The in-memory backend stores cumulative counters for diagnostics.
        # After a visual reset, keep the counters aligned with the new scene so
        # scenario snapshots measure actor churn for the current showcase only.
        backend = self.ctx.gizmos.backend
        if hasattr(backend, "created"):
            try:
                backend.created = len(self.ctx.gizmos.handles(owner_tool=self.owner_tool))
            except Exception:
                pass
        self.ctx.preview.clear_tool(self.owner_tool)
        self.notes.clear()

    def build_overlay_gallery(self) -> None:
        group = f"{self.owner_tool}.ui_modes"
        self.ctx.overlay.show_panel(
            ToolPanelSpec(
                "diag.ui.gallery",
                "UI / Gizmo Showcase",
                [
                    ToolButtonSpec("diag.mode.modify", "Modify", icon="cursor", checkable=True, checked=True, group=group, shortcut="Esc"),
                    ToolButtonSpec("diag.mode.line", "Line", icon="line", checkable=True, group=group, shortcut="L"),
                    ToolButtonSpec("diag.mode.arc", "Arc", icon="arc", checkable=True, group=group, shortcut="A"),
                    ToolButtonSpec("diag.mode.circle", "Circle", icon="circle", checkable=True, group=group, shortcut="C"),
                    ToolButtonSpec("diag.delete", "Delete", icon="trash", enabled=False, tooltip="Enabled only when something is selected"),
                ],
            )
        )
        self.ctx.overlay.set_group_active(group, "diag.mode.circle")
        self.ctx.overlay.set_button_enabled("diag.delete", True)
        self.notes.append("Overlay gallery: exclusive modes, shortcuts, enabled/disabled action state.")

    def build_handle_states(self) -> None:
        states = [
            ("default", (0.10, 0.62, 1.00, 1.0), False, False, 18),
            ("hover", (0.20, 0.90, 1.00, 1.0), False, True, 22),
            ("selected", (1.00, 0.80, 0.20, 1.0), True, False, 24),
            ("locked", (0.55, 0.62, 0.70, 0.55), False, False, 18),
        ]
        for idx, (label, color, selected, hover, radius) in enumerate(states):
            x = float(idx) * 9.0
            self.ctx.gizmos.create_handle(
                GizmoHandle(
                    id=f"diag:handle:{label}",
                    owner_tool=self.owner_tool,
                    position=(x, 0.0, 0.35),
                    radius_px=radius,
                    color=color,
                    selected=selected,
                    hover=hover,
                    selectable=(label != "locked"),
                    kind="state",
                )
            )
            self.ctx.preview.show_text(
                f"diag:label:{label}",
                self.owner_tool,
                label,
                (x, -3.2, 0.35),
                size_px=14,
            )
        self.notes.append("Handle states: large readable hit targets with explicit default/hover/selected/locked styles.")

    def build_primitives(self) -> None:
        # Line and polyline examples.
        self.ctx.preview.show_line("diag:line", self.owner_tool, (0.0, 10.0, 0.1), (28.0, 10.0, 0.1))
        self.ctx.preview.show_polyline(
            "diag:polyline",
            self.owner_tool,
            [(0.0, 15.0, 0.1), (7.0, 21.0, 0.1), (17.0, 16.0, 0.1), (29.0, 23.0, 0.1)],
        )

        # Circle and arc examples sampled once; real renderer can batch them as line cells.
        center = (43.0, 13.0, 0.1)
        radius = 6.0
        circle: list[Point3] = []
        for i in range(49):
            t = (2.0 * pi * i) / 48.0
            circle.append((center[0] + cos(t) * radius, center[1] + sin(t) * radius, center[2]))
        self.ctx.preview.show_circle("diag:circle", self.owner_tool, circle)

        arc: list[Point3] = []
        for i in range(25):
            t = pi * i / 24.0
            arc.append((62.0 + cos(t) * 7.0, 14.0 + sin(t) * 7.0, 0.1))
        self.ctx.preview.show_arc("diag:arc", self.owner_tool, arc)

        # Face example: closed 2D area suitable for extrusion preview.
        face = ((39.0, 25.0, 0.05), (55.0, 25.0, 0.05), (58.0, 35.0, 0.05), (36.0, 35.0, 0.05))
        self.ctx.preview.show_face("diag:face", self.owner_tool, face)
        self.ctx.preview.show_text("diag:text:face", self.owner_tool, "closed face preview", (46.0, 30.0, 0.2), size_px=13)
        self.notes.append("Primitives: line, polyline, circle, arc and filled face are preview items, not tool-specific actors.")

    def build_snap_guides(self) -> None:
        guide_points = [(0.0, 42.0, 0.2), (10.0, 42.0, 0.2), (20.0, 42.0, 0.2), (30.0, 42.0, 0.2)]
        for idx, point in enumerate(guide_points):
            self.ctx.gizmos.create_handle(
                GizmoHandle(
                    id=f"diag:snap:{idx}",
                    owner_tool=self.owner_tool,
                    position=point,
                    radius_px=17,
                    color=(0.70, 0.95, 0.30, 1.0),
                    kind="snap",
                )
            )
        self.ctx.preview.show_polyline("diag:snap:guide", self.owner_tool, guide_points)
        self.ctx.preview.show_text("diag:text:snap", self.owner_tool, "smart snap anchors", (14.0, 38.0, 0.3), size_px=13)
        self.notes.append("Snap guides: visible anchors separate snap intent from drawn geometry.")

    def build_text_examples(self) -> None:
        labels = [
            ("2D overlay text", (0.0, 55.0, 0.25), 16),
            ("constraint: coincident", (23.0, 55.0, 0.25), 13),
            ("dimension: 28.0 mm", (48.0, 55.0, 0.25), 13),
            ("warning / invalid loop", (72.0, 55.0, 0.25), 13),
        ]
        for idx, (text, pos, size) in enumerate(labels):
            self.ctx.preview.show_text(f"diag:text:{idx}", self.owner_tool, text, pos, size_px=size)
        self.notes.append("Text examples: limited labels only; heavy text clouds must be batched or avoided.")

    def run_drag_stress(self, *, handle_count: int = 120, steps: int = 90) -> None:
        for i in range(handle_count):
            row = i // 30
            col = i % 30
            self.ctx.gizmos.create_handle(
                GizmoHandle(
                    id=f"diag:stress:{i}",
                    owner_tool=self.owner_tool,
                    position=(float(col) * 2.2, 68.0 + float(row) * 2.2, 0.15),
                    radius_px=10,
                    color=(0.32, 0.64, 1.0, 0.95),
                    kind="stress",
                )
            )
        self.ctx.gizmos.begin_interactive_update()
        for step in range(steps):
            target = step % handle_count
            self.ctx.gizmos.update_positions_only({f"diag:stress:{target}": (float(target % 30) * 2.2, 68.0 + float(target // 30) * 2.2 + 0.35, 0.15)})
            self.ctx.profiler.increment("diag.ui_stress.position_only_updates")
        self.ctx.gizmos.end_interactive_update()
        self.notes.append(f"Stress: {handle_count} handles, {steps} position-only updates, no actor deletion requested.")

    def build_full_showcase(self) -> UiShowcaseSnapshot:
        self.reset_visuals()
        self.build_overlay_gallery()
        self.build_handle_states()
        self.build_primitives()
        self.build_snap_guides()
        self.build_text_examples()
        self.run_drag_stress(handle_count=90, steps=60)
        return self.snapshot()

    def snapshot(self) -> UiShowcaseSnapshot:
        labels = sum(1 for item in self.ctx.preview.items(owner_tool=self.owner_tool) if getattr(item.kind, "value", item.kind) == "text")
        drag_updates = int(self.ctx.profiler.snapshot().get("diag.ui_stress.position_only_updates", 0))
        return UiShowcaseSnapshot(
            handles=len(self.ctx.gizmos.handles(owner_tool=self.owner_tool)),
            previews=len(self.ctx.preview.items(owner_tool=self.owner_tool)),
            labels=labels,
            overlay_buttons=len(self.ctx.overlay.buttons),
            drag_updates=drag_updates,
            notes=tuple(self.notes),
        )
