# -*- coding: utf-8 -*-
from __future__ import annotations

from ..ids import TOOL_PLAN_TRACE

_TOOL_GROUP = "plan_trace_2d.tool"
_ANCHOR_OVERLAY_ID = "plan_trace_2d.anchor_prompt"
_TOOLBOX_ID = "plan_trace_2d.toolbox"
_MODE_BADGE_ID = "plan_trace_2d.mode_badge"
_DELETE_BUTTON_ID = "plan_trace_2d.action.delete"
_RESTORE_FACES_BUTTON_ID = "plan_trace_2d.action.restore_faces"
_PATTERN_FACE_BUTTON_ID = "plan_trace_2d.action.pattern_face"
_VALIDATE_ADD_BUTTON_ID = "plan_trace_2d.validation.add"
_VALIDATE_SUBTRACT_BUTTON_ID = "plan_trace_2d.validation.subtract"
_PATTERN_GENERATE_BUTTON_ID = "plan_trace_2d.action.pattern_generate"
_METRIC_OVERLAY_ID = "plan_trace_2d.metric_overlay"
_METRIC_VALIDATE_BUTTON_ID = "plan_trace_2d.metric.validate"
_METRIC_CANCEL_BUTTON_ID = "plan_trace_2d.metric.cancel"

# Pattern (pattern) overlay: dedicated viewport window for browsing motifs and
# editing parameters with a live preview of the perforation.  The Plan Tracer
# toolbox "Pattern" button toggles this overlay; opening requires a Plan Tracer
# face already selected via Modify mode so the workflow stays linear:
#   Modify → click face → Pattern → tweak → Apply / Back.
# IMPORTANT: the Apply button id MUST contain the substring "apply" so the
# generic Qt overlay layer flushes pending QLineEdit text through
# ``flush_overlay_edits_for_button`` (tool_core/overlay/qt_commit.py) before
# routing the click to the tool.  Without that token the user's most recent
# value would be discarded on commit, regenerating the motif with stale state.
# IMPORTANT: the cancel/return button id deliberately does NOT contain 'close':
# the generic Qt adapter treats close-like ids as a direct window hide, which
# would bypass Plan Tracer's preview rollback.
_MOTIF_OVERLAY_ID = "plan_trace_2d.motif_overlay"
_MOTIF_BUTTON_PREV = "plan_trace_2d.motif.prev"
_MOTIF_BUTTON_NEXT = "plan_trace_2d.motif.next"
_MOTIF_BUTTON_PRESET_SAVE = "plan_trace_2d.motif.preset.save"
_MOTIF_BUTTON_PRESET_DELETE = "plan_trace_2d.motif.preset.delete"
_MOTIF_BUTTON_KEEP_FORM = "plan_trace_2d.motif.keep_form"
_MOTIF_BUTTON_APPLY = "plan_trace_2d.motif.apply"
_MOTIF_BUTTON_CLOSE = "plan_trace_2d.motif.cancel"
_MOTIF_FIELD_KIND = "plan_trace_2d.motif.kind"
_MOTIF_FIELD_PRESET = "plan_trace_2d.motif.preset"
_MOTIF_FIELD_PRESET_NAME = "plan_trace_2d.motif.preset_name"
_MOTIF_FIELD_FACE = "plan_trace_2d.motif.face"
_MOTIF_FIELD_CELL_SIZE = "plan_trace_2d.motif.cell_size"
_MOTIF_FIELD_WALL = "plan_trace_2d.motif.wall"
_MOTIF_FIELD_MARGIN = "plan_trace_2d.motif.margin"
_MOTIF_FIELD_KEEP_FORM = "plan_trace_2d.motif.keep_form"
_MOTIF_FIELD_ANGLE = "plan_trace_2d.motif.angle"
_MOTIF_FIELD_ASPECT = "plan_trace_2d.motif.aspect"
_MOTIF_FIELD_SEED = "plan_trace_2d.motif.seed"
_MOTIF_FIELD_OFFSET_X = "plan_trace_2d.motif.offset_x"
_MOTIF_FIELD_OFFSET_Y = "plan_trace_2d.motif.offset_y"
_MOTIF_FIELD_STATUS = "plan_trace_2d.motif.status"
_CURSOR_ID = f"{TOOL_PLAN_TRACE}:cursor"
_ANCHOR_ID = f"{TOOL_PLAN_TRACE}:height_anchor"
_PENDING_PREVIEW_PREFIX = f"{TOOL_PLAN_TRACE}:pending_preview"

_PHASE_PICK_HEIGHT = "pick_height"
_PHASE_DRAW = "draw"
_MODE_MODIFY = "modify"
_MODE_LINE = "line"
_MODE_POLYLINE = "polyline"
_MODE_RECTANGLE = "rectangle"
_MODE_CIRCLE = "circle"
_MODE_ARC = "arc"
_MODE_BEZIER = "bezier"
_MODE_HALF_CIRCLE = "half_circle"
_MODE_POINT = "point"
_MODE_DIMENSION = "dimension"
_MODE_MESH_TRACE = "mesh_trace"
_MODE_DUPLICATE = "duplicate"
_MODE_MIRROR = "mirror"
_TOOL_MODES = (_MODE_MODIFY, _MODE_MESH_TRACE, _MODE_DUPLICATE, _MODE_MIRROR, _MODE_LINE, _MODE_POLYLINE, _MODE_RECTANGLE, _MODE_CIRCLE, _MODE_ARC, _MODE_BEZIER, _MODE_HALF_CIRCLE, _MODE_POINT, _MODE_DIMENSION)
_DRAW_INPUT_MODES = (_MODE_LINE, _MODE_POLYLINE, _MODE_RECTANGLE, _MODE_CIRCLE, _MODE_ARC, _MODE_BEZIER, _MODE_HALF_CIRCLE, _MODE_POINT, _MODE_DIMENSION)
_IMPLEMENTED_DRAW_MODES = (_MODE_LINE, _MODE_POLYLINE, _MODE_RECTANGLE, _MODE_CIRCLE, _MODE_ARC, _MODE_BEZIER, _MODE_HALF_CIRCLE, _MODE_POINT, _MODE_DIMENSION)

__all__ = [
    "_TOOL_GROUP",
    "_ANCHOR_OVERLAY_ID",
    "_TOOLBOX_ID",
    "_MODE_BADGE_ID",
    "_DELETE_BUTTON_ID",
    "_RESTORE_FACES_BUTTON_ID",
    "_PATTERN_FACE_BUTTON_ID",
    "_VALIDATE_ADD_BUTTON_ID",
    "_VALIDATE_SUBTRACT_BUTTON_ID",
    "_PATTERN_GENERATE_BUTTON_ID",
    "_METRIC_OVERLAY_ID",
    "_METRIC_VALIDATE_BUTTON_ID",
    "_METRIC_CANCEL_BUTTON_ID",
    "_MOTIF_OVERLAY_ID",
    "_MOTIF_BUTTON_PREV",
    "_MOTIF_BUTTON_NEXT",
    "_MOTIF_BUTTON_PRESET_SAVE",
    "_MOTIF_BUTTON_PRESET_DELETE",
    "_MOTIF_BUTTON_KEEP_FORM",
    "_MOTIF_BUTTON_APPLY",
    "_MOTIF_BUTTON_CLOSE",
    "_MOTIF_FIELD_KIND",
    "_MOTIF_FIELD_PRESET",
    "_MOTIF_FIELD_PRESET_NAME",
    "_MOTIF_FIELD_FACE",
    "_MOTIF_FIELD_CELL_SIZE",
    "_MOTIF_FIELD_WALL",
    "_MOTIF_FIELD_MARGIN",
    "_MOTIF_FIELD_KEEP_FORM",
    "_MOTIF_FIELD_ANGLE",
    "_MOTIF_FIELD_ASPECT",
    "_MOTIF_FIELD_SEED",
    "_MOTIF_FIELD_OFFSET_X",
    "_MOTIF_FIELD_OFFSET_Y",
    "_MOTIF_FIELD_STATUS",
    "_CURSOR_ID",
    "_ANCHOR_ID",
    "_PENDING_PREVIEW_PREFIX",
    "_PHASE_PICK_HEIGHT",
    "_PHASE_DRAW",
    "_MODE_MODIFY",
    "_MODE_LINE",
    "_MODE_POLYLINE",
    "_MODE_RECTANGLE",
    "_MODE_CIRCLE",
    "_MODE_ARC",
    "_MODE_BEZIER",
    "_MODE_HALF_CIRCLE",
    "_MODE_POINT",
    "_MODE_DIMENSION",
    "_MODE_MESH_TRACE",
    "_MODE_DUPLICATE",
    "_MODE_MIRROR",
    "_TOOL_MODES",
    "_DRAW_INPUT_MODES",
    "_IMPLEMENTED_DRAW_MODES",
]
