# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from laserprog_studio.tool_api.inspector import (
    BoolField,
    ButtonRow,
    ChoiceField,
    FileField,
    FloatField,
    HelpText,
    InspectorActionEvent,
    IntField,
    Panel,
    ReadonlyField,
    Section,
    Vector3Field,
)

ActionCallback = Callable[[InspectorActionEvent], bool]
RefreshCallback = Callable[[Any, Any], None]


def build_texture_projection_panel(
    *,
    owner_tool: str,
    refresh: RefreshCallback,
    preview: ActionCallback,
    clear: ActionCallback,
) -> Panel:
    return Panel(
        "Texture projection",
        id="texture.projection",
        owner_tool=owner_tool,
        description="Place image textures with viewport handles for move, size and rotation.",
        sections=(
            Section(
                "Texture",
                fields=(
                    HelpText("texture_help", "Choose an image, preview/click a face, then place it with viewport handles: center = move, ring = rotate, square = scale, edge handles = stretch."),
                    FileField("texture_path", "Image", default="", on_change=refresh),
                    ChoiceField("projection_mode", "Mode", default="planar", choices=(("planar", "Planar"), ("box", "Box"), ("cylindrical", "Cylindrical"), ("spherical", "Spherical")), on_change=refresh),
                    ChoiceField("usage", "Usage", default="visual", choices=(("engrave", "Engrave"), ("visual", "Visual only"), ("cut", "Cut outline")), on_change=refresh),
                ),
            ),
            Section(
                "Transform",
                fields=(
                    FloatField("scale", "Size", default=1.0, min_value=0.001, max_value=100000.0, step=0.1, on_change=refresh),
                    FloatField("stretch_u", "Stretch U", default=1.0, min_value=0.001, max_value=100000.0, step=0.05, visible=False, on_change=refresh),
                    FloatField("stretch_v", "Stretch V", default=1.0, min_value=0.001, max_value=100000.0, step=0.05, visible=False, on_change=refresh),
                    FloatField("rotation_deg", "Rotation", default=0.0, min_value=-180.0, max_value=180.0, step=5.0, unit="°", on_change=refresh),
                    FloatField("offset_u", "Fine offset U", default=0.0, min_value=-1000.0, max_value=1000.0, step=0.05, on_change=refresh),
                    FloatField("offset_v", "Fine offset V", default=0.0, min_value=-1000.0, max_value=1000.0, step=0.05, on_change=refresh),
                    FloatField("coverage_angle_deg", "Coverage", default=20.0, min_value=0.0, max_value=180.0, step=5.0, unit="°", on_change=refresh),
                    BoolField("repeat", "Repeat texture", default=False, on_change=refresh),
                    BoolField("attach_to_mesh", "Attach to mesh", default=False, on_change=refresh),
                    BoolField("preserve_aspect", "Keep image ratio", default=True, on_change=refresh),
                    IntField("target_index", "Target index", default=-1, min_value=-1, max_value=10_000_000, visible=False),
                    IntField("seed_face_index", "Seed face", default=-1, min_value=-1, max_value=10_000_000, visible=False),
                    Vector3Field("projection_origin", "Origin", default=(0.0, 0.0, 0.0), visible=False),
                    Vector3Field("projection_normal", "Normal", default=(0.0, 0.0, 1.0), visible=False),
                    BoolField("projection_origin_active", "Origin active", default=False, visible=False),
                ),
            ),
            Section(
                "Preview",
                fields=(
                    HelpText("placement_help", "Preview updates the texture. During drag only the lightweight projector UI is moved; the heavy mesh preview is rebuilt on release."),
                    ReadonlyField("selection_summary", "Selected", default="No mesh selected."),
                    ButtonRow(
                        "texture_actions",
                        "Actions",
                        buttons=(("preview", "Preview selected"), ("clear", "Clear selected texture")),
                        callbacks={"preview": preview, "clear": clear},
                    ),
                    ReadonlyField("texture_report", "Report", default="Ready."),
                ),
            ),
        ),
    )


__all__ = ["build_texture_projection_panel"]
